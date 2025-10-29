# Data Challenges and Tests
This directory contains tools to:
- fetch ESGF 1.5 metadata and store it as payloads, and
- generate STAC metadata payloads from that ESGF metadata,
- run data challenges using those payloads.

## Fetch ESGF 1.5 Metadata
To fetch CMIP6 metadata filtered by activity and institution, run:
```
fetch_esgf_cmip6.py --activity-id AerChemMIP --institution-id NCAR
```
This will download all CMIP6 metadata with `"activity_id": ["AerChemMIP"]` and `"institution_id": ["NCAR"]`.

You can also run:
```
bash fetch_100k_cmip6.sh
```
This script fetches CMIP6 metadata for more than 100,000 datasets/files across different combinations of `activity_id` and `institution_id`.
## Generate STAC Payloads
To convert the downloaded ESGF metadata into STAC Items, run:
```
generate_payloads.py
```

## Validate STAC Items
To validate an Item, run:
```
stac-validator esgfng-payloads/CMIP6.AerChemMIP.NOAA-GFDL.GFDL-ESM4.ssp370SST-lowNTCF.r1i1p1f1.AERmon.mmrnh4.gr1.v20180701_eagle.alcf.anl.gov.json

Thanks for using STAC version 1.1.0!

[
    {
        "version": "1.1.0",
        "path": "esgfng-payloads/CMIP6.AerChemMIP.NOAA-GFDL.GFDL-ESM4.ssp370SST-lowNTCF.r1i1p1f1.AERmon.mmrnh4.gr1.v20180701_eagle.alcf.anl.gov.json",
        "schema": [
            "https://esgf.github.io/stac-transaction-api/cmip6/v1.0.0/schema.json",
            "https://stac-extensions.github.io/alternate-assets/v1.2.0/schema.json",
            "https://stac-extensions.github.io/file/v2.1.0/schema.json",
            "https://schemas.stacspec.org/v1.1.0/item-spec/json-schema/item.json"
        ],
        "valid_stac": true,
        "asset_type": "ITEM",
        "validation_method": "default"
    }
]

Validation completed in 504.94ms
```

