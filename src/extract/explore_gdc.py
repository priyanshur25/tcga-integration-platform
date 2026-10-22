import json
from pathlib import Path

import requests

GDC = "https://api.gdc.cancer.gov"
PROJECT = "TCGA-BRCA"
RAW = Path("data/raw")
RAW.mkdir(parents=True, exist_ok=True)

SAMPLE_TYPES = {
    "01": "Primary Solid Tumor",
    "02": "Recurrent Solid Tumor",
    "06": "Metastatic",
    "10": "Blood Derived Normal",
    "11": "Solid Tissue Normal",
}

project_filter = {
    "op": "in",
    "content": {"field": "cases.project.project_id", "value": [PROJECT]},
}


def post(endpoint, payload):
    r = requests.post(f"{GDC}/{endpoint}", json=payload, timeout=120)
    r.raise_for_status()
    return r.json()["data"]


def parse_barcode(barcode):
    """Split a TCGA barcode into its hierarchy levels."""
    parts = barcode.split("-")
    out = {
        "project": parts[0],
        "tissue_source_site": parts[1],
        "patient_barcode": "-".join(parts[:3]),
    }
    if len(parts) >= 4:
        out["sample_barcode"] = "-".join(parts[:4])
        out["sample_type_code"] = parts[3][:2]
        out["sample_type"] = SAMPLE_TYPES.get(parts[3][:2], "Other")
        out["vial"] = parts[3][2:]
    return out


# 1. Project summary
r = requests.get(
    f"{GDC}/projects/{PROJECT}", params={"expand": "summary"}, timeout=60
)
r.raise_for_status()
summary = r.json()["data"]["summary"]
print(f"== {PROJECT} summary ==")
print("Cases:", summary["case_count"], "| Files:", summary["file_count"])

# 2. What kinds of data exist for this project?
data = post(
    "files",
    {
        "filters": project_filter,
        "facets": "data_category,data_type,experimental_strategy",
        "size": 0,
    },
)
for facet in ["data_category", "data_type", "experimental_strategy"]:
    print(f"\n== Files by {facet} ==")
    for b in data["aggregations"][facet]["buckets"]:
        print(f"{b['key']:<45} {b['doc_count']}")

# 3. A few clinical case records
cases = post(
    "cases",
    {
        "filters": project_filter,
        "fields": ",".join(
            [
                "submitter_id",
                "demographic.gender",
                "demographic.vital_status",
                "demographic.days_to_death",
                "diagnoses.primary_diagnosis",
                "diagnoses.ajcc_pathologic_stage",
                "diagnoses.days_to_last_follow_up",
            ]
        ),
        "size": 5,
    },
)
print("\n== Sample case records ==")
print(json.dumps(cases["hits"][:2], indent=2))
(RAW / "sample_cases.json").write_text(json.dumps(cases["hits"], indent=2))

# 4. A few slide image records
slides = post(
    "files",
    {
        "filters": {
            "op": "and",
            "content": [
                project_filter,
                {
                    "op": "in",
                    "content": {"field": "data_type", "value": ["Slide Image"]},
                },
            ],
        },
        "fields": "file_name,file_size,experimental_strategy,"
        "cases.submitter_id,cases.samples.submitter_id,"
        "cases.samples.sample_type",
        "size": 5,
    },
)
print("\n== Sample slide records ==")
print(json.dumps(slides["hits"][:2], indent=2))
(RAW / "sample_slides.json").write_text(json.dumps(slides["hits"], indent=2))

# 5. Barcode parsing demo
print("\n== Barcode parsing demo ==")
for bc in [
    "TCGA-A1-A0SB-01A-11R-A144-07",
    "TCGA-A1-A0SB-11A-01D-A142-09",
]:
    print(bc, "->", parse_barcode(bc))
