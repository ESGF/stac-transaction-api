import json
import os
import sys
import time
import requests
import settings


esgf_search_url = settings.ESGF_SEARCH_URL

facets = [
    "mip_era",
    "activity_drs",
    "institution_id",
    "source_id",
    "experiment_id",
    "member_id",
    "table_id",
    "variable_id",
    "grid_label",
    "version",
]


def get_search_response(object_type, limit, extra_params):
    params = {
        "limit": limit,
        "offset": 0,
        "replica": "False",
        # "retracted": "False",
        "project": "CMIP6",
        "data_node": settings.DATA_NODE,
        "type": object_type,
        "format": "application/solr+json",
    }
    params.update(extra_params)

    r = requests.get(esgf_search_url, params=params)
    # print(r)
    if r.status_code != 200:
        print(f"The ESGF Index server returned {r.status_code}")
        sys.exit(1)

    try:
        search_response = r.json()
    except ValueError:
        print("Error when decoding JSON response from the ESGF Index server")
        sys.exit(1)
    # print(search_response)
    response = search_response.get("response")
    # print(response)
    docs = response.get("docs")
    return docs


def get_dataset_document(path):
    splitted_path = path.split("/")
    params = {}
    for i in range(len(splitted_path)):
        if facets[i] == "version":
            params[facets[i]] = splitted_path[i][1:]
        else:
            params[facets[i]] = splitted_path[i]
    while True:
        docs = get_search_response("Dataset", 1, params)
        if len(docs) == 1:
            return docs
        else:
            time.sleep(1)
            return None


def get_file_documents(dataset_id, number_of_files):
    while True:
        docs = get_search_response("File", number_of_files, {"dataset_id": dataset_id})
        if len(docs) == number_of_files:
            return docs
        else:
            time.sleep(1)
            return None


def download_dataset_documents(path):
    dataset_documents = get_dataset_document(path)
    if not dataset_documents:
        print(f"Dataset {path} not found")
        return None
    if len(dataset_documents) == 0:
        print(f"Dataset {path} not found")
        sys.exit(1)
    dataset_document = dataset_documents[0]
    dataset_id = dataset_document.get("id")
    number_of_files = dataset_document.get("number_of_files")
    # print(dataset_id, number_of_files)
    file_documents = get_file_documents(dataset_id, number_of_files)
    if not file_documents:
        print(f"Files for dataset {path} not found")
        return None
    if len(file_documents) == 0:
        print(f"Files for dataset {path} not found")
        sys.exit(1)
    dataset_documents.extend(file_documents)
    return dataset_documents


def download(paths, documents_dir):
    if not os.path.exists(documents_dir):
        os.makedirs(documents_dir)

    counter = 1
    for path in paths:
        file_name = path.replace("/", ".") + ".json"
        file_path = os.path.join(documents_dir, file_name)
        if os.path.exists(file_path):
            print(f"{counter}/{len(paths)}: File {file_name} already exists")
            counter += 1
            continue
        docs = download_dataset_documents(path)
        if not docs:
            continue
        with open(file_path, "w") as f:
            json.dump(docs, f, indent=4)
        print(f"{counter}/{len(paths)}: Downloaded", path)
        counter += 1
