# Synthetic Patient Dataset

## Overview

This repository contains a synthetic patient dataset in JSON format for use in the Meridian Care Network healthcare API security lab.

The dataset simulates patient records that a healthcare organization might manage when providing controlled access to patient information through APIs.

## Dataset File

- **`patients.json`** — Contains 100 fictional patient records with IDs ranging from `1001` to `1100`.

Each record includes fields such as:
- Patient ID
- Resource type
- Name
- Gender
- Date of birth
- Active status

The existing patient records `1001` (Ava Example) and `1002` (Noah Sample) are retained for compatibility with the lab instructions.

## Usage

The dataset can be downloaded using `curl` and uploaded to an Azure Blob Storage container named `input`.

```bash
curl -fL "https://raw.githubusercontent.com/OWNER/REPOSITORY/BRANCH/patients.json" \
  -o patients.json
```

Replace `OWNER`, `REPOSITORY`, and `BRANCH` with the appropriate GitHub organization or username, repository name, and branch.

## Data Disclaimer

All records in this dataset are fictional and intended for educational and testing purposes only. This dataset does not represent real patients or contain real patient information.
