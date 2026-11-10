__author__    = "Daniel Westwood"
__contact__   = "daniel.westwood@stfc.ac.uk"

# Purpose:
# - Generate STAC schema for aggregated asset conventions.
# - Utilise esgf_core_utils definitions to construct the schema.

import sys
import json
import glob

import argparse

from esgf_core_utils.models.aggregation_assets import (
    AGGREGATED_ASSETS,
    ASSET_AGG_DESCRIPTIONS,
    ASSET_AGG_MIMETYPES,
    ASSET_AGG_PROTOCOLS,
    ASSET_AGG_PATHS
)

schema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ESGF Aggregated Asset",
    "description": (
        "Aggregated Assets for ESGF-NG can be of type "
        "kerchunk, CFA, zarr or icechunk."
    ),
    "oneOf": [],
}

for asset in AGGREGATED_ASSETS:
    schema["oneOf"].append(
        {
            "type": "object",
            "required": [
                "href",
                "type",
                "roles",
                "protocol",
                "description",
            ],
            "properties": {
                "href": {
                    "type": "string"
                },
                "type": {
                    "const": ASSET_AGG_MIMETYPES[asset]
                },
                "roles": {
                    "type": "array",
                    "contains": {
                        "const": "virtual"
                    }
                },
                "protocol": {
                    "type": "string",
                    "enum": ASSET_AGG_PROTOCOLS,
                },
                "description": {
                    "const": ASSET_AGG_DESCRIPTIONS[asset]
                },
                "alternate:name": {
                    "type": "string"
                },
                "created": {
                    "type": "string",
                    "format": "date-time"
                },
                "updated": {
                    "type": "string",
                    "format": "date-time"
                },
                "file:size": {
                    "type": "integer"
                },
            },
            "additionalProperties": True,
        }
    )


# Requirements for full schema.

def latest_schema_version(schemas) -> str:
    versions = sorted(
                glob.glob(f'{schemas}/*/schema.json'))
    return versions[-1].split('/')[-2]

def latest_schema_file(schemas) -> str:
    versions = sorted(
                glob.glob(f'{schemas}/*/schema.json'))
    if len(versions) == 0:
        return None
    return versions[-1]

def determine_new_version(old_schema, new_schema, old_version):

    # MAJOR: 
    # MINOR: 
    # PATCH:

    # Once we know what counts as a change, can be more specific here.
    old_schema.pop('$id')

    if old_schema == new_schema:
        return None

    major = int(old_version.split('.')[0][1:]) #v
    minor = int(old_version.split('.')[1])
    patch = int(old_version.split('.')[2])

    # Default all patches to minor changes
    minor += 1

    return f'v{major}.{minor}.{patch}'

parser = argparse.ArgumentParser()
parser.add_argument('--schemas')
parser.add_argument('--outfile')
parser.add_argument('--outdir')

def main():
    args = parser.parse_args()
    
    file = None
    if args.schemas:
        file = latest_schema_file(args.schemas)

    if file is None:
        print(f'No initial version - output to {args.outfile}')
        with open(args.outfile,'w') as f:
            f.write(json.dumps(schema))
        return

    version = latest_schema_version(args.schemas)
    print(f'Comparing latest: {version}')
    with open(file) as f:
        refs = json.load(f)

    new_version = determine_new_version(refs, schema, version)

    if new_version:
        print(f'Differing versions - producing {new_version}')

        schema['$id'] = f"https://esgf.github.io/stac-transaction-api/aggregated_assets/{new_version}/schema.json#"

        with open(f'{args.outdir}/tmpfile_aggregation_{new_version}.json','w') as f:
            f.write(json.dumps(schema))
    else:
        print('No changes introduced in latest esgf_core_utils version')
    

if __name__ == '__main__':
    main()