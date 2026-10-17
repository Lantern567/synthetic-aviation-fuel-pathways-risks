"""Verify that every Supplementary References entry corresponds to a real,
correctly-cited paper.

Strategy:
  1. Extract the numbered entries directly from insert_section1_refs.REFS
     so the script is authoritative even without re-reading the docx.
  2. For each entry, extract:
       - DOI (if written explicitly in the text)
       - Best-effort first-author surname + year + shortened title
  3. Query OpenAlex:
       - If DOI present: look up by DOI, compare author / year / venue.
       - Otherwise: title-search, then check whether the top match has a
         plausible similarity (first-author surname + year match).
  4. Classify every reference as:
       - ok            DOI resolves and author/year/venue match (or no DOI
                       but title search returns clear author+year match)
       - doi_mismatch  DOI resolves but author/year/venue differ
       - doi_404       DOI was in the text but does not resolve
       - title_weak    No DOI, best title match is marginal / no match
       - skipped       Data sources, reports, books that cannot be verified
                       through OpenAlex (IEA, IRENA, GEM datasets, NDRC
                       notices, BADA software etc.) — listed separately
  5. Print a summary table for human review.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from insert_section1_refs import REFS  # noqa: E402

USER_AGENT = "SAFAppendixRefVerifier/0.1 (mailto:verify@example.com)"
OA_BASE = "https://api.openalex.org/works"

# Entries we do not expect OpenAlex to index — data sources, software,
# standards bodies, agency reports, book monographs. They still need
# human verification (URL + access date) but are not fabrication risks.
NON_OA_KEYWORDS = [
    "PANGAEA",  # dataset DOI on PANGAEA (OpenAlex sometimes misses)
    "Flightera",
    "EUROCONTROL",
    "Global Energy Monitor",
    "Baker Institute",
    "Global CCS Institute",
    "National Development and Reform Commission",
    "National Bureau of Statistics",
    "International Energy Agency",
    "International Renewable Energy Agency",
    "International Air Transport Association",
    "OpenStreetMap contributors",
    "GraphHopper",
    "NREL Technical Report",
    "SCCER Mobility Whitepaper",
    "Fischer-Tropsch Refining (Wiley-VCH",  # de Klerk 2011 book
    "OIES Paper",
    "Global Sensitivity Analysis: The Primer (Wiley",  # Saltelli 2008 book
]


def extract_doi(text: str) -> str | None:
    """Return the first DOI-like string found in text, or None."""
    # Typical DOI patterns: "10.xxxx/yyyy", sometimes prefixed with doi.org URL.
    m = re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", text, flags=re.IGNORECASE)
    if m is None:
        return None
    doi = m.group(0).rstrip(".,;)")
    return doi


def extract_first_author_surname(text: str) -> str | None:
    # Entry format: "Surname, A. et al. ..." or "Surname, A. B. & Other, C. Title."
    # Surname is the first word before the first comma.
    m = re.match(r"([A-Z][A-Za-zÀ-ÿ'\-]+(?:\s[A-Za-zÀ-ÿ'\-]+)?),\s+[A-ZÀ-ÿ]", text.strip())
    if m is None:
        # Some "et al." entries or agencies.
        return None
    return m.group(1)


def extract_year(text: str) -> int | None:
    m = re.search(r"\((\d{4})\)\s*\.?\s*$", text.strip())
    if m:
        return int(m.group(1))
    m = re.search(r"\((\d{4})\)", text)
    if m:
        return int(m.group(1))
    return None


def extract_title(text: str) -> str | None:
    """Very rough title extractor: the segment after the author block, before the venue italics."""
    # Strip everything through the first ". " after the authors. We assume
    # authors end at the first ". " that is followed by an uppercase word.
    # This is imperfect — used only for fallback title search.
    m = re.search(r"\.\s+([A-Z][^.]{10,200})\.", text)
    if m:
        return m.group(1).strip()
    return None


def fetch_openalex(doi: str | None, title: str | None) -> dict | None:
    try:
        if doi:
            url = f"{OA_BASE}/https://doi.org/{doi}"
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read())
        elif title:
            q = urllib.parse.quote(title)
            url = f"{OA_BASE}?search={q}&per-page=1&mailto=verify@example.com"
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
                results = data.get("results") or []
                return results[0] if results else None
    except Exception as e:
        return {"_error": str(e)}
    return None


def is_skippable(text: str) -> bool:
    return any(kw in text for kw in NON_OA_KEYWORDS)


def classify(entry: str) -> dict:
    result: dict = {"text": entry, "status": "unknown"}
    if is_skippable(entry):
        result["status"] = "skipped_nonOA"
        return result
    doi = extract_doi(entry)
    author = extract_first_author_surname(entry)
    year = extract_year(entry)
    title = extract_title(entry)
    result.update({"doi": doi, "author": author, "year": year, "title": title})

    record = fetch_openalex(doi, title)
    if record is None:
        result["status"] = "not_found"
        return result
    if "_error" in record:
        result["status"] = "error"
        result["error"] = record["_error"]
        return result
    # Compare
    oa_year = record.get("publication_year")
    authors = [a["author"]["display_name"] for a in record.get("authorships", [])[:3]]
    venue = ((record.get("primary_location") or {}).get("source") or {}).get("display_name")
    oa_title = (record.get("title") or "")
    result["openalex"] = {
        "year": oa_year,
        "authors": authors,
        "venue": venue,
        "title": oa_title[:110],
        "doi": record.get("doi"),
    }
    # Check: first author surname must appear in first listed OA author
    author_ok = False
    if author and authors:
        # simple case-insensitive surname match against any of first 3 authors
        author_ok = any(author.lower() in a.lower() for a in authors)
    year_ok = bool(year and oa_year and abs(year - oa_year) <= 1)
    if doi:
        # DOI was provided — strict check
        if author_ok and year_ok:
            result["status"] = "ok_by_doi"
        else:
            result["status"] = "doi_mismatch"
    else:
        # No DOI in entry; we did a title search
        if author_ok and year_ok:
            result["status"] = "ok_by_title_search"
        else:
            result["status"] = "title_weak"
    return result


def main() -> None:
    print(f"Verifying {len(REFS)} references...\n")
    statuses = {}
    problems = []
    for idx, entry in enumerate(REFS, start=1):
        res = classify(entry)
        statuses[res["status"]] = statuses.get(res["status"], 0) + 1
        head = entry[:90].replace("\n", " ")
        tag = res["status"]
        print(f"[{idx:>3}] {tag:<20} {head}")
        if res["status"] in ("doi_mismatch", "not_found", "title_weak", "error"):
            problems.append((idx, res))
        time.sleep(0.1)  # gentle rate limit
    print("\n========== SUMMARY ==========")
    for s, c in sorted(statuses.items(), key=lambda x: -x[1]):
        print(f"  {s:<22} : {c}")
    print("\n========== PROBLEMS (need review) ==========")
    for idx, res in problems:
        print(f"\n[{idx}] status={res['status']}")
        print(f"  text: {res['text'][:200]}")
        if "openalex" in res:
            oa = res["openalex"]
            print(f"  OpenAlex -> {oa['authors']} ({oa['year']}) | {oa['venue']}")
            print(f"             {oa['title']}")
            print(f"             doi={oa['doi']}")


if __name__ == "__main__":
    main()
