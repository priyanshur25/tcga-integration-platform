import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from src.load.db import get_engine

REPORT = Path("reports/qc_report.md")

# (id, severity, description, SQL returning the number of violating rows)
CHECKS = [
    # ---------- errors: must be zero ----------
    ("E1", "error", "Specimen barcode does not start with its patient barcode",
     "SELECT count(*) FROM specimen WHERE left(sample_barcode, 12) <> patient_barcode"),
    ("E2", "error", "Sample-type code does not match characters 14-15 of the barcode",
     "SELECT count(*) FROM specimen "
     "WHERE substring(sample_barcode from 14 for 2) <> sample_type_code"),
    ("E3", "error", "Slide id does not match the patient and sample type of its specimen",
     "SELECT count(*) FROM slide s JOIN specimen sp USING (sample_barcode) "
     "WHERE left(s.slide_id, 15) <> left(sp.sample_barcode, 15)"),
    ("E4", "error", "Mutation sample differs from the sample of its molecular profile",
     "SELECT count(*) FROM mutation m JOIN molecular_profile p USING (profile_id) "
     "WHERE m.sample_barcode <> p.sample_barcode"),
    ("E5", "error", "Outcome event does not agree with patient vital status",
     "SELECT count(*) FROM outcome o JOIN patient p USING (patient_barcode) "
     "WHERE (o.os_event = 1) <> (p.vital_status = 'Dead')"),
    ("E6", "error", "Patient with diagnoses does not have exactly one index diagnosis",
     "SELECT count(*) FROM (SELECT patient_barcode FROM diagnosis GROUP BY 1 "
     "HAVING sum(is_index_diagnosis::int) <> 1) t"),
    ("E7", "error", "Mutation end position is before its start position",
     "SELECT count(*) FROM mutation WHERE end_position < start_position"),
    ("E8", "error", "Mutation chromosome is not in the form chr1..chr22, chrX, chrY, chrM",
     "SELECT count(*) FROM mutation "
     "WHERE coalesce(chromosome, '') !~ '^chr([0-9]+|X|Y|M)$'"),
    ("E9", "error", "Sample with more than one mutation profile",
     "SELECT count(*) FROM (SELECT sample_barcode FROM molecular_profile "
     "WHERE assay_type = 'mutation' GROUP BY 1 HAVING count(*) > 1) t"),
    # ---------- warnings: known limitations ----------
    ("W1", "warning", "Patients with no survival outcome",
     "SELECT count(*) FROM patient p WHERE NOT EXISTS "
     "(SELECT 1 FROM outcome o WHERE o.patient_barcode = p.patient_barcode)"),
    ("W2", "warning", "Patients with no tumor specimen",
     "SELECT count(*) FROM patient p WHERE NOT EXISTS "
     "(SELECT 1 FROM specimen sp JOIN ref_sample_type r ON r.code = sp.sample_type_code "
     "WHERE sp.patient_barcode = p.patient_barcode AND r.is_tumor)"),
    ("W3", "warning", "Index diagnoses with missing stage",
     "SELECT count(*) FROM diagnosis WHERE is_index_diagnosis "
     "AND ajcc_pathologic_stage IS NULL"),
    ("W4", "warning", "Index diagnoses with missing histology",
     "SELECT count(*) FROM diagnosis WHERE is_index_diagnosis "
     "AND primary_diagnosis IS NULL"),
    ("W5", "warning", "Patients with no mutation data",
     "SELECT count(*) FROM patient p WHERE NOT EXISTS "
     "(SELECT 1 FROM specimen sp JOIN mutation m ON m.sample_barcode = sp.sample_barcode "
     "WHERE sp.patient_barcode = p.patient_barcode)"),
    ("W6", "warning", "Surplus duplicate mutation rows (same sample, gene, position, allele)",
     "SELECT coalesce(sum(n - 1), 0)::int FROM (SELECT count(*) AS n FROM mutation "
     "GROUP BY sample_barcode, hugo_symbol, chromosome, start_position, tumor_allele "
     "HAVING count(*) > 1) t"),
    # ---------- info: coverage ----------
    ("I1", "info", "Slides not yet quality-checked (qc_status = 'unchecked')",
     "SELECT count(*) FROM slide WHERE qc_status = 'unchecked'"),
    ("I2", "info", "Index diagnoses with no ER status recorded",
     "SELECT count(*) FROM diagnosis WHERE is_index_diagnosis AND er_status IS NULL"),
]


def main():
    engine = get_engine()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows, failed = [], False

    with engine.begin() as conn:
        totals = {
            t: conn.execute(text(f"SELECT count(*) FROM {t}")).scalar()
            for t in ["patient", "outcome", "specimen", "slide",
                      "molecular_profile", "mutation"]
        }
        for cid, sev, desc, sql in CHECKS:
            n = conn.execute(text(sql)).scalar()
            if sev == "info":
                status = "INFO"
            elif n == 0:
                status = "PASS"
            else:
                status = "FAIL" if sev == "error" else "WARN"
            failed = failed or status == "FAIL"
            rows.append((cid, sev, status, n, desc))
            conn.execute(
                text("INSERT INTO ingestion_log (step, source, rows_in, status, message) "
                     "VALUES ('validate', :src, :n, :st, :msg)"),
                {"src": cid, "n": n, "st": status.lower(), "msg": desc},
            )

    # ---- terminal output ----
    print(f"{'id':<4}{'status':<7}{'count':>7}  description")
    for cid, sev, status, n, desc in rows:
        print(f"{cid:<4}{status:<7}{n:>7}  {desc}")

    # ---- markdown report ----
    lines = [
        "# Data quality report",
        "",
        f"Generated: {now}",
        "",
        "## Table sizes",
        "",
        "| Table | Rows |",
        "|---|---|",
    ]
    lines += [f"| {t} | {n:,} |" for t, n in totals.items()]
    lines += [
        "",
        "## Validation results",
        "",
        "Each rule counts the rows that violate it. Errors must be zero; "
        "warnings are known data limitations; info rows describe coverage.",
        "",
        "| ID | Status | Violations | Rule |",
        "|---|---|---|---|",
    ]
    lines += [f"| {cid} | {st} | {n:,} | {desc} |" for cid, _, st, n, desc in rows]
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n")
    print(f"\nReport written to {REPORT}")

    if failed:
        print("\nOne or more ERROR rules failed.")
        sys.exit(1)
    print("\nAll error rules passed.")


if __name__ == "__main__":
    main()
