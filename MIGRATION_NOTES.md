# Migration notes: v0.4 (flat) -> v0.5 (array-based sustainability_sources)

This is a **breaking change** to the dataset shape. If you have code reading
`eu_sustainability_reports.csv` / `.json` or `all_487_report_sources.csv`
directly, it will need to be updated to read `eu_sustainability_sources_v5.json`
instead - the old files are kept for reference but are no longer the source
of truth going forward.

## Why

The old shape stored exactly one source per company. In reality a company
often has more than one legitimate current source at once (e.g. a
downloadable ESG report AND a sustainability section inside its Annual
Report), plus older reports worth keeping for progress-tracking rather than
overwriting each year. The old shape couldn't represent either case. See the
schema for the full rationale: `schema/sustainability_sources.schema.json`.

## Old shape (two files, joined by company_name)

```
eu_sustainability_reports.csv:
  company_name, country, sector, hq_city, sustainability_page_url,
  gri_referenced, report_year, universal_standards, topic_standards_200,
  topic_standards_300, topic_standards_400, externally_assured,
  verification_status, source_method

all_487_report_sources.csv:
  company_name, country, report_title, source_pdf_url,
  additional_source_urls, notes, source_type   (source_type: downloadable_pdf | webpage_landing_page)
```

## New shape (one file, one object per company)

```
eu_sustainability_sources_v5.json:
  [{ company_id, company_name, country, sector,
     sustainability_sources: [{ entry_id, source_type, reporting_year,
       publication_date, report_url, report_title, source_url,
       retrieved_date, archive_url, parent_document_type,
       parent_document_url, section_reference, frameworks_referenced,
       is_legacy, notes }] }]
```

Full field-level definitions and conditional rules (which fields are
populated for which `source_type`) live in
`schema/sustainability_sources.schema.json`.

## How the migration ran

`migrate_to_sources_schema.py` was run once, across the **full** 487-company
dataset (not a sample), producing `eu_sustainability_sources_v5.json`. Result:

- **487/487 companies migrated**, each with exactly one `sustainability_sources`
  entry (the one source that existed for them under the old schema). Zero
  companies ended up with no entry.
- **168** classified as `downloadable_report`, **211** as `agr_section`,
  **108** as `webpage` (mapping logic below).
- **0 schema violations** against `schema/sustainability_sources.schema.json`
  (validated with `jsonschema` Draft 2020-12).
- **0 duplicate `company_id`s**, **0 duplicate `entry_id`s**.

### source_type mapping (old -> new)

| Old `source_type` | New `source_type` | Rule |
|---|---|---|
| `downloadable_pdf` | `agr_section` | if `report_title`/`notes` mention "Annual Report", "Management Report", "Report and Accounts", "Combined Management Report", etc. (the sustainability content is embedded in a broader annual filing, not a standalone report) |
| `downloadable_pdf` | `downloadable_report` | otherwise (a standalone sustainability/ESG report PDF) |
| `webpage_landing_page` | `webpage` | always |

This is a text-keyword heuristic, not a guarantee - it's right in the
overwhelming majority of cases because `report_title` was written
descriptively during original data collection (e.g. titles literally
containing "part of the Combined Management Report"), but a handful of
entries may be misclassified. **Submissions correcting a misclassified
`source_type` are welcome** via the normal submission flow (see
`CONTRIBUTING.md`) - set `target.supersedes_entry_id` to the entry being
corrected.

## What was preserved vs. dropped vs. folded

