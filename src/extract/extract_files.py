from collections import Counter

from src.extract.gdc import PROJECT_FILTER, and_filter, fetch_all, in_filter, save_json

FILE_FIELDS = [
    "file_id",
    "file_name",
    "file_size",
    "data_type",
    "data_format",
    "experimental_strategy",
    "access",
    "analysis.workflow_type",
    "cases.submitter_id",
    "cases.samples.submitter_id",
    "cases.samples.sample_type",
    "cases.samples.portions.slides.submitter_id",
]

if __name__ == "__main__":
    # Slide images (metadata only, no downloading)
    print("Fetching slide image file records...")
    slides = fetch_all(
        "files",
        and_filter(PROJECT_FILTER, in_filter("data_type", ["Slide Image"])),
        FILE_FIELDS,
        sort="file_id",
    )
    save_json(slides, "slide_files.json")

    # Open-access somatic mutation files (listed only)
    print("\nFetching mutation file records...")
    muts = fetch_all(
        "files",
        and_filter(
            PROJECT_FILTER,
            in_filter("data_type", ["Masked Somatic Mutation"]),
            in_filter("access", ["open"]),
        ),
        FILE_FIELDS,
        sort="file_id",
    )
    save_json(muts, "mutation_files.json")

    # Summaries
    print("\n== Slide summary ==")
    print("Slide files:", len(slides))
    print("Unique cases with slides:", len({h["cases"][0]["submitter_id"] for h in slides}))
    kinds = Counter(h["file_name"].split(".")[0].split("-")[-1][:2] for h in slides)
    print("Slide kinds (by name suffix):", dict(kinds))
    print("Total size (GB):", round(sum(h["file_size"] for h in slides) / 1e9, 1))

    print("\n== Mutation file summary ==")
    print("Mutation files:", len(muts))
    print("Unique cases:", len({h["cases"][0]["submitter_id"] for h in muts}))
    print("Workflows:", dict(Counter(h.get("analysis", {}).get("workflow_type") for h in muts)))
    print("Total size (MB):", round(sum(h["file_size"] for h in muts) / 1e6, 1))
