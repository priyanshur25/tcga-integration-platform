import json

import requests

from src.extract.gdc import GDC, PROJECT_FILTER, and_filter, in_filter

filters = and_filter(PROJECT_FILTER, in_filter("demographic.vital_status", ["alive"]))
payload = {
    "filters": filters,
    "expand": "follow_ups,diagnoses",
    "size": 3,
    "sort": "submitter_id",
}
r = requests.post(f"{GDC}/cases", json=payload, timeout=120)
r.raise_for_status()
hits = r.json()["data"]["hits"]


def day_fields(record):
    """Keep only keys that mention 'days' and have a value."""
    return {k: v for k, v in record.items() if "days" in k and v is not None}


for c in hits:
    print("\n==", c["submitter_id"])
    for d in c.get("diagnoses", []):
        print("  diagnosis day fields:", day_fields(d))
    fus = c.get("follow_ups", [])
    print("  follow_up records:", len(fus))
    for f in fus[:3]:
        print("  follow_up day fields:", day_fields(f))

print("\nAll keys in one follow_up record:")
for c in hits:
    if c.get("follow_ups"):
        print(sorted(c["follow_ups"][0].keys()))
        break
