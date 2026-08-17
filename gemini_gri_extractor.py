#!/usr/bin/env python3
"""
Fills in GRI verification fields for eu_sustainability_reports.csv using the
Gemini API's url_context tool, which lets Gemini fetch and read a PDF
directly from a URL (no need to download files yourself).

SETUP
1. Get an API key: https://aistudio.google.com/apikey
2. pip install google-genai pydantic --break-system-packages   (or plain pip install in your own env)
3. export GEMINI_API_KEY="your-key-here"          (Windows cmd: set GEMINI_API_KEY=your-key-here)
4. Put these two files in the same folder as this script:
     - eu_sustainability_reports.csv   (the dataset, empty verification fields - now 487 companies, 27 countries)
     - all_487_report_sources.csv      (company_name, country, report_title, source_pdf_url, additional_source_urls, notes)

   NOTE: the dataset grew from 98 -> 202 -> 311 -> 487 companies (27 EU countries covered, with
   deeper coverage per country each round). If you already have a partial
   eu_sustainability_reports_filled.csv from a previous run, use merge_expansion.py (included
   alongside this script) to fold your existing results into the new 487-row file before
   resuming - that preserves everything you've already verified and only queues up the
   newly-added companies (176 in this latest round).
5. python gemini_gri_extractor.py

OUTPUT
- eu_sustainability_reports_filled.csv  (same schema as the original, fields filled in)
- eu_sustainability_reports_filled.json
- gemini_run_log.csv  (per-company: what Gemini returned + any errors, for your own review)

RESUMING ACROSS MULTIPLE DAYS / RUNS
This script uses ONE API call per company (not two), and defaults to gemini-3.5-flash-lite,
which on the free tier has a much higher daily cap (500 requests/day) than regular Flash
models (20/day) - so a 98-company run should comfortably finish in a single sitting. If you
still run out of quota partway (e.g. from other usage on the same key that day), resuming is
handled automatically:
- Every run reads eu_sustainability_reports_filled.csv if it already exists (instead of
  starting over from the blank original), so you can just rerun the script again later and
  it picks up where it left off.
- Companies already marked "verified" or "unable to verify - no GRI index found" (both are
  genuine outcomes - Gemini actually read the document and reached a conclusion) are skipped.
- Companies that failed due to an API error (quota exhausted, transient 503, etc.) are left
  as "needs retry" and WILL be retried on the next run - they are not mislabeled as "no GRI
  index found" just because the API call failed. This distinction matters: conflating "we
  couldn't check" with "we checked and found nothing" would make the dataset misleading.
- If ALL models' daily quota is exhausted, the script stops cleanly with a message telling
  you to come back later, rather than burning through the rest of the list logging instant
  failures.

MODEL FALLBACK
A single model being temporarily overloaded (503 UNAVAILABLE) shouldn't stall the whole run.
For each company, the script tries MODELS in order: if the current model fails after its
retries (transient 503s) or its daily quota is exhausted, it moves on to the next model in
the list before giving up on that company. A model whose daily quota gets exhausted is
remembered as "dead" for the rest of this run so later companies skip straight past it
instead of re-discovering the same quota error each time. The script only stops the whole
run (as a QuotaExhausted) once every model in MODELS is dead. Which model actually answered
each company is recorded in gemini_run_log.csv's "model" column.

NOTES
- Primary model is gemini-3.5-flash-lite - confirmed to support the url_context tool,
  structured output, and function calling, with a much higher free-tier daily quota (500/day)
  than full Flash models (20/day each). Fallbacks are gemini-3.5-flash and gemini-2.5-flash,
  each with their own separate 20/day free-tier quota - so a fully-exhausted primary model
  still leaves up to 40 more companies gettable per day via the fallbacks.
  gemini-2.5-pro is retired for new API keys (404 "no longer available to new users") so it's
  not included in the fallback list.
- If you have billing enabled on your Google AI Studio / Cloud project, daily quotas are much
  higher (or removed) across all these models and this will run to completion in one sitting.
"""

import csv
import json
import os
import re
import time
import sys
from pathlib import Path

try:
    from google import genai
    from google.genai import types
except ImportError:
    sys.exit("Missing dependency. Run: pip install google-genai pydantic --break-system-packages")

# Tried in order per company: primary first (high free-tier quota), then fallbacks if the
# primary is overloaded (503) or its daily quota is exhausted. gemini-2.5-pro is deliberately
# excluded - it's retired for new API keys (404 "no longer available to new users").
MODELS = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-2.5-flash"]
SLEEP_SECONDS = 4  # gap between companies, be polite to rate limits
MAX_RETRIES_TRANSIENT = 2  # retries per model for transient errors (503 overload), NOT for daily quota

