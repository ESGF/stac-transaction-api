import sys
import re
from settings import STAC_API

# Key = Solr name
# Value = STAC name
# None = unchanged
item_properties = {
#    "access": None, # Replaced by "protocol" in asset
    "latest": None,
    "master_id": "base_id", # Add and rename
#    "project": None, # Redundant with "collection", not part of the schema
    "retracted": None,
    "title": None,
}

# Key = Solr name
# Value = STAC name
# None = unchanged
project_item_properties = {
    "CMIP6": {
        "activity_id": None,
        "cf_standard_name": "variable_cf_standard_name",
        "citation_url": None,
        "data_specs_version": None,
        "experiment_id": None,
        "experiment_title": "experiment",
        "frequency": None,
        "further_info_url": None,
        "grid": None,
        "grid_label": None,
        "institution_id": None,
        "member_id": None,
 #       "mip_era": None, # Redundant with "collection", not part of the schema
        "nominal_resolution": None,
        "pid": None,
        "product": None,
        "realm": None,
        "source_id": None,
        "source_type": None,
        "sub_experiment_id": None,
        "table_id": None,
        "variable_id": None,
        "variable_long_name": None,
        "variable_units": None,
        "variant_label": None,
        "version": None
    }
}

list_properties = [
    "activity_id",
#    "access",
    "realm",
    "source_type",
]


def convert2stac(json_data):
    dataset_doc = {}
    for doc in json_data:
        if doc.get("type") == "Dataset":
            dataset_doc = doc
            break

    assets = {}

    if "Globus" in dataset_doc.get("access"):
        for doc in json_data:
            if doc.get("type") == "File":
                urls = doc.get("url")
                for url in urls:
                    if url.startswith("globus:"):
                        m = re.search(r"^globus:([^/]*)(.*/)[^/]*$", url)
                        href = f"https://app.globus.org/file-manager?origin_id={m[1]}&origin_path={m[2]}"
                        assets = {
                            "globus": {
                                "href": href,
                                "description": "Dataset Globus Web App Link",
                                "type": "text/html",
                                "roles": ["data"],
                                "alternate:name": dataset_doc.get("data_node"),
                                "created": doc.get("timestamp", "2025-01-02T00:00:00Z"),
                                "updated": "2025-01-02T00:00:00Z",
                                "protocol": "globus",
                            }
                        }
                break

    size = 0
    if "HTTPServer" in dataset_doc.get("access"):
        counter = 0
        for doc in json_data:
            if doc.get("type") == "File":
                urls = doc.get("url")
                for url in urls:
                    if url.endswith("application/netcdf|HTTPServer"):
                        url_split = url.split("|")
                        href = url_split[0]
                        checksum_type = doc.get("checksum_type")[0]
                        if checksum_type != "SHA256":
                            print("{checksum_type} not supported")
                            sys.exit(1)
                        assets[f"data{counter:04}"] = {
                            "href": href,
                            "description": "HTTPServer Link",
                            "type": "application/netcdf",
                            "roles": ["data"],
                            "alternate:name": dataset_doc.get("data_node"),
                            "file:size": doc.get("size", 0),
                            "file:checksum": "1220" + doc.get("checksum")[0],
                            "cmip6:tracking_id": doc.get("tracking_id")[0],
                            "created": doc.get("timestamp", "2025-01-02T00:00:00Z"),
                            "updated": "2025-01-02T00:00:00Z",
                            "protocol": "http"
                        }
                        size += doc.get("size", 0)
                        counter += 1
                        break

    if not assets:
        return None


    collection = dataset_doc.get("project")[0]
    item_id = dataset_doc.get("instance_id")
    west_degrees = dataset_doc.get("west_degrees", 0.0)
    south_degrees = dataset_doc.get("south_degrees", -90.0)
    east_degrees = dataset_doc.get("east_degrees", -360.0)
    north_degrees = dataset_doc.get("north_degrees", 90.0)

    properties = {
        "datetime": None,
        "start_datetime": dataset_doc.get("datetime_start", "1975-01-01T00:00:00Z"),
        "end_datetime": dataset_doc.get("datetime_end", "1975-01-02T00:00:00Z"),
        "size": size,
        "created": dataset_doc.get("timestamp", "2025-01-02T00:00:00Z"),
        "updated": "2025-01-02T00:00:00Z"
    }

    collection_item_properties = project_item_properties.get(collection, [])
    property_keys = list(item_properties.keys()) + list(collection_item_properties.keys())
    namespace = collection.lower()

    for k in property_keys:
        v = dataset_doc.get(k)
        if k in item_properties:
            if item_properties[k] is None:
                nk = k
            else:
                nk = item_properties[k]
        elif k in collection_item_properties:
            if collection_item_properties[k] is None:
                nk = f"{namespace}:{k}"
            else:
                nk = f"{namespace}:{collection_item_properties[k]}"
        # Convert version into string for pattern control.
        if k == "version" and isinstance(v, int):
            properties[nk] = str(v)
            continue
        if isinstance(v, list):
            if k in list_properties:
                properties[nk] = v
            else:
                if (v[0] is None or v[0] == "none") and k != "sub_experiment_id":
                    continue
                properties[nk] = v[0]
        else:
            # Skip none value except for sub_experiment_id
            if (v is None or v == "none") and k != "sub_experiment_id":
                continue
            properties[nk] = v

    item = {
        "type": "Feature",
        "stac_version": "1.1.0",
        "stac_extensions": [
            "https://stac-extensions.github.io/cmip6/v3.0.0/schema.json",
            #"https://esgf.github.io/stac-transaction-api/cmip6/v1.0.0/schema.json",
            #"http://host.docker.internal/cmip6/v2.0.2/schema.json",
            "https://stac-extensions.github.io/alternate-assets/v1.2.0/schema.json",
            #"http://host.docker.internal/alternate-assets/v1.2.0/schema.json",
            "https://stac-extensions.github.io/file/v2.1.0/schema.json"
            #"http://host.docker.internal/file/v2.1.0/schema.json"
        ],
        "id": item_id,
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [west_degrees, south_degrees],
                    [east_degrees, south_degrees],
                    [east_degrees, north_degrees],
                    [west_degrees, north_degrees],
                    [west_degrees, south_degrees]
                ]
            ]
        },
        "bbox": [
            west_degrees, south_degrees, east_degrees, north_degrees
        ],
        "collection": collection,
        "links": [
            {
                "rel": "self",
                "type": "application/json",
                "href": f"{STAC_API}/collections/{collection}/items/{item_id}"
            },
            {
                "rel": "parent",
                "type": "application/json",
                "href": f"{STAC_API}/collections/{collection}"
            },
            {
                "rel": "collection",
                "type": "application/json",
                "href": f"{STAC_API}/collections/{collection}"
            },
            {
                "rel": "root",
                "type": "application/json",
                "href": f"{STAC_API}/collections"
            }
        ],
        "properties": properties,
        "assets": assets
    }

    return item
