#!/usr/bin/env python3
"""
Automated first-pass check for community submissions - the equivalent of a
Wikipedia edit filter / bot check that runs BEFORE a human reviewer looks at
anything. It does not approve submissions (only a human sets
review.status = "approved"); it just catches malformed/incomplete/conflicting
submissions early so reviewers spend their time on judgment calls, not typo
hunting.

Runs automatically in CI (.github/workflows/validate-submissions.yml) on any
PR that touches submissions/pending/*.json, and can be run locally too:

    pip install jsonschema referencing --break-system-packages
    python3 validate_submission.py                       # validates every file in submissions/pending/
    python3 validate_submission.py submissions/pending/sub-2026-08-21-0007.json   # validates one file

CHECKS PERFORMED
1. Schema validity against schema/submission.schema.json (which itself
   references schema/sustainability_sources.schema.json's sourceEntry
   definition for the nested `entry` object).
2. target_company_id (if set) actually exists in
   eu_sustainability_sources_v5.json - catches typos'd company ids.
3. supersedes_entry_id (if set) actually exists on the target company -
   catches references to entries that don't exist or belong to a different
   company.
4. entry_id collision: the placeholder entry_id must not already collide
   with a real, already-merged entry_id in the live dataset (a genuine
   collision here usually means the submission was copy-pasted from an
   existing entry instead of using the submission_id placeholder).
5. Duplicate-submission heuristic: warns (does not fail) if another PENDING
   submission already targets the same company with the same source_type
   and reporting_year - a likely duplicate that a reviewer should look at
   before approving both.
6. Basic URL well-formedness for whichever URL field the source_type
   requires (report_url / source_url / parent_document_url) - syntax only,
   this script does NOT fetch the URL. Reviewers are expected to actually
   open the link and confirm it resolves and matches the claim (see
   checklist.url_resolves_and_matches_claim in CONTRIBUTING.md) - that's a
   human judgment step CI cannot safely automate (fetching arbitrary
   submitted URLs from CI is also a mild SSRF/abuse surface, so this script
   deliberately does not do it).

EXIT CODE
0 if every checked file passes hard checks (warnings don't affect exit code).
1 if any file fails a hard check - CI uses this to block the PR from being
mergeable until fixed, mirroring how a failing edit filter blocks a
Wikipedia save.
"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    import jsonschema
    from referencing import Registry, Resource
except ImportError:
    sys.exit(
        "Missing dependencies. Run:\n"
        "  pip install jsonschema referencing --break-system-packages"
    )

BASE_DIR = Path(__file__).parent
SCHEMA_DIR = BASE_DIR / "schema"
PENDING_DIR = BASE_DIR / "submissions" / "pending"
DATASET_JSON = BASE_DIR / "eu_sustainability_sources_v5.json"

SUBMISSION_ID_RE = re.compile(r"^sub-\d{4}-\d{2}-\d{2}-\d{4}$")

URL_FIELD_BY_SOURCE_TYPE = {
    "downloadable_report": "report_url",
    "webpage": "source_url",
    "agr_section": "parent_document_url",
}


def load_validator():
    src_schema = json.loads((SCHEMA_DIR / "sustainability_sources.schema.json").read_text(encoding="utf-8"))
    sub_schema = json.loads((SCHEMA_DIR / "submission.schema.json").read_text(encoding="utf-8"))
    registry = Registry().with_resources([
        (src_schema["$id"], Resource.from_contents(src_schema)),
        (sub_schema["$id"], Resource.from_contents(sub_schema)),
    ])
    return jsonschema.Draft202012Validator(sub_schema, registry=registry)


def strip_comment_keys(obj):
    """Recursively remove '_comment' keys left over from TEMPLATE.json, with a note."""
    stripped_any = False
    if isinstance(obj, dict):
        for k in list(obj.keys()):
            if k == "_comment":
                del obj[k]
                stripped_any = True
            else:
                if strip_comment_keys(obj[k]):
                    stripped_any = True
    elif isinstance(obj, list):
        for item in obj:
            if strip_comment_keys(item):
                stripped_any = True
    return stripped_any


def is_well_formed_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def load_dataset():
    if not DATASET_JSON.exists():
        return {}
    companies = json.loads(DATASET_JSON.read_text(encoding="utf-8"))
    return {c["company_id"]: c for c in companies}


def validate_file(path: Path, validator, dataset_by_id, pending_index) -> bool:
    """Returns True if the file passes all hard checks."""
    print(f"\n=== {path.relative_to(BASE_DIR)} ===")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"  FAIL: not valid JSON ({e})")
        return False

    if strip_comment_keys(raw):
        print("  NOTE: found and ignored leftover '_comment' key(s) from TEMPLATE.json - "
              "remove these before submitting for real.")

    ok = True

    # 1. Schema validity
    errs = sorted(validator.iter_errors(raw), key=lambda e: list(e.path))
    if errs:
        ok = False
        print(f"  FAIL: {len(errs)} schema violation(s):")
        for e in errs:
            loc = "/".join(str(p) for p in e.path) or "(root)"
            print(f"    - at {loc}: {e.message}")
        # Can't safely run the rest of the checks against a non-conforming shape.
        return False

    submission_id = raw["submission_id"]
    if not SUBMISSION_ID_RE.match(submission_id):
        ok = False
        print(f"  FAIL: submission_id '{submission_id}' doesn't match pattern sub-YYYY-MM-DD-NNNN")

    target = raw["target"]
    entry = raw["entry"]

    # 2/3. target_company_id / supersedes_entry_id existence checks
    target_company = None
    if target.get("target_company_id"):
        cid = target["target_company_id"]
        target_company = dataset_by_id.get(cid)
        if target_company is None:
            ok = False
            print(f"  FAIL: target_company_id '{cid}' does not exist in eu_sustainability_sources_v5.json "
                  f"(check for typos, or use new_company instead if this is a genuinely new company)")
        else:
            existing_entry_ids = {s["entry_id"] for s in target_company["sustainability_sources"]}
            supersedes = target.get("supersedes_entry_id")
            if supersedes and supersedes not in existing_entry_ids:
                ok = False
                print(f"  FAIL: supersedes_entry_id '{supersedes}' does not belong to company "
                      f"'{cid}' (existing entry_ids: {sorted(existing_entry_ids)})")
    elif target.get("new_company"):
        nc = target["new_company"]
        print(f"  INFO: proposing a NEW company '{nc['company_name']}' ({nc['country']}) - "
              f"reviewer should double-check it isn't already in the dataset under a slightly "
              f"different name before approving (see CONTRIBUTING.md name-collision guidance).")
    else:
        ok = False
        print("  FAIL: target must set either target_company_id or new_company (schema should "
              "have caught this - if you're seeing this, the schema and this check disagree, please "
              "file an issue)")

    # 4. entry_id collision against already-merged entries
    if target_company is not None:
        placeholder_id = entry["entry_id"]
        collision = any(s["entry_id"] == placeholder_id for s in target_company["sustainability_sources"])
        if collision and placeholder_id != submission_id:
            ok = False
            print(f"  FAIL: entry.entry_id '{placeholder_id}' collides with an existing merged entry. "
                  f"Set entry.entry_id to this submission's submission_id as a placeholder instead - "
                  f"merge_submissions.py assigns the real id.")
        elif entry["entry_id"] != submission_id:
            print(f"  WARN: entry.entry_id ('{entry['entry_id']}') doesn't match submission_id "
                  f"('{submission_id}'). This still validates, but the convention is to use the "
                  f"submission_id as the placeholder so it's obviously provisional.")

    # 5. Duplicate-submission heuristic (warning only)
    key = (target.get("target_company_id") or f"NEW:{(target.get('new_company') or {}).get('company_name')}",
           entry["source_type"], entry.get("reporting_year"))
    if key in pending_index and pending_index[key] != submission_id:
        print(f"  WARN: another pending submission ({pending_index[key]}) already proposes a "
              f"{entry['source_type']} entry for the same company/reporting_year. Reviewer should "
              f"check these aren't duplicates before approving both.")
    else:
        pending_index[key] = submission_id

    # 6. URL well-formedness for the field this source_type requires
    url_field = URL_FIELD_BY_SOURCE_TYPE[entry["source_type"]]
    url_value = entry.get(url_field)
    if not url_value or not is_well_formed_url(url_value):
        ok = False
        print(f"  FAIL: entry.{url_field} is required for source_type='{entry['source_type']}' "
              f"and must be a well-formed http(s) URL, got: {url_value!r}")

    if ok:
        print("  PASS (hard checks). Remember: a human reviewer still needs to open the URL, "
              "confirm it matches the claim, and complete the review.checklist before setting "
              "review.status to 'approved'.")
    return ok


def main():
    args = sys.argv[1:]
    if args:
        files = [Path(a) for a in args]
    else:
        if not PENDING_DIR.exists():
            sys.exit(f"No {PENDING_DIR} directory found.")
        files = sorted(PENDING_DIR.glob("*.json"))
        files = [f for f in files if f.name != "TEMPLATE.json"]

    if not files:
        print("No submission files to validate.")
        return

    validator = load_validator()
    dataset_by_id = load_dataset()
    if not dataset_by_id:
        print(f"WARNING: {DATASET_JSON.name} not found or empty - skipping "
              f"target_company_id/supersedes_entry_id existence checks.")

    pending_index = {}
    all_ok = True
    for f in files:
        if not validate_file(f, validator, dataset_by_id, pending_index):
            all_ok = False

    print(f"\n{'='*60}")
    print(f"{sum(1 for _ in files)} file(s) checked. {'ALL PASSED' if all_ok else 'SOME FAILED'}.")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
