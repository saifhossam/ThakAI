"""
Arabic Legal Document – Hierarchical Structure Profiler
Outputs two JSON schemas per document:
  1. document_metadata  – identity, jurisdiction, dates
  2. structure_profile  – hierarchy, counts, pages
"""

import re
import json
import sys
import uuid
from pathlib import Path


# ---------------------------------------------------------------------------
# *** Configuration ***
# ---------------------------------------------------------------------------
FOLDER_PATH   = r"Splits"    # ← input folder containing the .txt files to process
OUTPUT_FOLDER = r"Regex Only Output"  # ← output folder for the generated JSON files
DOC_TYPE      = "Federal Law"                           # doc-type label
JURISDICTION  = "UAE"                                   # ← Country label 
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Structural patterns
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

# Mapping Arabic doc-type keywords → English label
DOC_TYPE_MAP = {
    "مرسوم بقانون":  "Decree-Law",
    "قانون اتحادي":  "Federal Law",
    "قرار وزاري":    "Ministerial Decision",
    "مرسوم":         "Decree",
    "قانون":         "Law",
    "لائحة":         "Regulation",
    "قرار":          "Decision",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_law_number(text: str) -> str | None:
    """Extract the primary law/decree number from the issuing clause."""
    patterns = [
        r"أصدرنا\s+(المرسوم بقانون الاتحادي رقم \(\d+\) لسنة \d{4})",
        r"أصدرنا\s+(المرسوم بقانون رقم \(\d+\) لسنة \d{4})",
        # Fallback: pick the law ref right before أصدرنا
        r"((?:المرسوم بقانون|القانون)\s+(?:الاتحادي\s+)?رقم\s*\(\d+\)\s+لسنة\s+\d{4})"
        r"(?=[^.]{0,300}أصدرنا)",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1).strip()

    # Generic: find the first occurrence of a law reference pattern anywhere in the text
    block_m = re.search(r"((?:المرسوم بقانون|القانون الاتحادي|قانون اتحادي)"
                        r"\s*(?:الاتحادي\s+)?رقم\s*\(\d+\)\s+لسنة\s+\d{4})", text)
    return block_m.group(1).strip() if block_m else None


def extract_title(text: str) -> str | None:
    """Extract the law subject (بشأن / في شأن) from the issuing law ref."""
    m = re.search(
        r"(?:المرسوم بقانون|القانون الاتحادي|قانون اتحادي)"
        r"[^،\n]{0,60}"
        r"(?:بشأن|في شأن|بإصدار)\s+([^،\n]{5,120})",
        text
    )
    if m:
        return m.group(1).strip().rstrip("،.")
    return None


def extract_year(text: str) -> str | None:
    """Extract the year from the first law ref."""
    m = re.search(r"لسنة\s+(\d{4})", text)
    return m.group(1) if m else None


def detect_doc_type(text: str) -> str:
    for arabic, english in DOC_TYPE_MAP.items():
        if arabic in text[:500]:
            return english
    return DOC_TYPE


def extract_page_info(text: str) -> dict:
    """Extract page count and preamble flag from === صفحة X === markers."""
    preamble_marker = re.search(r"===\s*صفحة المقدمة\s*===", text)
    numbered_pages  = re.findall(r"===\s*صفحة\s+(\d+)\s*===", text)

    has_preamble = preamble_marker is not None
    page_numbers = [int(n) for n in numbered_pages]
    total_pages  = max(page_numbers) if page_numbers else None

    return {
        "has_preamble_page": has_preamble,
        "total_pages": total_pages,
        "page_markers_found": len(numbered_pages) + (1 if has_preamble else 0),
    }


# ---------------------------------------------------------------------------
# Core profiler  →  returns (metadata_json, structure_json)
# ---------------------------------------------------------------------------
def profile_document(filepath: str, doc_type_override: str | None = None,
                     jurisdiction: str = "UAE") -> tuple[dict, dict]:

    text     = Path(filepath).read_text(encoding="utf-8")
    doc_id   = str(uuid.uuid4())
    filename = Path(filepath).name

    # ── 1. Detect structural vocabulary ──────────────────────────────────
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

    # ── 2. Extract metadata ───────────────────────────────────────────────
    detected_type = doc_type_override or detect_doc_type(text)
    law_number    = extract_law_number(text)
    title         = extract_title(text)
    year          = extract_year(text)
    effective_date = f"{year}-01-01" if year else None

    # ── 3. Page info ──────────────────────────────────────────────────────
    page_info = extract_page_info(text)

    # ── 4. Structure counts ───────────────────────────────────────────────
    bab_count   = next((d["estimated_count"] for d in found_divisions if d["division_type"] == "الباب"),  0)
    fasl_count  = next((d["estimated_count"] for d in found_divisions if d["division_type"] == "الفصل"), 0)
    mada_count  = next((d["estimated_count"] for d in found_divisions if d["division_type"] == "المادة"), 0)
    total_nodes = bab_count + fasl_count + mada_count
    top_level   = hierarchy_en[0] if hierarchy_en else None
    has_preamble = (
        page_info["has_preamble_page"]
        or bool(re.search(r"بعد الاطلاع على الدستور|ديباجة|المقدمة", text[:1000]))
    )

    # ── 5. Build output schemas ───────────────────────────────────────────
    metadata = {
        "document_id":    doc_id,
        "filename":       filename,
        "title":          title,
        "law_number":     law_number,
        "document_type":  detected_type,
        "jurisdiction":   jurisdiction,
        "language":       "Arabic",
        "effective_date": effective_date,
        "status":         "in_force",
        "message":        "profiled",
    }

    structure = {
        "document_id":         doc_id,
        "filename":            filename,
        "total_nodes":         total_nodes,
        "parts_extracted":     bab_count,
        "chapters_extracted":  fasl_count,
        "articles_extracted":  mada_count,
        "top_level_type":      top_level,
        "has_preamble":        has_preamble,
        "pages":               page_info,
        "structural_vocabulary": found_divisions,
        "hierarchy":           hierarchy,
        "hierarchy_english":   hierarchy_en,
        "message":             "structure extracted",
    }

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
        print(f"Processing: {filepath.name} ...", end=" ")

        metadata, structure = profile_document(
            str(filepath),
            doc_type_override=DOC_TYPE,
            jurisdiction=JURISDICTION,
        )

        stem = filepath.stem
        (output_folder / f"{stem}_metadata.json").write_text(
            json.dumps(metadata,  ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output_folder / f"{stem}_structure.json").write_text(
            json.dumps(structure, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        print(f"saved → {stem}_metadata.json  +  {stem}_structure.json")

    print(f"\nDone! {len(txt_files)} file(s) processed → '{output_folder}'.")


if __name__ == "__main__":
    main()