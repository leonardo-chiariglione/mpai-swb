"""
Script: JSON String Search with Line Reporting (Full Directory)

Purpose
-------
Identify all JSON files under a base directory that contain a
user-specified string and report the exact line numbers where
the string occurs.

Behavior
--------
- Prompts the user for a string to search
- Recursively scans ALL folders under BASE_DIR
- Processes only ".json" files
- Reads files line by line (efficient for large files)
- Reports every occurrence found in each file
- For each match:
    • file path
    • line number

Output
------
- Prints each match as:
    ✅ <file path> : line <number>
- Displays a summary:
    • total files scanned
    • files containing the string
    • total matches

Error Handling
--------------
- Uses UTF-8 decoding with errors="ignore"
- Continues processing even if a file cannot be read

Scope
-----
- Entire BASE_DIR directory tree
- All nested subfolders included automatically

Notes
-----
- Search is literal (no regex)
- Matching is case-sensitive
- Reports all occurrences (not just first match)
"""

import os

BASE_DIR = r"C:\Users\Leonardo\OneDrive - CEDEO\My Standards\mpai\schemas"


def search_in_file(path, search_string):
    matches = 0
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line_number, line in enumerate(f, start=1):
                if search_string in line:
                    print(f"✅ {path} : line {line_number}")
                    matches += 1
    except Exception as e:
        print(f"❌ Error: {path}")
        print(e)
    return matches


def main():
    print("=== JSON STRING SEARCH (LINE MODE) ===")
    print("Scanning base directory:")
    print(BASE_DIR)

    search_string = input("\nEnter string to search: ").strip()

    if not search_string:
        print("\n❌ No search string provided.")
        return

    print("\nScanning...\n")

    files_scanned = 0
    files_with_match = 0
    total_matches = 0

    for root, _, files in os.walk(BASE_DIR):
        for name in files:
            if name.endswith(".json"):
                files_scanned += 1
                file_path = os.path.join(root, name)

                matches = search_in_file(file_path, search_string)

                if matches > 0:
                    files_with_match += 1
                    total_matches += matches

    print("\n--- SUMMARY ---")
    print(f"Files scanned:         {files_scanned}")
    print(f"Files containing text: {files_with_match}")
    print(f"Total matches:         {total_matches}")

    print("\n✅ Done.")


if __name__ == "__main__":
    main()
