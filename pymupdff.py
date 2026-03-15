from pathlib import Path
import fitz  # PyMuPDF  

# ═══════════════════════════════════════════════════════════════
#  PATHS  —  edit these two lines only
# ═══════════════════════════════════════════════════════════════
INPUT_FOLDER  = Path("PDFs")
OUTPUT_FOLDER = Path("PyMuPDF Output")   
# ═══════════════════════════════════════════════════════════════


def pdf_to_markdown(pdf_path: Path) -> str:
    """Extract all text from a PDF and format it as markdown."""
    doc = fitz.open(str(pdf_path))
    pages_md = []

    for page_num, page in enumerate(doc, start=1):
        try:
            text = page.get_text("text").strip()
        except Exception as e:
            print(f"   ⚠️  Skipping page {page_num}: {e}")
            continue

        if not text:
            continue

        pages_md.append(f"## Page {page_num}\n\n{text}")

    doc.close()
    return "\n\n---\n\n".join(pages_md)


def extract_pdf(pdf_path: Path, out_dir: Path) -> None:
    print(f"\n📄 Processing: {pdf_path.name}")

    text = pdf_to_markdown(pdf_path)

    if not text.strip():
        print(f"   ⚠️  No text extracted — PDF may be image-only (needs OCR)")
        return

    out_file = out_dir / (pdf_path.stem + ".md")
    out_file.write_text(text, encoding="utf-8")
    print(f"   ✅ Saved → {out_file}  ({len(text):,} characters)")


def main() -> None:
    if not INPUT_FOLDER.exists():
        print(f"❌ Input folder not found: {INPUT_FOLDER.resolve()}")
        return

    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(INPUT_FOLDER.glob("*.pdf"))
    if not pdf_files:
        print(f"❌ No PDFs found in: {INPUT_FOLDER.resolve()}")
        return

    print(f"🔍 Found {len(pdf_files)} PDF(s) in:  {INPUT_FOLDER.resolve()}")
    print(f"💾 Output folder:                     {OUTPUT_FOLDER.resolve()}")

    for pdf in pdf_files:
        try:
            extract_pdf(pdf, OUTPUT_FOLDER)
        except Exception as e:
            print(f"   ⚠️  Failed [{pdf.name}]: {e}")

    print("\n🎉 Done! Check the output folder for your .md files.")


if __name__ == "__main__":
    main()