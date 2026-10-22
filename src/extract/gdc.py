import json
import time
from pathlib import Path

import requests

GDC = "https://api.gdc.cancer.gov"
PROJECT = "TCGA-BRCA"
RAW = Path("data/raw")
RAW.mkdir(parents=True, exist_ok=True)

PROJECT_FILTER = {
    "op": "in",
    "content": {"field": "cases.project.project_id", "value": [PROJECT]},
}


def and_filter(*conditions):
    return {"op": "and", "content": list(conditions)}


def in_filter(field, values):
    return {"op": "in", "content": {"field": field, "value": values}}


def fetch_all(endpoint, filters, fields, sort, page_size=200):
    """Fetch every record from a GDC endpoint, page by page."""
    hits, start = [], 0
    while True:
        payload = {
            "filters": filters,
            "fields": ",".join(fields),
            "sort": sort,
            "size": page_size,
            "from": start,
        }
        for attempt in range(3):
            try:
                r = requests.post(f"{GDC}/{endpoint}", json=payload, timeout=120)
                r.raise_for_status()
                break
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))
        data = r.json()["data"]
        hits.extend(data["hits"])
        total = data["pagination"]["total"]
        print(f"  fetched {len(hits)}/{total}")
        start += page_size
        if start >= total:
            break
    return hits


def save_json(obj, name):
    path = RAW / name
    path.write_text(json.dumps(obj, indent=1))
    print(f"Saved {len(obj)} records -> {path}")
