#!/usr/bin/env python3
"""
One-time helper: folds your existing eu_sustainability_reports_filled.csv (from
whatever Gemini run you've already done - 98, 202, 311, or partway through 487) into
the current eu_sustainability_reports.csv, so gemini_gri_extractor.py can resume
and only process the newly-added companies.

WHEN TO RUN THIS
Run it once, after your current Gemini run has produced (or is partway through
producing) eu_sustainability_reports_filled.csv, and before you resume the script
against an updated, larger eu_sustainability_reports.csv.

WHAT IT DOES
- Reads your existing eu_sustainability_reports_filled.csv (some rows verified,
  some "unable to verify", some "error - retry needed", some still blank).
- Reads the current eu_sustainability_reports.csv (now 487 rows across all 27 EU
  countries, following four expansion rounds: 98 -> 202 -> 311 -> 487).
- For every company that appears in both files, keeps YOUR existing result (so
  nothing you've already verified gets lost or re-queried).
- For newly-added companies, keeps the blank "unverified - pending manual review"
  row so the extractor script will process them on the next run.
- Writes the result to eu_sustainability_reports_filled.csv (overwriting the old
  version) so gemini_gri_extractor.py picks it up automatically as its resume file.

USAGE
1. Put this script in the same folder as your eu_sustainability_reports_filled.csv,
   the current eu_sustainability_reports.csv (487 rows), and all_487_report_sources.csv.
2. python merge_expansion.py
3. python gemini_gri_extractor.py   (resumes - only queries the newly-added companies,
   plus any old rows still marked "error - retry needed")
"""

import csv
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
OLD_FILLED = BASE_DIR / "eu_sustainability_reports_filled.csv"
NEW_BASE = BASE_DIR / "eu_sustainability_reports.csv"
OUT = BASE_DIR / "eu_sustainability_reports_filled.csv"

FIELDNAMES = [
    "company_name", "country", "sector", "hq_city", "sustainability_page_url",
    "gri_referenced", "report_year", "universal_standards",
    "topic_standards_200", "topic_standards_300", "topic_standards_400",
    "externally_assured", "verification_status", "source_method",
]


def main():
    if not NEW_BASE.exists():
        sys.exit(f"Missing {NEW_BASE.name} - get the updated 487-company file first.")

    with open(NEW_BASE, newline="", encoding="utf-8") as f:
        new_rows = list(csv.DictReader(f))
    print(f"New base dataset: {len(new_rows)} companies.")

    if not OLD_FILLED.exists():
        print(f"No existing {OLD_FILLED.name} found - nothing to merge. "
              f"You can just run gemini_gri_extractor.py directly; it will start "
              f"fresh from {NEW_BASE.name} and process all 487 companies.")
        return

    with open(OLD_FILLED, newline="", encoding="utf-8") as f:
        old_rows = {r["company_name"].strip(): r for r in csv.DictReader(f)}
    print(f"Existing filled results: {len(old_rows)} companies.")

    merged = []
    carried_over = 0
    new_blank = 0
    for row in new_rows:
        name = row["company_name"].strip()
        if name in old_rows:
            merged.append(old_rows[name])
            carried_over += 1
        else:
            merged.append(row)
            new_blank += 1

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(merged)

    print(f"Wrote {OUT.name}: {carried_over} companies carried over from your "
          f"existing results, {new_blank} new companies queued for verification.")
    print("Next: run python gemini_gri_extractor.py to resume.")


if __name__ == "__main__":
    main()
