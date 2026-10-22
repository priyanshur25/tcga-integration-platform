from collections import Counter

from src.extract.gdc import PROJECT_FILTER, fetch_all, save_json

FIELDS = [
    "case_id",
    "submitter_id",
    "project.project_id",
    # patient-level
    "demographic.gender",
    "demographic.race",
    "demographic.ethnicity",
    "demographic.vital_status",
    "demographic.days_to_death",
    "demographic.age_at_index",
    # diagnosis-level
    "diagnoses.primary_diagnosis",
    "diagnoses.ajcc_pathologic_stage",
    "diagnoses.age_at_diagnosis",
    "diagnoses.days_to_last_follow_up",
    # treatments
    "diagnoses.treatments.treatment_type",
    "diagnoses.treatments.therapeutic_agents",
    "diagnoses.treatments.days_to_treatment_start",
    # samples and slides
    "samples.submitter_id",
    "samples.sample_id",
    "samples.sample_type",
    "samples.portions.slides.submitter_id",
    "samples.portions.slides.slide_id",
]

if __name__ == "__main__":
    print("Fetching cases...")
    cases = fetch_all("cases", PROJECT_FILTER, FIELDS, sort="submitter_id")
    save_json(cases, "cases.json")

    # Quick sanity summary
    n_samples = sum(len(c.get("samples", [])) for c in cases)
    n_slides = sum(
        len(p.get("slides", []))
        for c in cases
        for s in c.get("samples", [])
        for p in s.get("portions", [])
    )
    vitals = Counter(c.get("demographic", {}).get("vital_status") for c in cases)
    with_death = sum(
        1 for c in cases if c.get("demographic", {}).get("days_to_death") is not None
    )
    n_dx = Counter(len(c.get("diagnoses", [])) for c in cases)

    print("\n== Summary ==")
    print("Cases:", len(cases))
    print("Unique patient barcodes:", len({c["submitter_id"] for c in cases}))
    print("Samples:", n_samples, "| Slides listed in case records:", n_slides)
    print("Vital status:", dict(vitals))
    print("Cases with days_to_death:", with_death)
    print("Diagnoses per case:", dict(n_dx))
