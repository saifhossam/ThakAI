"""
Arabic Legal Document – Hybrid Profiler
Strategy:
  - Rule-based (Regex) handles structure  → fast, free, deterministic
  - Gemini fills metadata + any gaps regex couldn't extract
  - Final output merges both, with a confidence field per section
"""

import re
import json
import sys
import uuid
from pathlib import Path
import google.generativeai as genai


# ---------------------------------------------------------------------------
# *** Configuration ***
# ---------------------------------------------------------------------------
FOLDER_PATH    = r"Splits"    # ← input folder containing the .txt files to process
OUTPUT_FOLDER  = r"Hybrid Output (AI & Regex)"  # ← output folder for the generated JSON files
GEMINI_API_KEY = "//"             # ← Gemini API Key
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Gemini setup
# ---------------------------------------------------------------------------
genai.configure(api_key=GEMINI_API_KEY)
gemini = genai.GenerativeModel("gemini-2.5-flash")


# ---------------------------------------------------------------------------
# Structural patterns  (rule-based layer)
# ---------------------------------------------------------------------------
PATTERNS = [
    {
        "division_type": "الباب",
        "english_label": "Part",
        "level_candidate": 1,
        "regex": r"^الباب\s+[\u0600-\u06ff]+",
        "line_regex": re.compile(r"^الباب\s+([\u0600-\u06ff]+)", re.MULTILINE),
        "numbering_style": "arabic_ordinal",
        "pattern_description": "الباب followed by Arabic ordinal",
        "example": "الباب الأول",
    },
    {
        "division_type": "الفصل",
        "english_label": "Chapter",
        "level_candidate": 2,
        "regex": r"^الفصل\s+[\u0600-\u06ff]+",
        "line_regex": re.compile(r"^الفصل\s+([\u0600-\u06ff]+)", re.MULTILINE),
        "numbering_style": "arabic_ordinal",
        "pattern_description": "الفصل followed by Arabic ordinal",
        "example": "الفصل الأول",
    },
    {
        "division_type": "المادة",
        "english_label": "Article",
        "level_candidate": 3,
        "regex": r"^المادة\s*\(\d+\)",
        "line_regex": re.compile(r"^المادة\s*\((\d+)\)", re.MULTILINE),
        "numbering_style": "numeric_parenthesised",
        "pattern_description": "المادة followed by integer in parentheses",
        "example": "المادة (1)",
    },
]

DOC_TYPE_MAP = {
    "مرسوم بقانون": "Decree-Law",
    "قانون اتحادي": "Federal Law",
    "قرار وزاري":   "Ministerial Decision",
    "مرسوم":        "Decree",
    "قانون":        "Law",
    "لائحة":        "Regulation",
    "قرار":         "Decision",
}


# ---------------------------------------------------------------------------
# LAYER 1 — Rule-based extraction
# ---------------------------------------------------------------------------
def regex_extract_structure(text: str, doc_id: str, filename: str) -> dict:
    found_divisions = []
    for pat in PATTERNS:
        matches = pat["line_regex"].findall(text)
        if not matches:
            continue
        first_match = re.search(pat["regex"], text, re.MULTILINE)
        example_str = first_match.group(0).strip() if first_match else pat["example"]
        if len(example_str) > 50:
            example_str = example_str[:50].rstrip() + "…"
        found_divisions.append({
            "division_type": pat["division_type"],
            "english_label": pat["english_label"],
            "level": pat["level_candidate"],
            "numbering_style": pat["numbering_style"],
            "pattern_description": pat["pattern_description"],
            "regex": pat["regex"],
            "example": example_str,
            "estimated_count": len(matches),
        })

    for idx, div in enumerate(found_divisions, start=1):
        div["level"] = idx

    hierarchy    = [d["division_type"] for d in found_divisions]
    hierarchy_en = [d["english_label"]  for d in found_divisions]
    for d in found_divisions:
        del d["english_label"]

    bab_count  = next((d["estimated_count"] for d in found_divisions if d["division_type"] == "الباب"),  0)
    fasl_count = next((d["estimated_count"] for d in found_divisions if d["division_type"] == "الفصل"), 0)
    mada_count = next((d["estimated_count"] for d in found_divisions if d["division_type"] == "المادة"), 0)

    page_info  = regex_extract_pages(text)
    has_preamble = page_info["has_preamble_page"] or bool(
        re.search(r"بعد الاطلاع على الدستور|ديباجة|المقدمة", text[:1000])
    )

    return {
        "document_id": doc_id,
        "filename": filename,
        "total_nodes": bab_count + fasl_count + mada_count,
        "parts_extracted": bab_count,
        "chapters_extracted": fasl_count,
        "articles_extracted": mada_count,
        "top_level_type": hierarchy_en[0] if hierarchy_en else None,
        "has_preamble": has_preamble,
        "pages": page_info,
        "structural_vocabulary": found_divisions,
        "hierarchy": hierarchy,
        "hierarchy_english": hierarchy_en,
    }


