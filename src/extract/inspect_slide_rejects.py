import json
from pathlib import Path

import pandas as pd

files = {h["file_id"]: h for h in json.loads(Path("data/raw/slide_files.json").read_text())}
rej = pd.read_csv("data/processed/slide_rejects.csv")

for _, r in rej.iterrows():
    h = files[r["gdc_file_id"]]
    case = h["cases"][0]
    print("\n", r["file_name"].split(".")[0], "|", r["reason"])
    print("   file size:", h.get("file_size"))
    print("   slide ids in GDC record:",
          sorted({sl.get("submitter_id")
                  for s in case.get("samples") or []
                  for p in s.get("portions") or []
                  for sl in p.get("slides") or []}))

# For the duplicate: show every file that shares that slide id
dup = rej.iloc[0]["file_name"].split(".")[0]
print("\n== All files whose name starts with", dup, "==")
for h in files.values():
    if h["file_name"].startswith(dup):
        print("  ", h["file_id"], h["file_name"], h["file_size"])
