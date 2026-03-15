import os
import re
import json

input_folder = "Clean_Text"
output_folder = "Cleaned & Splitted"
max_chars_per_page = 2000

# Create the output folder if it doesn't exist
os.makedirs(output_folder, exist_ok=True)

def split_text_into_pages_by_chars(text, max_chars_per_page=2000):
    bab_pattern = re.compile(r"^الباب\s+\S+")
    fasl_pattern = re.compile(r"^الفصل\s+\S+")
    mada_pattern = re.compile(r"^المادة\s*\(\d+\)")

    lines = text.split("\n")

    pages = []
    current_page = []
    current_length = 0
    page_number = 1

    # Capture preface content until the first structural marker is found
    first_structural_found = False
    preface_page = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Introduction content before the first structural marker
        if not first_structural_found:
            if bab_pattern.match(line) or fasl_pattern.match(line) or mada_pattern.match(line):
                first_structural_found = True
                if preface_page:
                    pages.append((0, preface_page))
            else:
                preface_page.append(line)
                continue

        # If adding the line exceeds the max chars per page, start a new page
        if current_length + len(line) > max_chars_per_page and current_page:
            pages.append((page_number, current_page))
            page_number += 1
            current_page = []
            current_length = 0

        current_page.append(line)
        current_length += len(line) + 1  # +1 for the newline character

    # Add the last page if it has content
    if current_page:
        pages.append((page_number, current_page))

    return pages

def write_pages(pages, output_file):
    with open(output_file, "w", encoding="utf-8") as f:
        for num, content in pages:
            if num == 0:
                f.write(f"\n=== صفحة المقدمة ===\n\n")
            else:
                f.write(f"\n=== صفحة {num} ===\n\n")
            f.write("\n".join(content))
            f.write("\n")

# Process each TXT file in the input folder
for filename in os.listdir(input_folder):
    if filename.lower().endswith(".txt"):
        input_path = os.path.join(input_folder, filename)
        with open(input_path, "r", encoding="utf-8") as f:
            text = f.read()

        # Split the text into pages based on character count and structural markers
        pages = split_text_into_pages_by_chars(text, max_chars_per_page)

        # Save the split pages to a new TXT file in the output folder
        output_txt_path = os.path.join(output_folder, filename)
        write_pages(pages, output_txt_path)
        print(f"{filename} → {output_txt_path}")

        # Create a JSON metadata file for the processed document
        json_data = {
            "document_id": "",
            "file_name": filename,
            "total_pages": len(pages),
            "strategy_used": "marker_detection",
            "page_boundary_type": "logical",
            "corresponds_to_pdf_page": False,
            "message": "processed"
        }

        output_json_path = os.path.join(output_folder, f"{os.path.splitext(filename)[0]}.json")
        with open(output_json_path, "w", encoding="utf-8") as jf:
            json.dump(json_data, jf, ensure_ascii=False, indent=2)

        print(f"{filename} → {output_json_path}")