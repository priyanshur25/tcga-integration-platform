import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from src.extract.gdc import GDC, RAW

MAF_DIR = RAW / "maf"
MAF_DIR.mkdir(parents=True, exist_ok=True)


def download(file_id):
    path = MAF_DIR / f"{file_id}.maf.gz"
    if path.exists() and path.stat().st_size > 0:
        return file_id, "cached"
    for attempt in range(3):
        try:
            r = requests.get(f"{GDC}/data/{file_id}", timeout=120)
            r.raise_for_status()
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(r.content)
            tmp.rename(path)
            return file_id, "downloaded"
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
    return file_id, "FAILED"


if __name__ == "__main__":
    files = json.loads((RAW / "mutation_files.json").read_text())
    ids = [h["file_id"] for h in files]
    print("Files to fetch:", len(ids))

    counts = {"cached": 0, "downloaded": 0, "FAILED": 0}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i, (fid, status) in enumerate(pool.map(download, ids), 1):
            counts[status] += 1
            if status == "FAILED":
                print("  failed:", fid)
            if i % 100 == 0:
                print(f"  {i}/{len(ids)}")

    print("\n", counts)
    total = sum(p.stat().st_size for p in MAF_DIR.glob("*.maf.gz"))
    print("Total size on disk (MB):", round(total / 1e6, 1))
