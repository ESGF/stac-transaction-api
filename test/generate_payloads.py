import argparse
import json
import os
import glob
from esgfng import convert2stac


def convert(documents_dir, payloads_dir):
    if not os.path.exists(payloads_dir):
        os.makedirs(payloads_dir)

    counter = 1
    for document_file_path in glob.glob(f"{documents_dir}/*.json"):
        file_name = os.path.basename(document_file_path)
        file_path = os.path.join(payloads_dir, file_name)

        if os.path.exists(file_path):
            print(f"{counter}: File {file_name} already exists")
            counter += 1
            continue

        if not os.path.exists(document_file_path):
            print(f"{counter}: File {file_name} does not exist in {documents_dir}")
            counter += 1
            continue
        with open(document_file_path, "r") as df:
            json_data = json.load(df)
            item = convert2stac(json_data)
            if not item:
                continue
            with open(file_path, "w") as f:
                json.dump(item, f, indent=4)
                print(f"{counter}: Generated {file_name}")
                counter += 1

def main(documents_dir, payloads_dir):
    convert(documents_dir, payloads_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate payloads for testing.")
    parser.add_argument(
        "--documents-dir",
        type=str,
        default="esgf1-payloads",
        help="A directory where files with ESGF1 metadata will be stored.",
    )
    parser.add_argument(
        "--payloads-dir",
        type=str,
        default="esgfng-payloads",
        help="A directory where files with ESGF-NG payloads will be stored.",
    )
    args = parser.parse_args()

    main(args.documents_dir, args.payloads_dir)
