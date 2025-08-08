import re
from settings import STAC_API


item_properties = [
    "access",
    "pid",
    "project",
    "version",
    "retracted",
]

project_item_properties = {
    "CMIP6": [
        "activity_id",
        "cf_standard_name",
        "citation_url",
        "data_specs_version",
        "experiment_id",
        "experiment_title",
        "frequency",
        "further_info_url",
        "grid",
        "grid_label",
        "institution_id",
        "member_id",
        "mip_era",
        "nominal_resolution",
        "pid",
        "product",
        "realm",
        "source_id",
        "source_type",
        "sub_experiment_id",
        "table_id",
        "variable",
        "variable_long_name",
        "variable_units",
        "variant_label",
    ]
}

list_properties = [
    "access",
    "realm",
    "source_type",
]


def convert2stac(json_data):
    dataset_doc = {}
    for doc in json_data:
        if doc.get("type") == "Dataset":
            dataset_doc = doc
            break

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
    }

    collection_item_properties = project_item_properties.get(collection, [])
    property_keys = item_properties + collection_item_properties
    namespace = collection.lower()

    for k in property_keys:
        v = dataset_doc.get(k)
        if k in item_properties:
            nk = k
        elif k in collection_item_properties:
            nk = f"{namespace}:{k}"
        if isinstance(v, list):
            if k in list_properties:
                properties[nk] = v
            else:
                if v[0] is None or v[0] == "none":
                    continue
                properties[nk] = v[0]
        else:
            if v is None or v == "none":
                continue
            properties[nk] = v

    item = {
        "type": "Feature",
        "stac_version": "1.0.0",
        "stac_extensions": [
            #"https://stac-extensions.github.io/cmip6/v2.0.0/schema.json",
            "http://host.docker.internal/cmip6/v2.0.1/schema.json",
            "https://stac-extensions.github.io/alternate-assets/v1.2.0/schema.json",
            "https://stac-extensions.github.io/file/v2.1.0/schema.json"
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
    }

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
                                "description": "Globus Web App Link",
                                "type": "text/html",
                                "roles": ["data"],
                                "alternate:name": dataset_doc.get("data_node"),
                            }
                        }
                break

    if "HTTPServer" in dataset_doc.get("access"):
        counter = 0
        for doc in json_data:
            if doc.get("type") == "File":
                urls = doc.get("url")
                for url in urls:
                    if url.endswith("application/netcdf|HTTPServer"):
                        url_split = url.split("|")
                        href = url_split[0]
                        assets[f"data{counter:04}"] = {
                            "href": href,
                            "description": "HTTPServer Link",
                            "type": "application/netcdf",
                            "roles": ["data"],
                            "alternate:name": dataset_doc.get("data_node"),
                            "file:size": doc.get("size", 0),
                            "file:checksum": "1220" + doc.get("checksum")[0],
                        }
                        counter += 1
                        break

    item["assets"] = assets

    return item
