#!/usr/bin/env python3
"""
One-time (but re-runnable) migration: converts the v0.1-v0.4 flat,
one-entry-per-company dataset shape into the v0.5 company-centric shape
with an array-based `sustainability_sources` field, per
schema/sustainability_sources.schema.json.

WHY THIS IS A REAL MIGRATION, NOT A BOLT-ON
The old shape stored exactly one source per company, spread across two
files joined by company_name:
  - eu_sustainability_reports.csv   (company_name, country, sector, hq_city,
    sustainability_page_url, gri_referenced, report_year, universal_standards,
    topic_standards_200/300/400, externally_assured, verification_status,
    source_method)
  - all_487_report_sources.csv      (company_name, country, report_title,
    source_pdf_url, additional_source_urls, notes, source_type)

The new shape nests a `sustainability_sources` array under each company, so a
company can carry a current downloadable_report AND an agr_section AND a
webpage entry simultaneously, plus is_legacy:true entries for older years.
This script performs a structural conversion (one company object per row,
with a first sustainability_sources[0] entry built from the old manifest
row) rather than just appending new fields to the old flat rows.

WHAT GETS DROPPED / FOLDED (read before running on your own fork)
The new schema (as specified) has no top-level slot for hq_city or for the
old report_year / universal_standards / topic_standards_* / externally_assured
/ verification_status / source_method fields. In this run:
  - universal_standards, topic_standards_200/300/400, externally_assured,
    report_year were EMPTY for 100% of the 487 rows (verification hadn't run
    yet), so nothing is actually lost by dropping those columns.
  - hq_city IS populated for every row, so it is preserved by prefixing it
    into the new entry's `notes` field ("HQ: <city>. <original notes>")
    rather than being silently discarded.
  - gri_referenced is DELIBERATELY NOT auto-promoted into frameworks_referenced,
    even though it's 'Y' for 484/487 (99.4%) of rows. That field only ever
    meant "selected because it's known to publish sustainability content
    referencing GRI" - it was never independently verified per-company
    (verification_status is 'unverified - pending manual review' dataset-wide).
    Promoting it wholesale would make frameworks_referenced look like a
    confirmed-per-entry signal when it isn't. Instead, frameworks_referenced
    is populated ONLY from explicit keyword hits in the actual report_title
    / notes text (grounded in real research findings), and gri_referenced=='Y'
    with no such hit is preserved as a soft, clearly-hedged note instead:
    "Believed to reference GRI Standards (unverified)."
  - verification_status / source_method were near-identical boilerplate
    across almost all 487 rows ("unverified - pending manual review" /
    "direct company sourcing") and are NOT repeated in every entry's notes;
    instead this fact is recorded once, globally, in MIGRATION_NOTES.md.
  - additional_source_urls (when present) is appended to `notes` as
    "Additional sources: <urls>", since the new schema doesn't have a
    dedicated multi-URL field per entry.

SOURCE_TYPE MAPPING (old -> new)
  - old source_type == 'downloadable_pdf':
      -> 'agr_section' if report_title/notes indicate the sustainability
         content is embedded inside a broader Annual Report / Management
         Report / Report and Accounts (heuristic keyword match - see
         AGR_TITLE_SIGNALS below). parent_document_url is set to the old
         source_pdf_url, since that PDF *is* the annual report containing
         the section.
      -> 'downloadable_report' otherwise (a standalone sustainability/ESG
         report PDF). report_url is set to the old source_pdf_url.
  - old source_type == 'webpage_landing_page':
      -> 'webpage'. source_url is set to the old source_pdf_url (which held
         the landing-page URL under the old schema's overloaded field name).

FIELDS THIS MIGRATION CANNOT BACKFILL (left null, flagged for follow-up)
  - archive_url: no real Wayback Machine snapshots were taken during data
    collection. Every migrated webpage entry has archive_url = null. See
    tools/archive_snapshot.py for a follow-up script that captures/records
    a snapshot per webpage entry (not run automatically here - it makes
    live requests to web.archive.org and should be rate-limited/reviewed).
  - retrieved_date: the exact date each webpage was checked wasn't recorded
    per-row during the original research (spread across several sessions).
    Left null rather than fabricated. New submissions going forward MUST
    populate retrieved_date (enforced by validate_submission.py).
  - publication_date: not reliably extractable from the old notes/title
    text at scale; left null. reporting_year is best-effort extracted from
    report_title/notes via a 4-digit-year regex instead.

USAGE
    python3 migrate_to_sources_schema.py
Reads eu_sustainability_reports.csv + all_487_report_sources.csv from the
same folder, writes eu_sustainability_sources_v5.json (a JSON array of
company objects) and prints a migration summary + any warnings.
"""

