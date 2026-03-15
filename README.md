# 📜 Arabic Legal Document Processing Pipeline

A modular, end-to-end pipeline for extracting, splitting, profiling, and structuring Arabic legal documents (UAE laws) from PDFs or web sources into structured JSON outputs.

---

## 🗂️ Project Overview

```
PDFs / Web
    │
    ▼
[1] PDF Text Extraction   ──► pymupdff.py  (PyMuPDF — native text)
                          ──► doclingg.py  (Docling — OCR for scanned PDFs)
    │
    ▼
[2] Web Scraping (optional) ──► scrap.py   (crawl4ai + BeautifulSoup)
    │
    ▼
[3] Page Splitting        ──► split.py     (logical pages + preamble detection)
    │
    ▼
[4] Document Profiling
    ├── regexx.py         (Regex-only — fast, deterministic)
    └── hybrid.py         (Regex + Gemini AI — fills metadata gaps)
    │
    ▼
Structured JSON outputs (metadata + structure)
```

---

## 📁 Repository Structure

```
.
├── PDFs/                        # Input PDF files
├── Clean_Text/                  # Raw scraped/extracted text
├── Splits/                      # Logically split .txt files
├── PyMuPDF Output/              # Markdown output from PyMuPDF
├── Docling Output/              # Markdown output from Docling (OCR)
├── Regex Only Output/           # JSON outputs from regex profiler
├── Hybrid Output (AI & Regex)/  # JSON outputs from hybrid profiler
│
├── pymupdff.py                  # PDF → Markdown (native text layer)
├── doclingg.py                  # PDF → Markdown (OCR via Docling + EasyOCR)
├── scrap.py                     # Web scraper for uaelegislation.gov.ae
├── split.py                     # Splits cleaned text into logical pages
├── regexx.py                    # Regex-only document profiler
└── hybrid.py                    # Hybrid profiler (Regex + Gemini AI)
```

---

## ⚙️ Setup & Installation

### Prerequisites

- Python 3.10+
- pip

### Install Dependencies

```bash
pip install pymupdf docling crawl4ai beautifulsoup4 google-generativeai
```

For `crawl4ai` browser support:

```bash
playwright install
```

---

## 🚀 Usage

### Step 1 — Extract Text from PDFs

**Option A: PyMuPDF** (fast, works on PDFs with a native text layer)

```bash
python pymupdff.py
```

> Reads from `PDFs/`, outputs `.md` files to `PyMuPDF Output/`

**Option B: Docling + EasyOCR** (for scanned/image-based Arabic PDFs)

```bash
python doclingg.py
```

> Reads from `PDFs/`, outputs `.md` files to `Docling Output/`

---

### Step 2 — Scrape Laws from the Web (optional)

```bash
python scrap.py
```

> Fetches laws from `uaelegislation.gov.ae` and saves cleaned text to `Clean_Text/`

---

### Step 3 — Split into Logical Pages

```bash
python split.py
```

> Reads `.txt` files from `Clean_Text/`, splits them at structural markers (الباب / الفصل / المادة), and saves paged `.txt` files + metadata `.json` to `Splits/`

---

### Step 4 — Profile & Structure Documents

**Option A: Regex-only** (no API key required, deterministic)

```bash
python regexx.py
```

**Option B: Hybrid (Regex + Gemini AI)** (richer metadata, AI-corrected counts)

1. Set your Gemini API key in `hybrid.py`:
   ```python
   GEMINI_API_KEY = "your-api-key-here"
   ```
2. Run:
   ```bash
   python hybrid.py
   ```

> Both profilers read from `Splits/` and output `*_metadata.json` + `*_structure.json` per document.

---

## 📤 Output Schema

Each processed document produces two JSON files:

### `*_metadata.json`

| Field | Description |
|---|---|
| `document_id` | UUID for the document |
| `title` | Law subject (extracted from بشأن clause) |
| `law_number` | Official reference number |
| `document_type` | e.g. Federal Law, Decree-Law |
| `jurisdiction` | e.g. UAE |
| `language` | Arabic |
| `effective_date` | YYYY-MM-DD |
| `status` | e.g. in_force |

### `*_structure.json`

| Field | Description |
|---|---|
| `total_nodes` | Total structural units found |
| `parts_extracted` | Count of أبواب (Parts) |
| `chapters_extracted` | Count of فصول (Chapters) |
| `articles_extracted` | Count of مواد (Articles) |
| `has_preamble` | Boolean |
| `hierarchy` | Ordered structural layers |
| `structural_vocabulary` | Patterns found with regex and counts |

---

## 🧩 Supported Document Structures

| Arabic | English | Level |
|---|---|---|
| الباب | Part | 1 |
| الفصل | Chapter | 2 |
| المادة | Article | 3 |

---

## 🤖 Hybrid Profiling Strategy

`hybrid.py` uses a two-layer approach for maximum accuracy:

- **Layer 1 (Regex):** Deterministic extraction of structure, law numbers, dates, and document types using compiled regular expressions.
- **Layer 2 (Gemini AI):** Fills in fields that regex cannot reliably extract (title, formatted law number, document type) and optionally corrects structural counts.
- **Layer 3 (Merge):** AI corrections are applied on top of regex results, with each field tagged by its extraction method (`ai` / `regex` / `regex+ai_corrected`).

---

## ⚠️ Notes

- The Gemini API key in `hybrid.py` should be replaced with your own key and kept out of version control. Consider using environment variables:
  ```python
  import os
  GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
  ```
- Docling OCR can be slow on large PDFs without a GPU. Set `use_gpu=True` in `doclingg.py` if a CUDA GPU is available.
- `pymupdff.py` will warn if a PDF has no native text layer (image-only PDFs need Docling instead).
