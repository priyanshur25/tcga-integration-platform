import json
from pathlib import Path

import pandas as pd

RAW = Path("data/raw")
OUT = Path("data/processed")
OUT.mkdir(parents=True, exist_ok=True)

MISSING = {
    "", "not reported", "unknown", "not allowed to collect",
    "'--", "--", "na", "n/a", "nan", "none",
}


def clean_text(value):
    """Return a stripped string, or None for placeholder values."""
    if value is None:
        return None
    s = str(value).strip()
    return None if s.lower() in MISSING else s


def to_int(value):
    """Return an int, or None if missing/non-numeric."""
    try:
        if value is None:
            return None
        f = float(value)
        return None if pd.isna(f) else int(f)
    except (TypeError, ValueError):
        return None


def clean_lower(value):
    s = clean_text(value)
    return s.lower() if s else None


def clean_vital(value):
    s = clean_lower(value)
    return {"alive": "Alive", "dead": "Dead"}.get(s)


def clean_stage(value):
    """'Stage IIA' / 'stage iia' -> 'Stage IIA'; 'Stage X' -> None."""
    s = clean_text(value)
    if s is None:
        return None
    s = s.upper().replace("STAGE", "").strip()
    if s in ("", "X"):
        return None
    return f"Stage {s}"


def main():
    cases = json.loads((RAW / "cases.json").read_text())

    patients, diagnoses, treatments, outcomes, rejects = [], [], [], [], []
    seen, duplicates, dx_id = set(), 0, 0

    for c in cases:
        barcode = c["submitter_id"]
        if barcode in seen:
            duplicates += 1
            continue
        seen.add(barcode)

        demo = c.get("demographic") or {}
        vital = clean_vital(demo.get("vital_status"))

        patients.append({
            "patient_barcode": barcode,
            "gdc_case_id": c.get("case_id"),
            "project_id": (c.get("project") or {}).get("project_id"),
            "gender": clean_lower(demo.get("gender")),
            "race": clean_lower(demo.get("race")),
            "ethnicity": clean_lower(demo.get("ethnicity")),
            "vital_status": vital,
        })

        dxs = c.get("diagnoses") or []
        for dx in dxs:
            dx_id += 1
            age = to_int(dx.get("age_at_diagnosis"))
            diagnoses.append({
                "diagnosis_id": dx_id,
                "patient_barcode": barcode,
                "primary_diagnosis": clean_text(dx.get("primary_diagnosis")),
                "ajcc_pathologic_stage": clean_stage(dx.get("ajcc_pathologic_stage")),
                "age_at_diagnosis_days": age if age is not None and age >= 0 else None,
            })
            for t in dx.get("treatments") or []:
                t_type = clean_text(t.get("treatment_type"))
                t_agent = clean_text(t.get("therapeutic_agents"))
                if t_type is None and t_agent is None:
                    continue  # nothing useful recorded
                treatments.append({
                    "diagnosis_id": dx_id,
                    "treatment_type": t_type,
                    "therapeutic_agent": t_agent,
                    "days_to_start": to_int(t.get("days_to_treatment_start")),
                })

        # ---- Outcome: time + event with censoring ----
        days_death = to_int(demo.get("days_to_death"))
        follow_vals = [to_int(d.get("days_to_last_follow_up")) for d in dxs]
        follow_vals = [v for v in follow_vals if v is not None]
        days_follow = max(follow_vals) if follow_vals else None

        reason, time, event = None, None, None
        if vital == "Dead":
            time, event = days_death, 1
            if time is None:
                reason = "dead but days_to_death missing"
        elif vital == "Alive":
            time, event = days_follow, 0
            if time is None:
                reason = "alive but days_to_last_follow_up missing"
        else:
            reason = "vital_status missing"

        if reason is None and time < 0:
            reason = "negative survival time"

        if reason:
            rejects.append({"patient_barcode": barcode, "reason": reason})
        else:
            outcomes.append({
                "patient_barcode": barcode,
                "os_time_days": time,
                "os_event": event,
                "source_note": "days_to_death" if event == 1 else "days_to_last_follow_up",
            })

    tables = {
        "patient": pd.DataFrame(patients),
        "diagnosis": pd.DataFrame(diagnoses),
        "treatment": pd.DataFrame(treatments),
        "outcome": pd.DataFrame(outcomes),
        "outcome_rejects": pd.DataFrame(rejects, columns=["patient_barcode", "reason"]),
    }
    for name, df in tables.items():
        df.to_csv(OUT / f"{name}.csv", index=False)

    # ---- Summary ----
    print("== Row counts ==")
    print("Input cases:", len(cases), "| duplicate barcodes skipped:", duplicates)
    for name, df in tables.items():
        print(f"{name:<16} {len(df)}")

    print("\n== Vital status ==")
    print(tables["patient"]["vital_status"].value_counts(dropna=False).to_string())
    print("\n== Stage ==")
    print(tables["diagnosis"]["ajcc_pathologic_stage"].value_counts(dropna=False).to_string())
    print("\n== Top diagnoses ==")
    print(tables["diagnosis"]["primary_diagnosis"].value_counts(dropna=False).head(6).to_string())
    print("\n== Outcome events (1 = died, 0 = censored) ==")
    print(tables["outcome"]["os_event"].value_counts().to_string())
    print("\n== Outcome rejects by reason ==")
    print(tables["outcome_rejects"]["reason"].value_counts().to_string()
          if len(rejects) else "none")
    print("\n== Treatment types ==")
    print(tables["treatment"]["treatment_type"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
