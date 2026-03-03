#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

import os
import sys
from pathlib import Path


def delete_scoring_files(directory: Path) -> None:
    keywords = ("sg", "scoring")
    deleted = []
    skipped = []

    for file in directory.iterdir():
        if not file.is_file():
            continue
        name_lower = file.name.lower()
        if any(kw in name_lower for kw in keywords):
            try:
                file.unlink()
                deleted.append(file.name)
            except OSError as e:
                skipped.append((file.name, str(e)))

    if deleted:
        print(f"Deleted {len(deleted)} file(s):")
        for name in deleted:
            print(f"  - {name}")
    else:
        print("No matching files found.")

    if skipped:
        print(f"\nFailed to delete {len(skipped)} file(s):")
        for name, err in skipped:
            print(f"  - {name}: {err}")


def main() -> None:
    if len(sys.argv) > 1:
        directory = Path(sys.argv[1])
    else:
        directory = Path(input("Enter directory path: ").strip())

    if not directory.exists():
        print(f"Error: '{directory}' does not exist.")
        sys.exit(1)
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory.")
        sys.exit(1)

    matches = [
        f for f in directory.iterdir()
        if f.is_file() and any(kw in f.name.lower() for kw in ("sg", "scoring"))
    ]

    if not matches:
        print("No matching files found.")
        return

    print(f"Found {len(matches)} file(s) to delete in '{directory}':")
    for f in matches:
        print(f"  - {f.name}")

    confirm = input("\nDelete these files? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    delete_scoring_files(directory)


if __name__ == "__main__":
    main()
