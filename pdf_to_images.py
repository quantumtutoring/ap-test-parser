#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pdf2image",
# ]
# ///
"""Convert all PDFs in a folder to PNG images. python pdf_to_images.py /path/to/folder/with/pdfs"""

import argparse
import sys
from pathlib import Path

from pdf2image import convert_from_path
from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPageCountError


def get_pdf_files(folder_path: Path) -> list[Path]:
    """Return list of PDF file paths in the given folder."""
    return sorted(folder_path.glob("*.pdf"))


def convert_pdf_to_images(pdf_path: Path, output_dir: Path) -> int:
    """Convert a single PDF to PNG images and save to output directory.

    Returns the number of pages converted.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    images = convert_from_path(pdf_path)

    for i, image in enumerate(images, start=1):
        output_path = output_dir / f"page_{i}.png"
        image.save(output_path, "PNG")

    return len(images)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert all PDFs in a folder to PNG images."
    )
    parser.add_argument(
        "folder",
        type=Path,
        help="Path to folder containing PDF files",
    )
    args = parser.parse_args()

    folder_path = args.folder.resolve()

    if not folder_path.exists():
        print(f"Error: Folder does not exist: {folder_path}", file=sys.stderr)
        return 1

    if not folder_path.is_dir():
        print(f"Error: Path is not a directory: {folder_path}", file=sys.stderr)
        return 1

    pdf_files = get_pdf_files(folder_path)

    if not pdf_files:
        print(f"No PDF files found in {folder_path}")
        return 0

    print(f"Found {len(pdf_files)} PDF file(s) in {folder_path}")

    succeeded = []
    failed = []

    for pdf_path in pdf_files:
        output_dir = folder_path / pdf_path.stem
        print(f"Converting: {pdf_path.name} -> {output_dir.name}/")

        try:
            page_count = convert_pdf_to_images(pdf_path, output_dir)
            succeeded.append((pdf_path.name, page_count))
            print(f"  Saved {page_count} page(s)")
        except PDFInfoNotInstalledError:
            print(
                "Error: poppler-utils is not installed. "
                "Install with: brew install poppler",
                file=sys.stderr,
            )
            return 1
        except PDFPageCountError as e:
            failed.append((pdf_path.name, str(e)))
            print(f"  Failed: {e}", file=sys.stderr)
        except Exception as e:
            failed.append((pdf_path.name, str(e)))
            print(f"  Failed: {e}", file=sys.stderr)

    print()
    print(f"Summary: {len(succeeded)} succeeded, {len(failed)} failed")

    if failed:
        print("Failed files:")
        for name, error in failed:
            print(f"  - {name}: {error}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
