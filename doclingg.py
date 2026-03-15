from pathlib import Path
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
from docling.document_converter import PdfFormatOption

# ═══════════════════════════════════════════════════════════════
#  PATHS  —  edit these two lines only
# ═══════════════════════════════════════════════════════════════
INPUT_FOLDER  = Path("PDFs")           # folder that contains your 3 PDFs
OUTPUT_FOLDER = Path("Docling Output")    # extracted .md files go here
# ═══════════════════════════════════════════════════════════════


def build_converter() -> DocumentConverter:
    ocr_options = EasyOcrOptions(
        lang=["ar"],   # Arabic docs
        use_gpu=False,       # set True if you have a CUDA GPU
    )
    pipeline_options = PdfPipelineOptions(
        do_ocr=True,
        do_table_structure=True,
        ocr_options=ocr_options,
    )
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )


def extract_pdf(converter: DocumentConverter, pdf_path: Path, out_dir: Path) -> None:
    print(f"\n📄 Processing: {pdf_path.name}")

    result = converter.convert(str(pdf_path))   # no page limit — full file
    text   = result.document.export_to_markdown()

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

    converter = build_converter()

    for pdf in pdf_files:
        try:
            extract_pdf(converter, pdf, OUTPUT_FOLDER)
        except Exception as e:
            print(f"   ⚠️  Failed [{pdf.name}]: {e}")

    print("\n🎉 Done! Check the output folder for your .md files.")


if __name__ == "__main__":
    main()