import csv
import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATASET_CSV = BASE_DIR / "eu_sustainability_reports.csv"
MANIFEST_CSV = BASE_DIR / "all_487_report_sources.csv"
OUT_JSON = BASE_DIR / "eu_sustainability_sources_v5.json"

FRAMEWORK_PATTERNS = [
    (re.compile(r"\bGRI\b"), "GRI"),
    (re.compile(r"\bCSRD\b|\bESRS\b"), "CSRD"),
    (re.compile(r"\bTCFD\b"), "TCFD"),
    (re.compile(r"\bTNFD\b"), "TNFD"),
    (re.compile(r"\bIFRS[\s\-]?S1\b"), "IFRS_S1"),
    (re.compile(r"\bIFRS[\s\-]?S2\b"), "IFRS_S2"),
]

AGR_TITLE_SIGNALS = [
    "annual report", "management report", "report and accounts",
    "administrators' report", "administrators report", "integrated annual report",
    "consolidated annual", "combined management report", "board of directors' report",
    "annual activity report", "consolidated management report",
]

YEAR_RE = re.compile(r"\b(20(?:1[5-9]|2[0-6]))\b")


def slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"&", " and ", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "company"


def make_unique_id(base: str, used: dict) -> str:
    if base not in used:
        used[base] = 1
        return base
    used[base] += 1
    return f"{base}-{used[base]}"


def detect_frameworks(*texts) -> list:
    joined = " ".join(t for t in texts if t)
    found = []
    for pattern, label in FRAMEWORK_PATTERNS:
        if pattern.search(joined) and label not in found:
            found.append(label)
    return found


def extract_year(*texts) -> str:
    for t in texts:
        if not t:
            continue
        m = YEAR_RE.search(t)
        if m:
            return m.group(1)
    return None


def looks_like_agr_section(report_title: str, notes: str) -> bool:
    haystack = f"{report_title or ''} {notes or ''}".lower()
    return any(sig in haystack for sig in AGR_TITLE_SIGNALS)


def build_notes(hq_city: str, manifest_notes: str, additional_source_urls: str,
                 gri_believed_but_unconfirmed: bool = False) -> str:
    parts = []
    if hq_city:
        parts.append(f"HQ: {hq_city}.")
    if manifest_notes:
        parts.append(manifest_notes.strip())
    if additional_source_urls:
        parts.append(f"Additional sources: {additional_source_urls.strip()}")
    if gri_believed_but_unconfirmed:
        parts.append("Believed to reference GRI Standards (unverified).")
    text = " ".join(p for p in parts if p).strip()
    return text or None