def regex_extract_metadata(text: str, doc_id: str, filename: str) -> dict:
    """Extract what regex can confidently get."""
    # Law number
    law_m = re.search(
        r"((?:المرسوم بقانون|القانون الاتحادي|قانون اتحادي)"
        r"\s*(?:الاتحادي\s+)?رقم\s*\(\d+\)\s+لسنة\s+\d{4})", text
    )
    law_number = law_m.group(1).strip() if law_m else None

    # Year → effective date
    year_m = re.search(r"لسنة\s+(\d{4})", text)
    year   = year_m.group(1) if year_m else None

    # Doc type
    doc_type = next(
        (english for arabic, english in DOC_TYPE_MAP.items() if arabic in text[:500]),
        None
    )

    return {
        "document_id": doc_id,
        "filename": filename,
        "law_number_regex": law_number,
        "effective_date_regex": f"{year}-01-01" if year else None,
        "document_type_regex": doc_type,
    }


def regex_extract_pages(text: str) -> dict:
    preamble      = re.search(r"===\s*صفحة المقدمة\s*===", text)
    numbered      = re.findall(r"===\s*صفحة\s+(\d+)\s*===", text)
    page_numbers  = [int(n) for n in numbered]
    return {
        "has_preamble_page": preamble is not None,
        "total_pages": max(page_numbers) if page_numbers else None,
        "page_markers_found": len(numbered) + (1 if preamble else 0),
    }


# ---------------------------------------------------------------------------
# LAYER 2 — Gemini fills gaps
# ---------------------------------------------------------------------------
GEMINI_GAP_PROMPT = """
You are a legal document analyst specializing in Arabic UAE law.
Analyze the text and fill in the missing metadata fields.

Already extracted by rule-based system:
{regex_findings}

Extract the following fields that the rule-based system could NOT reliably extract:
- title: the law subject in arabic (from بشأن / في شأن clause)
- law_number: formatted in English e.g. "Federal Decree-Law No. 32 of 2021"
- document_type: one of [Federal Law, Decree-Law, Ministerial Decision, Decree, Regulation, Decision]
- effective_date: YYYY-MM-DD format if a specific date is mentioned, otherwise derive from year
- status: "in_force" unless explicitly stated otherwise

Also verify/correct these rule-based findings if they look wrong:
- structural counts (parts, chapters, articles)
- has_preamble

Return ONLY a valid JSON object (no markdown, no explanation):
{{
  "title": "...",
  "law_number": "...",
  "document_type": "...",
  "effective_date": "...",
  "status": "in_force",
  "ai_corrections": {{
    "parts_extracted": <corrected count or null if regex was correct>,
    "chapters_extracted": <corrected count or null if regex was correct>,
    "articles_extracted": <corrected count or null if regex was correct>,
    "has_preamble": <true/false or null if regex was correct>
  }}
}}

Document text:
{text}
"""


def gemini_fill_gaps(text: str, regex_meta: dict, regex_struct: dict) -> dict:
    regex_summary = {
        "law_number_found":    regex_meta.get("law_number_regex"),
        "effective_date_found": regex_meta.get("effective_date_regex"),
        "document_type_found": regex_meta.get("document_type_regex"),
        "parts":     regex_struct.get("parts_extracted"),
        "chapters":  regex_struct.get("chapters_extracted"),
        "articles":  regex_struct.get("articles_extracted"),
        "has_preamble": regex_struct.get("has_preamble"),
    }

    prompt = GEMINI_GAP_PROMPT.format(
        regex_findings=json.dumps(regex_summary, ensure_ascii=False, indent=2),
        text=text[:20000]
    )

    response = gemini.generate_content(prompt)
    clean    = re.sub(r"```(?:json)?", "", response.text).strip().rstrip("`").strip()

    try:
        return json.loads(clean)
    except json.JSONDecodeError as e:
        print(f"\n  ⚠ Gemini parse error: {e}. Using regex fallback for metadata.")
        return {}


