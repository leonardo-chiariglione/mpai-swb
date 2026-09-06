"""
Script: Global String Replace in JSON Files (Recursive)

Purpose
-------
Replace all occurrences of a user-defined string (STRING1)
with another string (STRING2) across all JSON files under
a specified base directory.

Behavior
--------
- Prompts the user for:
    • STRING1 (text to find)
    • STRING2 (replacement text)
- Recursively scans ALL folders under BASE_DIR
- Processes only ".json" files
- Searches for exact matches of STRING1 (literal, case-sensitive)
- Reports each file where STRING1 is found
- Replaces ALL occurrences of STRING1 with STRING2
- Writes file back ONLY if changes are made

Output
------
- For each modified file:
    • file path
    • number of replacements
- Summary statistics:
    • total files scanned
    • files modified
    • total replacements performed

Error Handling
--------------
- Uses UTF-8 decoding (safe for most JSON files)
- Catches file errors and continues processing

Scope
-----
- Entire BASE_DIR directory tree
- All nested subfolders included

Notes
-----
- Replacement is literal (no regex)
- Matching is case-sensitive
- Files are modified in place → use version control or backup
"""

import os

# ==============================
# CONFIGURATION
# ==============================

BASE_DIR = r"C:\Users\Leonardo\OneDrive - CEDEO\My Standards\mpai\schemas"

# ==============================
# USER INPUT
# ==============================

print("\n=== GLOBAL STRING REPLACEMENT ===")
print(f"Base directory:\n{BASE_DIR}")

STRING1 = input("\nEnter STRING1 (text to find): ").strip()
STRING2 = input("Enter STRING2 (replacement): ").strip()

if not STRING1:
    print("\n❌ STRING1 cannot be empty.")
    exit()

# ==============================
# PROCESSING
# ==============================

files_scanned = 0
files_modified = 0
total_replacements = 0

print("\nScanning and replacing...\n")

for root, _, files in os.walk(BASE_DIR):
    for file in files:
        if not file.endswith(".json"):
            continue

        file_path = os.path.join(root, file)
        files_scanned += 1

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if STRING1 in content:
                count = content.count(STRING1)

                print(f"MODIFY: {file_path}")
                print(f"  -> Replacements: {count}")

                new_content = content.replace(STRING1, STRING2)

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

                files_modified += 1
                total_replacements += count

        except Exception as e:
            print(f"ERROR processing {file_path}: {e}")

# ==============================
# SUMMARY
# ==============================

print("\n--- SUMMARY ---")
print(f"Files scanned:      {files_scanned}")
print(f"Files modified:     {files_modified}")
print(f"Total replacements: {total_replacements}")

print("\n✅ Done.")