def main():
    if not DATASET_CSV.exists():
        sys.exit(f"Missing {DATASET_CSV.name}")
    if not MANIFEST_CSV.exists():
        sys.exit(f"Missing {MANIFEST_CSV.name}")

    with open(DATASET_CSV, newline="", encoding="utf-8") as f:
        dataset_rows = list(csv.DictReader(f))
    with open(MANIFEST_CSV, newline="", encoding="utf-8") as f:
        manifest_rows = list(csv.DictReader(f))

    manifest_by_name = {r["company_name"]: r for r in manifest_rows}

    print(f"Dataset rows:  {len(dataset_rows)}")
    print(f"Manifest rows: {len(manifest_rows)}")

    unmatched = [r["company_name"] for r in dataset_rows if r["company_name"] not in manifest_by_name]
    if unmatched:
        print(f"WARNING: {len(unmatched)} dataset companies have no manifest row - skipping their source entry:")
        for n in unmatched[:20]:
            print(f"    - {n}")

    used_ids = {}
    companies = []
    agr_classified = 0
    downloadable_classified = 0
    webpage_classified = 0
    frameworks_detected_count = 0

    for row in dataset_rows:
        name = row["company_name"]
        company_id = make_unique_id(slugify(name), used_ids)

        manifest = manifest_by_name.get(name)
        sources = []

        if manifest:
            old_type = manifest.get("source_type", "").strip()
            report_title = manifest.get("report_title") or None
            source_pdf_url = manifest.get("source_pdf_url") or None
            manifest_notes = manifest.get("notes") or None
            additional_urls = manifest.get("additional_source_urls") or None

            frameworks = detect_frameworks(report_title, manifest_notes)
            gri_believed_but_unconfirmed = (
                row.get("gri_referenced", "").strip().upper() == "Y" and "GRI" not in frameworks
            )
            notes = build_notes(row.get("hq_city"), manifest_notes, additional_urls,
                                 gri_believed_but_unconfirmed)
            if frameworks:
                frameworks_detected_count += 1
            reporting_year = extract_year(report_title, manifest_notes)

            entry_id = f"{company_id}-001"

            if old_type == "webpage_landing_page":
                entry = {
                    "entry_id": entry_id,
                    "source_type": "webpage",
                    "reporting_year": reporting_year,
                    "publication_date": None,
                    "report_url": None,
                    "report_title": None,
                    "source_url": source_pdf_url,
                    "retrieved_date": None,
                    "archive_url": None,
                    "parent_document_type": None,
                    "parent_document_url": None,
                    "section_reference": None,
                    "frameworks_referenced": frameworks,
                    "is_legacy": False,
                    "notes": notes,
                }
                webpage_classified += 1

            elif old_type == "downloadable_pdf" and looks_like_agr_section(report_title, manifest_notes):
                entry = {
                    "entry_id": entry_id,
                    "source_type": "agr_section",
                    "reporting_year": reporting_year,
                    "publication_date": None,
                    "report_url": None,
                    "report_title": None,
                    "source_url": None,
                    "retrieved_date": None,
                    "archive_url": None,
                    "parent_document_type": "annual_general_report",
                    "parent_document_url": source_pdf_url,
                    "section_reference": report_title,
                    "frameworks_referenced": frameworks,
                    "is_legacy": False,
                    "notes": notes,
                }
                agr_classified += 1

            else:
                entry = {
                    "entry_id": entry_id,
                    "source_type": "downloadable_report",
                    "reporting_year": reporting_year,
                    "publication_date": None,
                    "report_url": source_pdf_url,
                    "report_title": report_title,
                    "source_url": None,
                    "retrieved_date": None,
                    "archive_url": None,
                    "parent_document_type": None,
                    "parent_document_url": None,
                    "section_reference": None,
                    "frameworks_referenced": frameworks,
                    "is_legacy": False,
                    "notes": notes,
                }
                downloadable_classified += 1

            sources.append(entry)

        company = {
            "company_id": company_id,
            "company_name": name,
            "country": row["country"],
            "sector": row["sector"],
            "sustainability_sources": sources,
        }
        companies.append(company)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(companies, f, indent=2, ensure_ascii=False)

    no_source = [c["company_name"] for c in companies if not c["sustainability_sources"]]

    print("\n--- Migration summary ---")
    print(f"Companies migrated:              {len(companies)}")
    print(f"  -> downloadable_report entries: {downloadable_classified}")
    print(f"  -> agr_section entries:         {agr_classified}")
    print(f"  -> webpage entries:             {webpage_classified}")
    print(f"Entries with >=1 detected framework: {frameworks_detected_count}")
    print(f"Companies with NO source entry:  {len(no_source)}")
    if no_source:
        for n in no_source[:20]:
            print(f"    - {n}")
    print(f"\nWrote {OUT_JSON.name}")


if __name__ == "__main__":
    main()