# ---------------------------------------------------------------------------
# LAYER 3 — Merge results
# ---------------------------------------------------------------------------
def merge_results(doc_id: str, filename: str,
                  regex_meta: dict, regex_struct: dict,
                  ai_data: dict) -> tuple[dict, dict]:

    corrections = ai_data.pop("ai_corrections", {}) or {}

    # Apply AI corrections to structure if provided
    if corrections.get("parts_extracted") is not None:
        regex_struct["parts_extracted"]    = corrections["parts_extracted"]
    if corrections.get("chapters_extracted") is not None:
        regex_struct["chapters_extracted"] = corrections["chapters_extracted"]
    if corrections.get("articles_extracted") is not None:
        regex_struct["articles_extracted"] = corrections["articles_extracted"]
    if corrections.get("has_preamble") is not None:
        regex_struct["has_preamble"]       = corrections["has_preamble"]

    # Recalculate total_nodes if corrections were applied
    regex_struct["total_nodes"] = (
        regex_struct["parts_extracted"] +
        regex_struct["chapters_extracted"] +
        regex_struct["articles_extracted"]
    )

    # Metadata: prefer AI for rich fields, regex for numeric/date fields
    metadata = {
        "document_id":    doc_id,
        "filename":       filename,
        "title":          ai_data.get("title"),
        "law_number":     ai_data.get("law_number") or regex_meta.get("law_number_regex"),
        "document_type":  ai_data.get("document_type") or regex_meta.get("document_type_regex"),
        "jurisdiction":   "UAE",
        "language":       "Arabic",
        "effective_date": ai_data.get("effective_date") or regex_meta.get("effective_date_regex"),
        "status":         ai_data.get("status", "in_force"),
        "extraction_method": {
            "law_number":     "ai"    if ai_data.get("law_number")    else "regex",
            "document_type":  "ai"    if ai_data.get("document_type") else "regex",
            "effective_date": "ai"    if ai_data.get("effective_date") else "regex",
            "title":          "ai",
            "structure":      "regex" if not corrections else "regex+ai_corrected",
        },
        "message": "profiled",
    }

    structure = {
        **regex_struct,
        "message": "structure extracted",
    }

    return metadata, structure


# ---------------------------------------------------------------------------
# Main profiler
# ---------------------------------------------------------------------------
def profile_document(filepath: str) -> tuple[dict, dict]:
    text     = Path(filepath).read_text(encoding="utf-8")
    doc_id   = str(uuid.uuid4())
    filename = Path(filepath).name

    print("  [1/3] Regex extraction ...", end=" ", flush=True)
    regex_meta   = regex_extract_metadata(text, doc_id, filename)
    regex_struct = regex_extract_structure(text, doc_id, filename)
    print("done")

    print("  [2/3] Gemini filling gaps ...", end=" ", flush=True)
    ai_data = gemini_fill_gaps(text, regex_meta, regex_struct)
    print("done")

    print("  [3/3] Merging results ...", end=" ", flush=True)
    metadata, structure = merge_results(doc_id, filename, regex_meta, regex_struct, ai_data)
    print("done")

    return metadata, structure


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    input_folder  = Path(FOLDER_PATH)
    output_folder = Path(OUTPUT_FOLDER)

    if not input_folder.is_dir():
        print(f"Error: '{input_folder}' is not a valid folder.")
        sys.exit(1)

    output_folder.mkdir(parents=True, exist_ok=True)

    txt_files = sorted(input_folder.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in '{input_folder}'.")
        sys.exit(1)

    for filepath in txt_files:
        print(f"\nProcessing: {filepath.name}")

        try:
            metadata, structure = profile_document(str(filepath))
            stem = filepath.stem
            (output_folder / f"{stem}_metadata.json").write_text(
                json.dumps(metadata,  ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (output_folder / f"{stem}_structure.json").write_text(
                json.dumps(structure, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"  ✓ saved → {stem}_metadata.json  +  {stem}_structure.json")

        except Exception as e:
            print(f"  ✗ FAILED: {e}")

    print(f"\nDone! {len(txt_files)} file(s) processed → '{output_folder}'.")


if __name__ == "__main__":
    main()
