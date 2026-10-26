import hmac
import json
import logging
import os

import azure.functions as func
from azure.core.exceptions import AzureError
from azure.storage.blob import BlobServiceClient

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

LEGACY_SHARED_KEY = os.environ.get("LEGACY_SHARED_KEY", "")
CLIENTS_JSON = os.environ.get("CLIENTS_JSON", "{}")
PATIENTS_STORAGE_CONNECTION_STRING = os.environ.get(
    "PATIENTS_STORAGE_CONNECTION_STRING", ""
)
PATIENTS_CONTAINER = "input"
PATIENTS_BLOB = "patients.json"


def json_response(payload, status_code=200):
    return func.HttpResponse(
        json.dumps(payload),
        status_code=status_code,
        mimetype="application/json",
    )


def supplied_key_matches(supplied_key, expected_key):
    return bool(supplied_key and expected_key) and hmac.compare_digest(
        supplied_key, expected_key
    )


def load_patients():
    """Load patient records from input/patients.json in Blob Storage."""
    if not PATIENTS_STORAGE_CONNECTION_STRING:
        raise RuntimeError(
            "PATIENTS_STORAGE_CONNECTION_STRING app setting is not configured."
        )

    blob_service = BlobServiceClient.from_connection_string(
        PATIENTS_STORAGE_CONNECTION_STRING
    )
    blob_client = blob_service.get_blob_client(
        container=PATIENTS_CONTAINER,
        blob=PATIENTS_BLOB,
    )
    raw_data = blob_client.download_blob().readall()
    patients = json.loads(raw_data)

    if not isinstance(patients, dict):
        raise ValueError("patients.json must be a JSON object keyed by patient ID.")

    for patient_id, patient in patients.items():
        if not isinstance(patient, dict) or str(patient.get("id")) != str(patient_id):
            raise ValueError(
                f"Patient record {patient_id!r} must have a matching 'id' field."
            )
    return patients


def load_clients():
    try:
        clients = json.loads(CLIENTS_JSON)
    except json.JSONDecodeError as exc:
        raise ValueError("CLIENTS_JSON must contain valid JSON.") from exc
    if not isinstance(clients, dict):
        raise ValueError("CLIENTS_JSON must be a JSON object.")
    return clients


@app.route(route="legacy-patient", methods=["GET"])
def legacy_patient(req: func.HttpRequest) -> func.HttpResponse:
    """Legacy endpoint: shared-key authentication cannot identify the calling app."""
    supplied_key = req.headers.get("x-shared-service-key", "")
    if not supplied_key_matches(supplied_key, LEGACY_SHARED_KEY):
        logging.warning("Legacy endpoint rejected a request with an invalid key.")
        return json_response({"error": "Unauthorized"}, 401)

    patient_id = req.params.get("id")
    if not patient_id:
        return json_response({"error": "Missing required query parameter: id"}, 400)

    try:
        patients = load_patients()
    except (RuntimeError, ValueError, json.JSONDecodeError):
        logging.exception("Patient data configuration or format error.")
        return json_response({"error": "Patient data is not configured correctly."}, 500)
    except AzureError:
        logging.exception("Could not load patient data from Blob Storage.")
        return json_response({"error": "Patient data is temporarily unavailable."}, 500)

    patient = patients.get(str(patient_id))
    if patient is None:
        return json_response({"error": "Patient not found"}, 404)

    logging.info("Legacy endpoint returned patient_id=%s", patient_id)
    return json_response(patient)


@app.route(route="patient/{patient_id}", methods=["GET"])
def secure_patient(req: func.HttpRequest) -> func.HttpResponse:
    """Client-specific endpoint enforcing a patient ID allowlist."""
    supplied_key = req.headers.get("x-api-key", "")
    if not supplied_key:
        logging.warning("Patient endpoint rejected a request without an API key.")
        return json_response({"error": "Unauthorized"}, 401)

    try:
        clients = load_clients()
    except ValueError:
        logging.exception("CLIENTS_JSON configuration error.")
        return json_response({"error": "Client configuration is invalid."}, 500)

    client_id = None
    client_config = None
    for configured_id, config in clients.items():
        if not isinstance(config, dict):
            continue
        if supplied_key_matches(supplied_key, config.get("api_key", "")):
            client_id = configured_id
            client_config = config
            break

    if client_config is None:
        logging.warning("Patient endpoint rejected an invalid client API key.")
        return json_response({"error": "Unauthorized"}, 401)

    patient_id = str(req.route_params.get("patient_id", ""))
    allowed_patients = [
        str(item) for item in client_config.get("allowed_patients", [])
    ]

    if patient_id not in allowed_patients:
        logging.warning(
            "Client %s denied access to patient_id=%s", client_id, patient_id
        )
        return json_response(
            {"error": "Forbidden: patient access is not permitted"}, 403
        )

    try:
        patients = load_patients()
    except (RuntimeError, ValueError, json.JSONDecodeError):
        logging.exception("Patient data configuration or format error.")
        return json_response({"error": "Patient data is not configured correctly."}, 500)
    except AzureError:
        logging.exception("Could not load patient data from Blob Storage.")
        return json_response({"error": "Patient data is temporarily unavailable."}, 500)

    patient = patients.get(patient_id)
    if patient is None:
        return json_response({"error": "Patient not found"}, 404)

    logging.info("Client %s successfully accessed patient_id=%s", client_id, patient_id)
    return json_response(patient)
