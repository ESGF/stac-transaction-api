# Data challenges and tests

```
generate_payloads.py --help

usage: generate_payloads.py [-h] --datasets DATASETS [--documents-dir DOCUMENTS_DIR] [--payloads-dir PAYLOADS_DIR]

Generate payloads for testing.

options:
  -h, --help            Show this help message and exit.
  --datasets DATASETS   Path to a file containing dataset paths (one per line).
  --documents-dir DOCUMENTS_DIR
                        Directory where ESGF1 metadata files will be stored.
  --payloads-dir PAYLOADS_DIR
                        Directory where generated payload files will be stored.
```

for example

```
python generate_payloads.py --datasets West-CMIP6-paths-0001-0500.txt
```
The ESGF1 metadata will be downloaded to the `esgf1-payloads/` default directory, converted to STAC Items and stored as STAC Item metadata payloads in `esgfng-payloads/`.
