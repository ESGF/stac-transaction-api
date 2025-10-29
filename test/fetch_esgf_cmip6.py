import argparse
import json
import os
import re
import time
from typing import Dict, Any, Iterable, Set, List, Optional
from urllib.parse import urlencode

import requests

BASE_URL_DEFAULT = "https://esgf-node.ornl.gov/esgf-1-5-bridge"
OUTDIR_DEFAULT = "esgf1-payloads"

PAGE_SIZE = 1000
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES = 6
BACKOFF_BASE = 1.5


def http_get_json(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """GET JSON with retries/backoff."""
    qs = urlencode(params, doseq=True)
    full_url = f"{url}?{qs}"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(full_url, timeout=60)
            if resp.status_code in RETRY_STATUS:
                raise requests.HTTPError(f"HTTP {resp.status_code}")
            resp.raise_for_status()
            return resp.json()
        except Exception:
            if attempt == MAX_RETRIES:
                raise
            time.sleep(BACKOFF_BASE ** attempt)


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def escape_for_filename(s: str) -> str:
    """Make dataset_id filename-safe but readable."""
    s = s.strip().replace("/", "__").replace("\\", "__").replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9._+=@,:\-]+", "_", s)


def dataset_json_path(outdir: str, dsid: str) -> str:
    """Return JSON path for a dataset_id."""
    return os.path.join(outdir, f"{escape_for_filename(dsid)}.json")


def write_initial_dataset_array(outdir: str, dsid: str, ds_doc: Dict[str, Any]):
    """
    Create <outdir>/<dsid>.json as:
    [
        { ...dataset doc exactly as returned... }
    ]

    Pretty-printed with 4 spaces.
    Do nothing if the file already exists (so we don't clobber later appends).
    """
    path = dataset_json_path(outdir, dsid)
    if os.path.exists(path):
        # If it already exists we assume it's from an earlier page or resume;
        # don't overwrite.
        return
    arr = [ds_doc]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(arr, f, ensure_ascii=False, indent=4)
        f.write("\n")


def append_files_to_dataset(outdir: str, dsid: str, new_file_docs: Iterable[Dict[str, Any]]):
    """
    Load <outdir>/<dsid>.json (which is a JSON array),
    append raw file docs (unchanged),
    and overwrite the same file with the updated array, pretty-printed.
    """
    path = dataset_json_path(outdir, dsid)
    if not os.path.exists(path):
        # We didn't capture this dataset in Phase 1, skip safely.
        return

    # Load current array
    with open(path, "r", encoding="utf-8") as f:
        arr = json.load(f)

    # arr should be a list. We just extend it.
    for fdoc in new_file_docs:
        arr.append(fdoc)

    # Rewrite pretty JSON
    with open(path, "w", encoding="utf-8") as f:
        json.dump(arr, f, ensure_ascii=False, indent=4)
        f.write("\n")


def load_dataset_id(ds_doc: Dict[str, Any]) -> Optional[str]:
    """
    Find a stable dataset ID in the doc.
    We do NOT add/modify any keys in the doc; this is just to know the filename.
    """
    return ds_doc.get("id") or ds_doc.get("dataset_id") or ds_doc.get("master_id")


def comma_split(vals: List[str]) -> List[str]:
    """Split comma-separated and repeated CLI args into one list."""
    out: List[str] = []
    for v in vals:
        if "," in v:
            out.extend([x.strip() for x in v.split(",") if x.strip()])
        elif v.strip():
            out.append(v.strip())
    return out


def build_common_filters(activity_ids: List[str], institution_ids: List[str]) -> Dict[str, Any]:
    """
    Build shared facet filters for queries.
    We always include project=CMIP6.
    We are NOT mutating docs — only query params.
    """
    filt: Dict[str, Any] = {
        "project": "CMIP6"
    }
    if activity_ids:
        filt["activity_id"] = activity_ids
    if institution_ids:
        filt["institution_id"] = institution_ids
    return filt


