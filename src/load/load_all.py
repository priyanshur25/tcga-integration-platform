import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID

from src.load.db import get_engine

PROC = Path("data/processed")

# Load order matters: parents before children.
# (table, csv, text-only columns, nullable-int columns, uuid columns)
TABLES = [
    ("patient",           "patient.csv",           [],                   [],                                     ["gdc_case_id"]),
    ("diagnosis",         "diagnosis.csv",         [],                   ["age_at_diagnosis_days"],              []),
    ("treatment",         "treatment.csv",         [],                   ["days_to_start"],                      []),
    ("outcome",           "outcome.csv",           [],                   ["os_time_days"],                       []),
    ("specimen",          "specimen.csv",          ["sample_type_code"], [],                                     ["gdc_sample_id"]),
    ("slide",             "slide.csv",             [],                   ["file_size_bytes"],                    ["gdc_file_id"]),
    ("molecular_profile", "molecular_profile.csv", [],                   [],                                     ["gdc_file_id"]),
    ("mutation",          "mutation.csv",          [],                   ["start_position", "end_position"],     []),
]


def load_table(conn, table, csv, str_cols, int_cols, uuid_cols):
    # Only empty cells become NULL; text such as "NA" or "None" is kept as is.
    df = pd.read_csv(
        PROC / csv,
        dtype={c: str for c in str_cols},
        keep_default_na=False,
        na_values=[""],
    )
    for c in int_cols:
        df[c] = df[c].astype("Int64")
    dtype = {c: UUID(as_uuid=False) for c in uuid_cols}
    df.to_sql(table, conn, if_exists="append", index=False,
              dtype=dtype, method="multi", chunksize=500)
    return len(df)


def scalar(conn, sql):
    return conn.execute(text(sql)).scalar()


def main():
    dx_cols = pd.read_csv(PROC / "diagnosis.csv", nrows=1).columns
    if "is_index_diagnosis" not in dx_cols:
        sys.exit("diagnosis.csv has no is_index_diagnosis column. "
                 "Finish the Step 6 patch and re-run clean_clinical first.")

    engine = get_engine()
    results = []
    with engine.begin() as conn:  # one transaction: all or nothing
        conn.execute(text("TRUNCATE TABLE patient CASCADE"))
        for table, csv, s, i, u in TABLES:
            print(f"loading {table} ...", flush=True)
            n_csv = load_table(conn, table, csv, s, i, u)
            n_db = scalar(conn, f"SELECT count(*) FROM {table}")
            status = "ok" if n_csv == n_db else "MISMATCH"
            conn.execute(
                text("INSERT INTO ingestion_log (step, source, rows_in, rows_out, status) "
                     "VALUES ('load', :src, :a, :b, :st)"),
                {"src": csv, "a": n_csv, "b": n_db, "st": status},
            )
            results.append((table, n_csv, n_db, status))

        # ids were inserted explicitly, so move the serial sequences past them
        for tbl, col in [("diagnosis", "diagnosis_id"),
                         ("molecular_profile", "profile_id")]:
            conn.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{tbl}', '{col}'), "
                f"(SELECT max({col}) FROM {tbl}))"))

    print("\n== Load results ==")
    print(f"{'table':<20}{'csv rows':>10}{'db rows':>10}  status")
    for t, a, b, st in results:
        print(f"{t:<20}{a:>10}{b:>10}  {st}")

    with engine.connect() as conn:
        print("\n== Chain check: patient -> specimen -> slide (tumor samples only) ==")
        print("Patients with a tumor specimen that has a slide:", scalar(conn, """
            SELECT count(DISTINCT sp.patient_barcode)
            FROM specimen sp
            JOIN ref_sample_type r ON r.code = sp.sample_type_code
            JOIN slide s ON s.sample_barcode = sp.sample_barcode
            WHERE r.is_tumor"""))

        print("\n== Chain check: index diagnosis -> outcome, by stage ==")
        rows = conn.execute(text("""
            SELECT coalesce(d.ajcc_pathologic_stage, 'missing') AS stage,
                   count(*) AS patients,
                   sum(o.os_event) AS deaths
            FROM diagnosis d
            JOIN outcome o USING (patient_barcode)
            WHERE d.is_index_diagnosis
            GROUP BY 1 ORDER BY 1""")).fetchall()
        print(f"{'stage':<14}{'patients':>9}{'deaths':>8}")
        for stage, p, dth in rows:
            print(f"{stage:<14}{p:>9}{dth:>8}")

        print("\n== Chain check: mutation -> specimen -> patient ==")
        print("Patients with at least one mutation:", scalar(conn, """
            SELECT count(DISTINCT sp.patient_barcode)
            FROM mutation m JOIN specimen sp USING (sample_barcode)"""))
        print("Patients with outcome + slide + mutation:", scalar(conn, """
            SELECT count(*) FROM outcome o
            WHERE EXISTS (
                SELECT 1 FROM slide s JOIN specimen sp USING (sample_barcode)
                WHERE sp.patient_barcode = o.patient_barcode)
            AND EXISTS (
                SELECT 1 FROM mutation m JOIN specimen sp USING (sample_barcode)
                WHERE sp.patient_barcode = o.patient_barcode)"""))

        print("\n== Top 5 mutated genes (patients) ==")
        for gene, n in conn.execute(text("""
            SELECT m.hugo_symbol, count(DISTINCT sp.patient_barcode) AS n
            FROM mutation m JOIN specimen sp USING (sample_barcode)
            GROUP BY 1 ORDER BY 2 DESC LIMIT 5""")).fetchall():
            print(f"{gene:<10}{n:>6}")

        print("\n== First cohort query ==")
        print("PIK3CA-mutated (non-silent) patients with an outcome and a slide:",
              scalar(conn, """
            SELECT count(DISTINCT sp.patient_barcode)
            FROM mutation m
            JOIN specimen sp ON sp.sample_barcode = m.sample_barcode
            JOIN outcome o ON o.patient_barcode = sp.patient_barcode
            WHERE m.hugo_symbol = 'PIK3CA'
              AND m.variant_classification <> 'Silent'
              AND EXISTS (
                  SELECT 1 FROM slide s
                  JOIN specimen sp2 ON sp2.sample_barcode = s.sample_barcode
                  WHERE sp2.patient_barcode = sp.patient_barcode)"""))


if __name__ == "__main__":
    main()
