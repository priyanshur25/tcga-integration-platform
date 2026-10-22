import json
from pathlib import Path

import pandas as pd

cases = {
    c["submitter_id"]: c
    for c in json.loads(Path("data/raw/cases.json").read_text())
}

# ---- 1. The rejected patients ----
rej = pd.read_csv("data/processed/outcome_rejects.csv")
print("== Rejected patients ==")
for _, row in rej.iterrows():
    c = cases[row["patient_barcode"]]
    demo = c.get("demographic") or {}
    print("\n", row["patient_barcode"], "|", row["reason"])
    print("   vital:", demo.get("vital_status"),
          "| days_to_death:", demo.get("days_to_death"))
    print("   diagnosis follow-ups:",
          [d.get("days_to_last_follow_up") for d in c.get("diagnoses") or []])
    print("   follow_ups:",
          [f.get("days_to_follow_up") for f in c.get("follow_ups") or []])

# ---- 2. Patients with several diagnosis records ----
def key(d):
    return (d.get("primary_diagnosis"), d.get("ajcc_pathologic_stage"),
            d.get("age_at_diagnosis"))

multi = {k: c for k, c in cases.items() if len(c.get("diagnoses") or []) > 1}
identical = sum(1 for c in multi.values()
                if len({key(d) for d in c["diagnoses"]}) == 1)

print("\n== Patients with more than one diagnosis record ==")
print("Total:", len(multi))
print("All records identical (diagnosis, stage, age):", identical)
print("Records differ:", len(multi) - identical)

shown = 0
for k, c in multi.items():
    if len({key(d) for d in c["diagnoses"]}) > 1 and shown < 3:
        shown += 1
        print("\n", k)
        for d in c["diagnoses"]:
            print("   ", key(d))
