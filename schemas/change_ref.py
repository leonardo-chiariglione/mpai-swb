"""
Script: Reference Path Normalizer (Binary Mode)

Purpose:
--------
Recursively scans JSON files in a specified subfolder and replaces
specific path segments with their normalized "nr*" equivalents.

Applied Transformations:
------------------------
- "/data"     → "/nrdata"
- "/actions"  → "/nractions"
- "/formats"  → "/nrformats"
- "/types"    → "/nrtypes"

Behavior:
---------
- Processes files in binary mode to avoid encoding issues
- Applies only exact byte-level replacements
- Updates files only if at least one replacement occurs
- Reports the number of replacements per file
- Leaves files unchanged if no matching patterns are found

Scope:
------
- Processes only files with ".json" extension
- Recursively traverses all subdirectories of the selected folder

Usage:
------
Run the script and provide a subfolder relative to BASE_DIR.

Example:
    MMM4\\V2.2\\actions

Notes:
------
- Matches ONLY exact patterns like "/formats"
- Does NOT modify variants such as "formats", "#/formats", or "../formats"
"""

import os

BASE_DIR = r"C:\Users\Leonardo\OneDrive - CEDEO\My Standards\mpai\schemas"


# Mapping of replacements
REPLACEMENTS = {
    b"/data": b"/nrdata",
    b"/actions": b"/nractions",
    b"/formats": b"/nrformats",
    b"/types": b"/nrtypes",
}


def process_file(path):
    try:
        with open(path, "rb") as f:
            content = f.read()

        updated = content
        total_count = 0

        # Apply all replacements
        for old, new in REPLACEMENTS.items():
            count = updated.count(old)
            if count > 0:
                updated = updated.replace(old, new)
                total_count += count

        if updated != content:
            print(f"Updating: {path}  (replacements: {total_count})")

            with open(path, "wb") as f:
                f.write(updated)

    except Exception as e:
        print(f"❌ Error: {path}")
        print(e)


def main():
    print("=== CHANGE REF (BINARY MODE) ===")
    print("Base directory:")
    print(BASE_DIR)

    subpath = input("\nEnter subfolder: ").strip()
    target = os.path.normpath(os.path.join(BASE_DIR, subpath))

    print("\nFull path:")
    print(target)

    if not os.path.isdir(target):
        print("\n❌ Invalid folder.")
        return

    print("\nProcessing...\n")

    for root, _, files in os.walk(target):
        for name in files:
            if name.endswith(".json"):
                process_file(os.path.join(root, name))

    print("\n✅ Done.")


if __name__ == "__main__":
    main()