import json
import re
from pathlib import Path

import pandas as pd

RAW = Path("data/raw")
OUT = Path("data/processed")
OUT.mkdir(parents=True, exist_ok=True)

KNOWN_CODES = {"01", "02", "06", "10", "11"}  # matches ref_sample_type


def sample_code(barcode):
    parts = barcode.split("-")
    return parts[3][:2] if len(parts) >= 4 else None


def slide_kind(slide_id):
    m = re.search(r"-(DX|TS|BS|MS)[A-Z0-9]*$", slide_id or "")
    return m.group(1) if m else None


def main():
    cases = json.loads((RAW / "cases.json").read_text())
    files = json.loads((RAW / "slide_files.json").read_text())

    # ---------- Specimens ----------
    specimens, spec_rejects, seen = [], [], set()
    case_slide_ids = set()
    for c in cases:
        patient = c["submitter_id"]
        for s in c.get("samples") or []:
            barcode = s.get("submitter_id")
            for p in s.get("portions") or []:
                for sl in p.get("slides") or []:
                    if sl.get("submitter_id"):
                        case_slide_ids.add(sl["submitter_id"])
            if not barcode or barcode in seen:
                continue
            seen.add(barcode)
            code = sample_code(barcode)
            reason = None
            if not barcode.startswith(patient):
                reason = "sample barcode does not start with patient barcode"
            elif code not in KNOWN_CODES:
                reason = f"sample type code {code} not in ref_sample_type"
            if reason:
                spec_rejects.append({"sample_barcode": barcode,
                                     "patient_barcode": patient,
                                     "reason": reason})
                continue
            specimens.append({
                "sample_barcode": barcode,
                "patient_barcode": patient,
                "sample_type_code": code,
                "gdc_sample_id": s.get("sample_id"),
            })
    spec = pd.DataFrame(specimens)
    valid_samples = dict(zip(spec["sample_barcode"], spec["patient_barcode"]))

    # ---------- Slides ----------
    slides, slide_rejects, seen_slides = [], [], set()
    for h in files:
        file_id = h["file_id"]
        case = (h.get("cases") or [{}])[0]
        patient = case.get("submitter_id")
        links = []
        for s in case.get("samples") or []:
            for p in s.get("portions") or []:
                for sl in p.get("slides") or []:
                    links.append((s.get("submitter_id"), sl.get("submitter_id")))

        def reject(reason):
            slide_rejects.append({"gdc_file_id": file_id,
                                  "file_name": h.get("file_name"),
                                  "reason": reason})

        if len(links) == 0:
            reject("no sample/slide link in GDC record")
            continue
        name_id = (h.get("file_name") or "").split(".")[0]
        matched = list({l for l in links if l[1] == name_id})
        if len(matched) != 1:
            reject("file name matches no single slide in GDC record")
            continue
        sample_barcode, slide_id = matched[0]
        if not slide_id:
            reject("slide id missing")
        elif slide_id in seen_slides:
            reject("duplicate slide id")
        elif sample_barcode not in valid_samples:
            reject("sample not in specimen table")
        elif valid_samples[sample_barcode] != patient:
            reject("slide patient differs from specimen patient")
        else:
            seen_slides.add(slide_id)
            slides.append({
                "slide_id": slide_id,
                "sample_barcode": sample_barcode,
                "gdc_file_id": file_id,
                "file_name": h.get("file_name"),
                "file_size_bytes": h.get("file_size"),
                "slide_type": slide_kind(slide_id),
            })
    sl = pd.DataFrame(slides)

    # ---------- Save ----------
    spec.to_csv(OUT / "specimen.csv", index=False)
    sl.to_csv(OUT / "slide.csv", index=False)
    pd.DataFrame(spec_rejects, columns=["sample_barcode", "patient_barcode", "reason"]
                 ).to_csv(OUT / "specimen_rejects.csv", index=False)
    pd.DataFrame(slide_rejects, columns=["gdc_file_id", "file_name", "reason"]
                 ).to_csv(OUT / "slide_rejects.csv", index=False)

    # ---------- Summary ----------
    print("== Row counts ==")
    print("specimen         ", len(spec), "| rejected:", len(spec_rejects))
    print("slide            ", len(sl), "| rejected:", len(slide_rejects))

    print("\n== Specimens by sample type ==")
    print(spec["sample_type_code"].value_counts().to_string())
    print("\n== Specimens per patient ==")
    print(spec.groupby("patient_barcode").size().describe().round(1).to_string())

    print("\n== Slides by type ==")
    print(sl["slide_type"].value_counts(dropna=False).to_string())
    print("\n== Slides per specimen (specimens that have slides) ==")
    print(sl.groupby("sample_barcode").size().describe().round(1).to_string())

    if slide_rejects:
        print("\n== Slide rejects by reason ==")
        print(pd.DataFrame(slide_rejects)["reason"].value_counts().to_string())
    if spec_rejects:
        print("\n== Specimen rejects by reason ==")
        print(pd.DataFrame(spec_rejects)["reason"].value_counts().to_string())

    file_slide_ids = set(sl["slide_id"])
    print("\n== Cross-check: slides in case records vs slide files ==")
    print("In case records only:", len(case_slide_ids - file_slide_ids))
    print("In files only:", len(file_slide_ids - case_slide_ids))

    tumor = set(spec[spec["sample_type_code"].isin(["01", "02", "06"])]["sample_barcode"])
    tumor_slide_patients = {
        valid_samples[b] for b in sl["sample_barcode"] if b in tumor
    }
    print("\nPatients with a tumor sample that has a slide:", len(tumor_slide_patients))
    print("Patients with no slide at all:",
          len(set(valid_samples.values())) - len({valid_samples[b] for b in sl["sample_barcode"]}))


if __name__ == "__main__":
    main()
