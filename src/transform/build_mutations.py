from pathlib import Path
import json

import pandas as pd

RAW = Path("data/raw")
MAF_DIR = RAW / "maf"
OUT = Path("data/processed")

COLS = {
    "Hugo_Symbol": "hugo_symbol",
    "Chromosome": "chromosome",
    "Start_Position": "start_position",
    "End_Position": "end_position",
    "Variant_Classification": "variant_classification",
    "Variant_Type": "variant_type",
    "Reference_Allele": "ref_allele",
    "Tumor_Seq_Allele2": "tumor_allele",
    "HGVSp_Short": "hgvsp_short",
}


def main():
    files = sorted(json.loads((RAW / "mutation_files.json").read_text()),
                   key=lambda h: h["file_id"])
    spec_df = pd.read_csv(OUT / "specimen.csv")
    specimen = set(spec_df["sample_barcode"])

    profiles, mutation_parts, rejects = [], [], []
    seen_samples, profile_id = set(), 0

    for h in files:
        fid, name = h["file_id"], h["file_name"]

        def reject(reason):
            rejects.append({"gdc_file_id": fid, "file_name": name, "reason": reason})

        path = MAF_DIR / f"{fid}.maf.gz"
        if not path.exists():
            reject("file not downloaded")
            continue

        df = pd.read_csv(path, sep="\t", comment="#", dtype=str,
                         compression="gzip", low_memory=False,
                         usecols=lambda c: c in COLS or c == "Tumor_Sample_Barcode")
        if df.empty:
            reject("no mutation rows in file")
            continue

        df["sample_barcode"] = (df["Tumor_Sample_Barcode"]
                                .str.split("-").str[:4].str.join("-"))
        samples = df["sample_barcode"].unique()
        if len(samples) != 1:
            reject("several tumor samples in one file")
            continue
        sample = samples[0]
        if sample not in specimen:
            reject("sample not in specimen table")
            continue
        if sample in seen_samples:
            reject("sample already loaded from another file")
            continue

        seen_samples.add(sample)
        profile_id += 1
        profiles.append({
            "profile_id": profile_id,
            "sample_barcode": sample,
            "assay_type": "mutation",
            "gdc_file_id": fid,
            "file_name": name,
            "workflow": (h.get("analysis") or {}).get("workflow_type"),
        })
        part = df.rename(columns=COLS)[["sample_barcode"] + list(COLS.values())].copy()
        part.insert(0, "profile_id", profile_id)
        mutation_parts.append(part)

    prof = pd.DataFrame(profiles)
    mut = pd.concat(mutation_parts, ignore_index=True)
    mut = mut[mut["hugo_symbol"].notna()]

    prof.to_csv(OUT / "molecular_profile.csv", index=False)
    mut.to_csv(OUT / "mutation.csv", index=False)
    pd.DataFrame(rejects, columns=["gdc_file_id", "file_name", "reason"]
                 ).to_csv(OUT / "mutation_file_rejects.csv", index=False)

    # ---------- Summary ----------
    patient_of = dict(zip(spec_df["sample_barcode"], spec_df["patient_barcode"]))
    mut["patient_barcode"] = mut["sample_barcode"].map(patient_of)

    print("== Row counts ==")
    print("Input files:", len(files))
    print("molecular_profile:", len(prof), "| rejected files:", len(rejects))
    print("mutation rows:", len(mut))
    print("Patients with mutation data:", mut["patient_barcode"].nunique())

    if rejects:
        print("\n== Rejected files by reason ==")
        print(pd.DataFrame(rejects)["reason"].value_counts().to_string())

    print("\n== Mutations per sample ==")
    print(mut.groupby("sample_barcode").size().describe().round(1).to_string())

    print("\n== Variant classifications ==")
    print(mut["variant_classification"].value_counts().head(8).to_string())

    print("\n== Top 10 genes by patients mutated ==")
    print(mut.groupby("hugo_symbol")["patient_barcode"].nunique()
          .sort_values(ascending=False).head(10).to_string())

    print("\n== Missing values ==")
    print(mut[list(COLS.values())].isna().sum().to_string())


if __name__ == "__main__":
    main()
