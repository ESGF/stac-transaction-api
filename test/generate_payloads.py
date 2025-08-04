import argparse
import json
import os
from esgf import download
from esgfng import convert2stac


def convert(paths, documents_dir, payloads_dir):
    if not os.path.exists(payloads_dir):
        os.makedirs(payloads_dir)

    counter = 1
    for path in paths:
        file_name = path.replace("/", ".") + ".json"
        file_path = os.path.join(payloads_dir, file_name)
        if os.path.exists(file_path):
            print(f"{counter}/{len(paths)}: File {file_name} already exists")
            counter += 1
            continue

        document_file_path = os.path.join(documents_dir, file_name)
        if not os.path.exists(document_file_path):
            print(f"{counter}/{len(paths)}: File {file_name} does not exist in {documents_dir}")
            counter += 1
            continue
        with open(document_file_path, "r") as df:
            json_data = json.load(df)
            item = convert2stac(json_data)
            with open(file_path, "w") as f:
                json.dump(item, f, indent=4)
                print(f"{counter}/{len(paths)}: Generated {file_name}")
                counter += 1


def main(datasets, documents_dir, payloads_dir):
    paths = []
    with open(datasets, "r") as f:
        paths = f.readlines()
    paths = [path.strip() for path in paths]
    print("Loading paths from", datasets)
    print("Found", len(paths), "paths")

    #download(paths, documents_dir)
    convert(paths, documents_dir, payloads_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate payloads for testing.")
    parser.add_argument(
        "--datasets",
        type=str,
        required=True,
        help="A file with paths to datasets.",
    )
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

    main(args.datasets, args.documents_dir, args.payloads_dir)