def fetch_paged(base_url: str, params_base: Dict[str, Any], page_size: int = PAGE_SIZE):
    """
    Generic pager for Solr-like ESGF endpoint.
    Yields (page_index, total_seen, docs_for_this_page).
    Stops when the page is short.
    """
    offset = 0
    total_seen = 0
    page_index = 0
    while True:
        params = dict(params_base)
        params["limit"] = page_size
        params["offset"] = offset

        payload = http_get_json(base_url, params)
        docs = payload.get("response", {}).get("docs", [])

        if not docs:
            break

        page_index += 1
        batch = len(docs)
        total_seen += batch
        offset += batch

        yield page_index, total_seen, docs

        if batch < page_size:
            break


def process(
    base_url: str,
    outdir: str,
    data_node: str,
    max_datasets: Optional[int],
    activity_ids: List[str],
    institution_ids: List[str],
):
    ensure_dir(outdir)

    # Build filters once (always include project=CMIP6)
    common_filters = build_common_filters(activity_ids, institution_ids)

    #
    # PHASE 1: Fetch Dataset docs
    # For each dataset doc:
    #   - figure out dsid
    #   - create <outdir>/<dsid>.json with [ dataset_doc ] (pretty)
    #
    base_ds_params = {
        "type": "Dataset",
        "latest": "true",
        "format": "application/solr+json",
        "data_node": data_node,
        **common_filters,
    }

    print(
        f"[phase1] datasets from data_node={data_node} project=CMIP6 "
        f"{'(activity_id='+','.join(activity_ids)+')' if activity_ids else ''} "
        f"{'(institution_id='+','.join(institution_ids)+')' if institution_ids else ''} "
        f"max_datasets={'ALL' if not max_datasets else max_datasets}",
        flush=True,
    )

    dataset_ids: Set[str] = set()
    saved_datasets = 0

    for page_idx, total_seen, ds_docs in fetch_paged(base_url, base_ds_params, PAGE_SIZE):
        # Cap by --max-datasets if provided
        if max_datasets:
            remaining = max_datasets - saved_datasets
            if remaining <= 0:
                break
            if len(ds_docs) > remaining:
                ds_docs = ds_docs[:remaining]

        for ds_doc in ds_docs:
            dsid = load_dataset_id(ds_doc)
            if not dsid:
                continue

            # Track dataset ids for phase2 matching
            dataset_ids.add(dsid)

            # Initialize the file with [ dataset_doc ]
            write_initial_dataset_array(outdir, dsid, ds_doc)

            saved_datasets += 1

        print(
            f"[datasets] page #{page_idx}: batch={len(ds_docs)} "
            f"total_saved={saved_datasets} total_seen_raw={total_seen}",
            flush=True,
        )

        if max_datasets and saved_datasets >= max_datasets:
            break

    print(
        f"[phase1] done: unique_dataset_ids={len(dataset_ids)} "
        f"saved_datasets={saved_datasets}",
        flush=True,
    )

    #
    # PHASE 2: Fetch File docs
    # We DO NOT query per-dataset.
    # Instead we pull global file docs (same filters, same node, still project=CMIP6),
    # group them by dataset_id for this page, then append to that dataset's array file.
    #
    base_file_params = {
        "type": "File",
        "latest": "true",
        "format": "application/solr+json",
        "data_node": data_node,
        **common_filters,
    }

    print(
        f"[phase2] files global scan (no dataset_id in query), pages of {PAGE_SIZE}",
        flush=True,
    )

    files_seen_total = 0
    files_appended_total = 0

    for page_idx, total_seen, file_docs in fetch_paged(base_url, base_file_params, PAGE_SIZE):
        files_seen_total = total_seen

        # bucket by dataset_id
        buckets: Dict[str, List[Dict[str, Any]]] = {}
        for fdoc in file_docs:
            dsid = fdoc.get("dataset_id")
            # only append if this dataset was captured in phase1
            if dsid in dataset_ids:
                buckets.setdefault(dsid, []).append(fdoc)

        # For each dataset_id that had file docs in this page:
        #   - read <dsid>.json (an array of entries)
        #   - append those file docs (unchanged)
        #   - save file back pretty-printed
        for dsid, docs_for_dataset in buckets.items():
            append_files_to_dataset(outdir, dsid, docs_for_dataset)
            files_appended_total += len(docs_for_dataset)

        print(
            f"[files] page #{page_idx}: batch={len(file_docs)} "
            f"matched_this_page={sum(len(v) for v in buckets.values())} "
            f"matched_total={files_appended_total}",
            flush=True,
        )

    print("\nDone.")
    print(f"  Dataset JSON files written:    {saved_datasets}")
    print(f"  Unique dataset_ids:           {len(dataset_ids)}")
    print(f"  File docs scanned overall:    {files_seen_total}")
    print(f"  File docs merged (matched):   {files_appended_total}")
    print(f"  Output dir:                   {outdir}")


