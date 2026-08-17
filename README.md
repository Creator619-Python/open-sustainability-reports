# Open Sustainability Reports Database

An open, CC0-licensed catalog of corporate sustainability reports, starting with a European Union pilot batch. Modeled on [open-epd-india](https://github.com/Creator619-Python/open-epd-india).

## Why this exists

GRI's own Sustainability Disclosure Database was discontinued as an actively maintained public resource (last populated December 2020). This project sources data directly from companies instead, so it doesn't depend on a single centralized registry.

## Pilot scope (v0.5)

- **Region:** European Union
- **Companies:** 487
- **Countries:** all 27 EU member states (Austria, Belgium, Bulgaria, Croatia, Cyprus, Czech Republic, Denmark, Estonia, Finland, France, Germany, Greece, Hungary, Ireland, Italy, Latvia, Lithuania, Luxembourg, Malta, Netherlands, Poland, Portugal, Romania, Slovakia, Slovenia, Spain, Sweden)
- **Sectors:** wide-ranging free-text industry descriptions spanning technology, automotive, pharma, finance, energy, retail, telecom, defense, and more

Grew in four company-count rounds: 49 -> 98 -> 202 -> 311 -> 487 (see git
history / `MIGRATION_NOTES.md` for details), and one **data-model** round:
v0.1-v0.4 stored exactly one source per company; **v0.5 (this release)
switches to a `sustainability_sources` array per company**, so a company can
carry a current downloadable report, a sustainability section embedded in
its Annual Report, and/or a webpage source simultaneously, plus older
entries kept for progress tracking instead of being overwritten. This is a
breaking change - see `MIGRATION_NOTES.md` for the full old-schema ->
new-schema mapping and what got preserved/dropped/folded.

## Files

**Current (v0.5) - start here:**

- `eu_sustainability_sources_v5.json` — the dataset. One object per company, each with a `sustainability_sources` array. This is the source of truth going forward.
- `schema/sustainability_sources.schema.json` — JSON Schema (Draft 2020-12) formally defining the shape above, including which fields are populated for each `source_type` (`downloadable_report` / `webpage` / `agr_section`).
- `schema/submission.schema.json` — schema for community-submitted entries (see Contributing below).
- `migrate_to_sources_schema.py` — the migration script that produced `eu_sustainability_sources_v5.json` from the old flat files (re-runnable; see `MIGRATION_NOTES.md`).
- `validate_submission.py` / `merge_submissions.py` — tooling for the submission review workflow (see Contributing below).
- `MIGRATION_NOTES.md` — full breakdown of the v0.4 -> v0.5 schema migration: field-by-field mapping, what was preserved vs. dropped vs. folded, and why.

**Legacy (v0.1-v0.4, kept for reference / backward compatibility):**

- `eu_sustainability_reports.csv` / `.json` — old flat one-entry-per-company dataset.
- `all_487_report_sources.csv` — old flat per-company report source manifest.
- `gemini_gri_extractor.py` — script that reads the old manifest and uses the Gemini API to check each source document for a GRI Content Index. **Not yet updated to read the v0.5 schema** - see `ROADMAP.md`.
- `merge_expansion.py` — helper for folding a partial Gemini verification run into a newer/larger version of the old flat dataset.
- `ROADMAP.md` — planned directions (legacy/historical reports, `gemini_gri_extractor.py` v0.5 support, benchmarking).

## Schema (v0.5)

Each company:

| Field | Description |
|---|---|
| company_id | Stable slug uniquely identifying the company |
| company_name | Company name |
| country | HQ country |
| sector | Industry sector |
| sustainability_sources | Array of one or more source entries (see below) |

Each entry in `sustainability_sources`:

| Field | Description |
|---|---|
| entry_id | Stable id for this entry, unique within the company |
| source_type | `downloadable_report` \| `webpage` \| `agr_section` — determines which field group below is populated |
| reporting_year | Fiscal/reporting year this source covers |
| publication_date | Date the source was published, if known |
| report_url / report_title | Populated for `downloadable_report` only |
| source_url / retrieved_date / archive_url | Populated for `webpage` only — `archive_url` is a Wayback Machine snapshot so the citation survives if the live page changes |
| parent_document_type / parent_document_url / section_reference | Populated for `agr_section` only — the sustainability content lives inside a broader Annual General Report |
| frameworks_referenced | Flat array, e.g. `["GRI", "CSRD"]` — only populated when grounded in the actual source text, never inferred |
| is_legacy | `true` for superseded/historical entries, kept for progress tracking rather than deleted |
| notes | Free text: CSRD/ESRS migration notes, name-collision warnings, sourcing caveats, etc. |

Full formal definition (including which fields must be `null` for each
`source_type`): `schema/sustainability_sources.schema.json`.

## Status

Company names, countries, and sectors have been compiled from public sources. Framework references (`frameworks_referenced`) are populated only where the source text itself explicitly names a framework — as of this migration, **238 of 487 entries (49%)** have at least one confirmed framework tag this way; the rest are honestly left empty rather than guessed. Classification into `downloadable_report` (168), `agr_section` (211), and `webpage` (108) was done via a text-keyword heuristic during migration and may occasionally be wrong — corrections are welcome via the submission process below. See `entry.notes` for cases involving CSRD/ESRS migration, redomiciled HQs, dual-country HQs, or similarly-named unrelated companies (name-collision flags are especially common — e.g. Banco BPI vs Bank of the Philippine Islands, Posta Slovenije vs Slovenska posta, Graphisoft Park SE vs Graphisoft SE).

Report-level verification (does the report actually contain a GRI Content Index, what year, is it externally assured) is still pending automation — `gemini_gri_extractor.py` does this today against the *old* flat schema; updating it to write directly into `sustainability_sources` entries is tracked in `ROADMAP.md`.

## Contributing

New sources and corrections go through a review workflow before being merged — propose a change as a file under `submissions/pending/`, an automated check validates its shape, a maintainer reviews its substance, then it's merged. See `CONTRIBUTING.md` for the full process (submission template, review checklist, and the scripts that enforce each step).

## License

CC0 1.0 — public domain. See `LICENSE`.
