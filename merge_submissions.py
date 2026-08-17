#!/usr/bin/env python3
"""
Maintainer-only step: folds APPROVED submissions from submissions/pending/
into eu_sustainability_sources_v5.json, then moves the submission file to
submissions/archive/ (kept, not deleted, so there's a permanent audit trail
of who submitted what and who approved it - same reasoning as keeping
superseded entries as is_legacy:true instead of deleting them).

This script deliberately refuses to touch anything whose review.status is
not exactly "approved" - it will not merge "pending" or "changes_requested"
submissions even if you point it at them directly, and it will not merge
anything if reviewed_by / reviewed_date are empty. A human has to have
actually filled in the review block (see CONTRIBUTING.md) for this to do
anything. This is the enforcement point for "review before merge" - CI's
validate_submission.py checks shape/consistency, but only a human can flip
review.status to "approved", and only this script (run by a maintainer,
usually right after merging the reviewed PR) commits that approval into the
live dataset.

WHAT IT DOES, per approved submission:
1. Determine the target company:
   - existing company (target.target_company_id) - looked up in the current
     dataset.
   - new company (target.new_company) - a new company object is created
     with an empty sustainability_sources list, using the same slugify /
     collision-avoidance logic as migrate_to_sources_schema.py so ids stay
     consistent across both tools.
2. Assign the entry a real entry_id: "<company_id>-<NNN>", continuing that
   company's existing sequence (does not reuse or renumber existing ids).
3. If target.supersedes_entry_id is set, flip that existing entry's
   is_legacy to true (it is NOT deleted - full history stays queryable).
4. Append the new entry to that company's sustainability_sources array.
5. Move the submission file to submissions/archive/.

USAGE
    python3 merge_submissions.py                 # merges every "approved" file in submissions/pending/
    python3 merge_submissions.py --dry-run        # prints what would happen, writes nothing
    python3 merge_submissions.py path/to/one.json # merge a single specific file
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATASET_JSON = BASE_DIR / "eu_sustainability_sources_v5.json"
PENDING_DIR = BASE_DIR / "submissions" / "pending"
ARCHIVE_DIR = BASE_DIR / "submissions" / "archive"


def slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"&", " and ", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "company"


def next_entry_id(company: dict) -> str:
    existing = company["sustainability_sources"]
    max_n = 0
    for s in existing:
        m = re.match(rf"^{re.escape(company['company_id'])}-(\d{{3,}})$", s["entry_id"])
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"{company['company_id']}-{max_n + 1:03d}"


def find_or_create_company(companies_by_id: dict, all_company_ids: set, target: dict) -> dict:
    if target.get("target_company_id"):
        cid = target["target_company_id"]
        company = companies_by_id.get(cid)
        if company is None:
            raise ValueError(f"target_company_id '{cid}' not found - re-run validate_submission.py first")
        return company

    nc = target["new_company"]
    base_id = slugify(nc["company_name"])
    cid = base_id
    suffix = 1
    while cid in all_company_ids:
        suffix += 1
        cid = f"{base_id}-{suffix}"
    company = {
        "company_id": cid,
        "company_name": nc["company_name"],
        "country": nc["country"],
        "sector": nc["sector"],
        "sustainability_sources": [],
    }
    companies_by_id[cid] = company
    all_company_ids.add(cid)
    return company


def merge_one(submission_path: Path, companies_by_id: dict, all_company_ids: set, dry_run: bool) -> bool:
    raw = json.loads(submission_path.read_text(encoding="utf-8"))
    review = raw.get("review", {})

    if review.get("status") != "approved":
        print(f"SKIP {submission_path.name}: review.status is "
              f"'{review.get('status')}', not 'approved'.")
        return False
    if not review.get("reviewed_by") or not review.get("reviewed_date"):
        print(f"SKIP {submission_path.name}: status is 'approved' but "
              f"reviewed_by/reviewed_date is empty - refusing to merge an "
              f"unattributed approval.")
        return False

    target = raw["target"]
    entry = dict(raw["entry"])  # copy - we'll mutate entry_id

    try:
        company = find_or_create_company(companies_by_id, all_company_ids, target)
    except ValueError as e:
        print(f"SKIP {submission_path.name}: {e}")
        return False

    new_entry_id = next_entry_id(company)
    old_entry_id = entry["entry_id"]
    entry["entry_id"] = new_entry_id

    supersedes = target.get("supersedes_entry_id")
    flipped = None
    if supersedes:
        for s in company["sustainability_sources"]:
            if s["entry_id"] == supersedes:
                s["is_legacy"] = True
                flipped = supersedes
                break
        if flipped is None:
            print(f"SKIP {submission_path.name}: supersedes_entry_id '{supersedes}' "
                  f"not found on company '{company['company_id']}' - aborting this merge "
                  f"so we don't silently lose the supersession relationship.")
            return False

    print(f"MERGE {submission_path.name}: company='{company['company_id']}', "
          f"new entry_id='{new_entry_id}' (was placeholder '{old_entry_id}'), "
          f"source_type='{entry['source_type']}'"
          + (f", superseded '{flipped}'" if flipped else "")
          + (" [DRY RUN - not written]" if dry_run else ""))

    if not dry_run:
        company["sustainability_sources"].append(entry)
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        shutil.move(str(submission_path), str(ARCHIVE_DIR / submission_path.name))

    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", help="Specific submission file(s) to merge. Defaults to all of submissions/pending/*.json.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not DATASET_JSON.exists():
        sys.exit(f"Missing {DATASET_JSON.name} - run migrate_to_sources_schema.py first.")

    companies = json.loads(DATASET_JSON.read_text(encoding="utf-8"))
    companies_by_id = {c["company_id"]: c for c in companies}
    all_company_ids = set(companies_by_id.keys())

    if args.files:
        files = [Path(f) for f in args.files]
    else:
        files = sorted(PENDING_DIR.glob("*.json")) if PENDING_DIR.exists() else []
        files = [f for f in files if f.name != "TEMPLATE.json"]

    if not files:
        print("No submission files found to merge.")
        return

    merged_count = 0
    for f in files:
        if merge_one(f, companies_by_id, all_company_ids, args.dry_run):
            merged_count += 1

    if not args.dry_run and merged_count:
        # companies list may have grown (new companies appended)
        companies_out = list(companies_by_id.values())
        DATASET_JSON.write_text(json.dumps(companies_out, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nWrote {DATASET_JSON.name} ({len(companies_out)} companies total).")

    print(f"\n{merged_count} submission(s) merged" + (" (dry run, nothing written)." if args.dry_run else "."))


if __name__ == "__main__":
    main()