BASE_DIR = Path(__file__).parent
ORIGINAL_CSV = BASE_DIR / "eu_sustainability_reports.csv"
MANIFEST_CSV = BASE_DIR / "all_487_report_sources.csv"
OUT_CSV = BASE_DIR / "eu_sustainability_reports_filled.csv"
OUT_JSON = BASE_DIR / "eu_sustainability_reports_filled.json"
LOG_CSV = BASE_DIR / "gemini_run_log.csv"

FIELDNAMES = [
    "company_name", "country", "sector", "hq_city", "sustainability_page_url",
    "gri_referenced", "report_year", "universal_standards",
    "topic_standards_200", "topic_standards_300", "topic_standards_400",
    "externally_assured", "verification_status", "source_method",
]

DONE_STATUSES = {"verified", "unable to verify - no GRI index found"}

PROMPT_TEMPLATE = """You are verifying GRI (Global Reporting Initiative) Standards disclosures for {company_name} ({country}).

Open and read the document(s) at these URL(s), using your URL-reading capability:
{urls}

Find the GRI Content Index (or an equivalent explicit table mapping disclosures to GRI Standards codes). It's often an appendix near the end of a sustainability/ESG report, or a separate standalone document.

Many EU companies have moved to CSRD/ESRS reporting and may NOT have a standalone GRI index anymore - that is a legitimate and common outcome. Do not treat ESRS disclosure requirement codes (e.g. "E1", "S1") as GRI codes; only report actual GRI Standards codes (e.g. GRI 305, GRI 403).

Respond with ONLY a single JSON object (no markdown fences, no other text) matching exactly this shape:
{{
  "gri_index_found": true or false - true ONLY if you actually located a GRI content index or explicit GRI standards mapping table,
  "report_year": string or null - the reporting period the document covers, e.g. "2025" or "FY2025",
  "universal_standards": string or null - which GRI 1/2/3 version was used, e.g. "GRI 1: Foundation 2021",
  "topic_standards_200": string or null - comma-separated GRI 200-series (Economic) codes disclosed, e.g. "201, 205",
  "topic_standards_300": string or null - comma-separated GRI 300-series (Environmental) codes disclosed, e.g. "302, 305",
  "topic_standards_400": string or null - comma-separated GRI 400-series (Social) codes disclosed, e.g. "403, 405",
  "externally_assured": string or null - "Y" if the document states third-party assurance was obtained, "N" if explicitly not, null if unclear,
  "evidence_note": string - 1-2 sentences on what you found and where (page/section), or why you could not confirm a GRI index
}}

Do not guess or infer codes from general sustainability topic descriptions - only report what you can directly point to in the document. If you cannot find and confirm an actual GRI content index, set gri_index_found to false and leave the other fields null, with evidence_note explaining why.
"""


def load_manifest():
    manifest = {}
    with open(MANIFEST_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            manifest[row["company_name"].strip()] = row
    return manifest


def parse_json_response(text):
    text = text.strip()
    # strip markdown code fences if the model added them despite instructions
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"No JSON object found in response: {text[:300]}")
    return json.loads(m.group(0))


class QuotaExhausted(Exception):
    pass


def extract_for_company(client, company_name, country, urls, dead_models):
    """Tries each model in MODELS (skipping any already known to be dead this run).
    Returns (result_dict, model_name_that_answered). Raises QuotaExhausted only once
    every model has had its daily quota exhausted; raises the last error if every
    model was tried and none succeeded for other reasons (bad response, etc.)."""
    prompt = PROMPT_TEMPLATE.format(company_name=company_name, country=country, urls="\n".join(urls))

    last_err = None
    tried_any = False
    for model in MODELS:
        if model in dead_models:
            continue
        tried_any = True
        for attempt in range(MAX_RETRIES_TRANSIENT + 1):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        tools=[{"url_context": {}}],
                        temperature=0,
                    ),
                )
                return parse_json_response(response.text), model
            except Exception as e:
                msg = str(e)
                if "RESOURCE_EXHAUSTED" in msg and "PerDay" in msg:
                    dead_models.add(model)
                    print(f"  [{model} daily quota exhausted - falling back]")
                    last_err = e
                    break  # this model is done for the day, try the next model
                last_err = e
                if attempt < MAX_RETRIES_TRANSIENT and ("UNAVAILABLE" in msg or "503" in msg):
                    time.sleep(5 * (attempt + 1))
                    continue
                break  # non-retryable error on this model, try the next model
        # falls through to the next model in MODELS

    if not tried_any or len(dead_models) >= len(MODELS):
        raise QuotaExhausted(str(last_err))
    raise last_err


