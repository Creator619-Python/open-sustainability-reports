# Contributing

## Submitting a new sustainability source (the main way to contribute)

As of v0.5, the dataset (`eu_sustainability_sources_v5.json`) supports
multiple source entries per company - a company can have a current
downloadable report, a sustainability section embedded in its Annual Report,
and/or a webpage source, plus older entries kept around for progress
tracking. New sources are added through a **propose-then-review** flow,
similar in spirit to editing a Wikipedia article: you don't write directly
into the live dataset file; you propose a change, an automated check looks
at its shape, and a human reviewer looks at its substance before it's merged.

### 1. Propose

1. Fork the repo.
2. Copy `submissions/TEMPLATE.json` to
   `submissions/pending/sub-YYYY-MM-DD-NNNN.json` (use today's date and a
   sequence number - if you're not sure what NNNN to use, `0001` is fine,
   the exact number doesn't need to be globally unique across all
   contributors, just unique against other files you're adding in the same PR).
3. Fill it in:
   - `target.target_company_id`: the company's existing `company_id` in
     `eu_sustainability_sources_v5.json` (search for the company by name to
     find it), if you're adding a source to a company already in the
     dataset. Leave `target.new_company` as `null`.
   - OR `target.new_company`: `{company_name, country, sector}` if the
     company isn't in the dataset yet. Leave `target.target_company_id` as
     `null`.
   - `target.supersedes_entry_id`: set this to an existing entry's
     `entry_id` if your new entry should become the current one for that
     source_type (e.g. this year's report replacing last year's). The old
     entry isn't deleted - it gets flipped to `is_legacy: true` so the
     dataset keeps a history, not just a snapshot.
   - `entry`: the actual source data. See "Which fields to fill in" below.
     Set `entry.entry_id` to your `submission_id` as a placeholder - a
     maintainer assigns the real id when merging.
   - `review`: leave exactly as the template has it (`status: "pending"`,
     everything else `null`/empty). This block is for reviewers, not you.
4. Delete the `_comment` keys (they're just inline instructions, not part of
   the real schema).
5. Open a PR. CI (`validate-submissions.yml`) runs `validate_submission.py`
   automatically and will fail the check if your JSON doesn't validate,
   references a company/entry_id that doesn't exist, or is missing a
   required URL for your `source_type`. Fix and push again until it's green.

### Which fields to fill in, by `source_type`

| source_type | Fill in | Leave null |
|---|---|---|
| `downloadable_report` | `report_url`, `report_title` | `source_url`, `retrieved_date`, `archive_url`, `parent_document_type`, `parent_document_url`, `section_reference` |
| `webpage` | `source_url`, `retrieved_date` (today's date), `archive_url` (see below) | `report_url`, `report_title`, `parent_document_type`, `parent_document_url`, `section_reference` |
| `agr_section` | `parent_document_type` (currently always `"annual_general_report"`), `parent_document_url`, `section_reference` (a page range like `"pp. 45-78"` or a section name like `"Sustainability Statement"`) | `report_url`, `report_title`, `source_url`, `archive_url` |

**`archive_url` for webpage entries:** before submitting, save a snapshot at
[web.archive.org/save](https://web.archive.org/save) (paste the page URL,
click "Save Page") and use the resulting `https://web.archive.org/web/.../...`
URL. This is what keeps the citation alive if the company reorganizes its
site later - don't skip it for webpage entries if you can help it.

**`frameworks_referenced`:** only list a framework (`GRI`, `CSRD`, `TCFD`,
`TNFD`, `IFRS_S1`, `IFRS_S2`) if the source text itself actually says so -
don't infer it from "this is a big company, it probably follows GRI." If
you're not sure, leave the array empty and mention what you noticed in
`notes` instead (e.g. `"Report mentions 'ESRS' but I couldn't confirm a
CSRD-compliant statement"`). Overclaiming a framework is worse than an
empty array - it's the kind of thing that erodes trust in the whole dataset.

### 2. Review (maintainers)

A submission is ready to merge once a reviewer has:

- [ ] **Opened the URL and confirmed it resolves and actually contains what
  the entry claims** (`checklist.url_resolves_and_matches_claim`). This is
  the one check CI deliberately does not automate - a script fetching every
  submitted URL is both an abuse surface and no substitute for a human
  actually reading the document.
- [ ] **Checked there isn't already a conflicting or duplicate entry**
  (`checklist.no_duplicate_or_conflicting_entry`) - including checking
  `submissions/pending/` for other open submissions targeting the same
  company (CI flags likely duplicates as a warning, but doesn't block on
  it).
- [ ] **Confirmed `frameworks_referenced` is grounded in the actual source
  text**, not guessed (`checklist.frameworks_referenced_grounded_in_source_text`).
- [ ] **Confirmed the right field group is filled in for the `source_type`**
  (`checklist.source_type_field_group_correct`) - CI enforces the schema
  shape but a human should sanity-check e.g. that a `downloadable_report`
  isn't actually just a landing page that should be `webpage`.
- [ ] **Confirmed `is_legacy`/`supersedes_entry_id` is handled correctly**
  (`checklist.is_legacy_and_supersedes_handled_correctly`) - if this is
  meant to replace an existing entry, `supersedes_entry_id` should be set;
  if it's a genuinely new, additional source (e.g. a webpage alongside an
  existing downloadable report), it shouldn't be.
- [ ] **Checked for company name collisions** (`checklist.no_name_collision_risk_or_flagged_in_notes`)
  - see the "Name collisions" note below. This dataset has already hit this
    (Banco BPI vs Bank of the Philippine Islands, Posta Slovenije vs
    Slovenska posta, Graphisoft Park SE vs Graphisoft SE, and others) -
    check the target company's country/sector actually match before
    assuming a search result is the right entity.

Once all six are checked, set `review.status` to `"approved"` and fill in
`reviewed_by` / `reviewed_date` / `reviewer_notes`, then merge the PR.

**If something needs fixing:** set `review.status` to `"changes_requested"`
and leave specific feedback in `reviewer_notes` - don't just close the PR.

**If it shouldn't be added at all:** set `review.status` to `"rejected"`
with a reason in `reviewer_notes`, for the record, then close the PR without
merging.

### 3. Merge (maintainers)

After an approved submission's PR lands on `main`, run:

```bash
python3 merge_submissions.py
git add eu_sustainability_sources_v5.json submissions/archive/
git commit -m "Merge approved submission: <short description>"
git push
```

`merge_submissions.py` refuses to merge anything that isn't
`review.status: "approved"` with `reviewed_by`/`reviewed_date` filled in -
it will not merge a submission just because it's sitting in
`submissions/pending/`. Use `--dry-run` first if you want to preview what
it'll do without writing anything.

### Name collisions

Before approving a submission (new or existing company), search the dataset
for similarly-named entities. This dataset already tracks several real
collisions in `notes` fields - similar company names across different
countries/industries are common enough that this is a routine check, not an
edge case: Metro AG vs Metro Inc; Colt CZ Group vs Colt Technology Services;
Banco BPI (Portugal) vs Bank of the Philippine Islands; Posta Slovenije vs
Slovenska posta; Graphisoft Park SE vs Graphisoft SE (the Nemetschek-owned
software company); U.S. Steel Kosice vs its US-listed parent. If you're
even slightly unsure, add a note flagging the ambiguity rather than silently
picking one.

---

## Other ways to contribute

- **Fixing an existing entry** (wrong URL, typo, wrong `source_type`, etc.):
  same submission flow as above, with `target.supersedes_entry_id` set to
  the entry you're correcting.
- **Verifying report-level fields** (`report_year`, GRI standards tagging,
  assurance status): still pending automation via `gemini_gri_extractor.py`
  - see `ROADMAP.md`.
- **Code/tooling changes** (schema, scripts, CI): open a normal PR against
  the relevant `.py`/`.json`/`.yml` file directly - the submission flow above
  is specifically for dataset content, not tooling.