def main():
    ap = argparse.ArgumentParser(
        description=(
            "PHASE 1: Query Dataset docs (latest=true) for a given data_node, ALWAYS with project=CMIP6 "
            "and optional activity_id/institution_id filters. For each dataset_id, create:\n"
            "    <outdir>/<dataset_id>.json\n"
            "containing a JSON array with a single element: the dataset doc exactly as returned. "
            "The array is pretty-printed with 4 spaces.\n"
            "\n"
            "PHASE 2: Query File docs (latest=true) using the same filters (still project=CMIP6), "
            "paged globally with NO dataset_id filter. For each file doc, if its dataset_id matches "
            "one of the datasets from PHASE 1, load that dataset's <dataset_id>.json (the array), "
            "append the new file docs (unchanged) to the SAME array, and overwrite the file pretty-printed.\n"
            "\n"
            "End result for each dataset file is a single JSON array like:\n"
            "[\n"
            "    { ... type: \"Dataset\", ... },\n"
            "    { ... type: \"File\", ... },\n"
            "    { ... type: \"File\", ... }\n"
            "]\n"
            "We do not add wrapper keys or modify the docs; we just append them in one list. "
            "All files live directly in --outdir (no subdirs, no tmp)."
        )
    )

    ap.add_argument(
        "-o", "--outdir",
        default=OUTDIR_DEFAULT,
        help=f"Output directory (default: {OUTDIR_DEFAULT})",
    )
    ap.add_argument(
        "-b", "--base-url",
        default=BASE_URL_DEFAULT,
        help=f"Bridge URL (default: {BASE_URL_DEFAULT})",
    )
    ap.add_argument(
        "--data-node",
        dest="data_node",
        default="eagle.alcf.anl.gov",
        help="data_node=... param in all queries (default: eagle.alcf.anl.gov)",
    )
    ap.add_argument(
        "--max-datasets",
        type=int,
        default=0,
        help="Stop after saving this many datasets. 0 means ALL datasets.",
    )
    ap.add_argument(
        "--activity-id",
        dest="activity_ids",
        action="append",
        default=[],
        help="Filter by activity_id. Repeat or comma-separate values.",
    )
    ap.add_argument(
        "--institution-id",
        dest="institution_ids",
        action="append",
        default=[],
        help="Filter by institution_id. Repeat or comma-separate values.",
    )

    args = ap.parse_args()

    activity_ids = comma_split(args.activity_ids)
    institution_ids = comma_split(args.institution_ids)
    max_dsets = args.max_datasets if args.max_datasets > 0 else None

    process(
        base_url=args.base_url,
        outdir=args.outdir,
        data_node=args.data_node,
        max_datasets=max_dsets,
        activity_ids=activity_ids,
        institution_ids=institution_ids,
    )


if __name__ == "__main__":
    main()


# activity_id AerChemMIP
# institution_id NOAA-GFDL NCAR BCC DKRZ NIMS-KMA NERC UCSB

# activity_id C4MIP
# institution_id MIROC CSIRO CNRM-CERFACS NCC MRI NASA-GISS

# activity_id CFMIP
# institution_id IPSL MRI MOHC NASA-GISS CNRM-CERFACS NCAR

# activity_id DAMIP
# institution_id NCAR CNRM-CERFACS

# activity_id CDRMIP
# institution_id MOHC MIROC

# activity_id CMIP
# institution_id CAS NOAA-GFDL BCC 

# activity_id FAFMIP
# institution_id MRI MIROC NCAR