def main():
    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("Set GEMINI_API_KEY first (env var), then rerun.")
    if not MANIFEST_CSV.exists():
        sys.exit(f"Missing {MANIFEST_CSV.name} - put the report-source manifest next to this script.")

    client = genai.Client()
    manifest = load_manifest()

    # Resume from a previous partial run if one exists, otherwise start from the blank original.
    if OUT_CSV.exists():
        with open(OUT_CSV, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        print(f"Resuming from existing {OUT_CSV.name} ({len(rows)} rows).")
    elif ORIGINAL_CSV.exists():
        with open(ORIGINAL_CSV, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        print(f"Starting fresh from {ORIGINAL_CSV.name} ({len(rows)} rows).")
    else:
        sys.exit(f"Missing both {OUT_CSV.name} and {ORIGINAL_CSV.name} - need one to start from.")

    log_rows = []
    if LOG_CSV.exists():
        with open(LOG_CSV, newline="", encoding="utf-8") as f:
            log_rows = list(csv.DictReader(f))

    processed_this_run = 0
    skipped_done = 0
    dead_models = set()  # models whose daily quota has been exhausted this run

    for row in rows:
        company = row["company_name"].strip()
        status = row.get("verification_status", "").strip()

        if status in DONE_STATUSES:
            skipped_done += 1
            continue

        m = manifest.get(company)
        if not m or not m.get("source_pdf_url"):
            print(f"[skip] {company} - no source URL in manifest")
            row["verification_status"] = "unable to verify - no GRI index found"
            log_rows.append({"company_name": company, "status": "no_manifest_url", "detail": "", "model": ""})
            continue

        urls = [m["source_pdf_url"]]
        extra = (m.get("additional_source_urls") or "").strip()
        if extra:
            urls.extend(u.strip() for u in extra.split(";") if u.strip())
        print(f"[query] {company} -> {len(urls)} doc(s)")

        try:
            result, model_used = extract_for_company(client, company, row["country"], urls, dead_models)
        except QuotaExhausted:
            print(f"\nAll models' daily quota exhausted after {processed_this_run} companies this run.")
            print("Progress has been saved. Just rerun this script again tomorrow (or after")
            print("your quota resets) to continue - it will pick up where it left off.")
            break
        except Exception as e:
            print(f"[error] {company}: {e}")
            row["verification_status"] = "error - retry needed"
            log_rows.append({"company_name": company, "status": "api_error", "detail": str(e), "model": ""})
            time.sleep(SLEEP_SECONDS)
            continue

        if model_used != MODELS[0]:
            print(f"  (answered by fallback model {model_used})")

        gri_found = bool(result.get("gri_index_found"))
        if gri_found:
            row["report_year"] = result.get("report_year") or ""
            row["universal_standards"] = result.get("universal_standards") or ""
            row["topic_standards_200"] = result.get("topic_standards_200") or ""
            row["topic_standards_300"] = result.get("topic_standards_300") or ""
            row["topic_standards_400"] = result.get("topic_standards_400") or ""
            row["externally_assured"] = result.get("externally_assured") or ""
            row["verification_status"] = "verified"
        else:
            row["verification_status"] = "unable to verify - no GRI index found"

        log_rows.append({
            "company_name": company,
            "status": "verified" if gri_found else "not_found",
            "detail": result.get("evidence_note", ""),
            "model": model_used,
        })
        processed_this_run += 1

        # write progressively so partial progress isn't lost
        with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
        with open(OUT_JSON, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)
        with open(LOG_CSV, "w", newline="", encoding="utf-8") as f:
            # restval handles resuming from an older log file written before the "model"
            # column existed - those rows just get a blank model value.
            writer = csv.DictWriter(f, fieldnames=["company_name", "status", "detail", "model"], restval="")
            writer.writeheader()
            writer.writerows(log_rows)

        time.sleep(SLEEP_SECONDS)
    else:
        print(f"\nDone. Processed {processed_this_run} this run, {skipped_done} already done.")

    print(f"Wrote {OUT_CSV.name}, {OUT_JSON.name}, {LOG_CSV.name}")


if __name__ == "__main__":
    main()