| Old field | What happened |
|---|---|
| `company_name`, `country`, `sector` | Preserved directly. |
| `hq_city` | **No slot in the new schema.** Preserved by prefixing into the entry's `notes` field as `"HQ: <city>. ..."` rather than silently dropped. |
| `sustainability_page_url` / `source_pdf_url` | Mapped to `report_url` / `source_url` / `parent_document_url` depending on the new `source_type`. |
| `report_title` | Preserved for `downloadable_report`; repurposed as `section_reference` for `agr_section` (since the old title text like "X Sustainability Statement (part of Combined Management Report)" doubles as a description of where in the parent document to look). |
| `notes` | Preserved into the new `notes` field (with `hq_city` and, where relevant, `additional_source_urls` and a GRI hedge note prefixed/appended - see below). |
| `additional_source_urls` | No dedicated field in the new schema (each entry has one URL, matching its `source_type`). Folded into `notes` as `"Additional sources: <urls>"` when present, rather than dropped. |
| `gri_referenced` (Y for 484/487 rows, 99.4%) | **Deliberately NOT auto-promoted into `frameworks_referenced`.** This field only ever meant "selected because it's known to publish GRI-adjacent content" - never independently verified per company (`verification_status` was `unverified - pending manual review` dataset-wide). Auto-promoting it would have made `frameworks_referenced` look like a confirmed per-entry signal for ~all 487 companies, which isn't true. Instead: `frameworks_referenced` is populated *only* from explicit keyword hits (`GRI`, `CSRD`/`ESRS`, `TCFD`, `TNFD`, `IFRS S1`, `IFRS S2`) found in the actual `report_title`/`notes` text - **238/487 (49%)** entries got at least one framework this way. Where `gri_referenced` was `Y` but no keyword hit occurred, the entry's `notes` instead gets an honest, hedged line: `"Believed to reference GRI Standards (unverified)."` |
| `report_year`, `universal_standards`, `topic_standards_200/300/400`, `externally_assured` | Empty/unpopulated for **100% of the 487 rows** (Gemini verification hadn't been run yet) - dropping these columns loses nothing real. `reporting_year` in the new schema is instead best-effort auto-extracted via a 4-digit-year regex over `report_title`/`notes`. |
| `verification_status`, `source_method` | Both were near-identical boilerplate across almost all 487 rows (`"unverified - pending manual review"` / `"direct company sourcing"`). Not repeated in every entry's `notes` (that would have been 487x noise for near-zero information); instead recorded once, here, as a dataset-wide fact: **as of v0.5, every migrated entry's `report_year`/`universal_standards`/`topic_standards_*`/`externally_assured` equivalent is still unverified**, and every entry's original source was direct company/public sourcing (not yet Gemini-verified). |

## What this migration could NOT backfill (left `null`, flagged for follow-up)

- **`archive_url`** - no real Wayback Machine snapshots were taken during
  the original research; every migrated `webpage` entry has `archive_url:
  null`. A follow-up `tools/archive_snapshot.py` (not built yet) could walk
  all `webpage` entries and request/record a snapshot per URL - deliberately
  not run automatically here since it makes live outbound requests to
  web.archive.org at volume (108 URLs) and should be rate-limited and
  reviewed, not fired blind from a migration script.
- **`retrieved_date`** - the exact date each webpage was checked wasn't
  recorded per-row during the original multi-session research, so it's left
  `null` rather than fabricated with a fake uniform date. **New submissions
  going forward must populate this field** (enforced structurally, though
  not content-checked, by the schema requiring the key to be present).
- **`publication_date`** - not reliably extractable from the old free-text
  `notes`/`report_title` at scale; left `null`. Use `reporting_year`
  (auto-extracted) as an approximation in the meantime.

## Re-running the migration

The migration script is idempotent and safe to re-run - it always reads
fresh from `eu_sustainability_reports.csv` + `all_487_report_sources.csv`
and overwrites `eu_sustainability_sources_v5.json` from scratch:

```bash
python3 migrate_to_sources_schema.py
```

Note: re-running it **after** submissions have been merged via
`merge_submissions.py` will discard those merges (it regenerates from the
old flat files, which don't know about submissions). Once v0.5 is the
system of record, this migration script should only be re-run if the old
flat files are regenerated from some upstream process - normal ongoing
updates should go through the submission flow instead (see
`CONTRIBUTING.md`), not by re-running this migration.
