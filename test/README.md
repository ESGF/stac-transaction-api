# Data Challenges and Tests

This subdirectory contains tools to generate STAC metadata payloads from ESGF1 metadata and to run data challenges using those payloads.

### Generating Payloads

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

for example, to generate payloads from a list of dataset paths:

```
python generate_payloads.py --datasets West-CMIP6-paths-0001-0500.txt
```
This will:

 - Download ESGF1 metadata files to the default directory `esgf1-payloads/`
 - Convert those files into STAC Items
 - Store the resulting STAC Item payloads in the directory `esgfng-payloads/`

### Running a Data Challenge
Once the payloads are generated, run a data challenge:
```
python data_challenge --west --dc 4
```
