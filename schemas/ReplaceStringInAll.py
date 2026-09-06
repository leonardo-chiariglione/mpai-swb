import os

# =========================================================
# FUNCTIONAL DESCRIPTION
# =========================================================
# This script performs a recursive search-and-replace operation
# across all JSON files under a specified base directory.
#
# The user is prompted to provide:
#   1. A target string to search for
#   2. A replacement string
#
# The script:
#   • Traverses all subfolders of BASE_DIR
#   • Processes only files with ".json" extension
#   • Counts occurrences of the target string in each file
#   • Replaces all occurrences with the replacement string
#   • Updates files only if at least one match is found
#
# Output:
#   • Lists files where matches are found
#   • Reports number of replacements per file
#   • Provides a final summary of:
#         - Files scanned
#         - Files modified
#         - Total replacements
#
# Verification step:
#   • Re-scans all processed files to ensure no occurrences remain
#   • Reports success or lists files still containing the string
#
# Notes:
#   • This script performs literal string replacement (no regex)
#   • Processing is case-sensitive
#   • Files are overwritten in-place (no backup is created)
# =========================================================


# ==============================
# CONFIGURATION
# ==============================

BASE_DIR = r"C:\Users\Leonardo\OneDrive - CEDEO\My Standards\mpai\schemas"

# Ask user for input strings
find_string = input("Enter the string to find: ").strip()
replace_string = input("Enter the replacement string: ").strip()

# ==============================
# PROCESSING
# ==============================

files_scanned = 0
files_modified = 0
total_replacements = 0

print("\nScanning for occurrences...\n")

for root, dirs, files in os.walk(BASE_DIR):
    for file in files:
        if not file.endswith(".json"):
            continue

        file_path = os.path.join(root, file)
        files_scanned += 1

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            occurrences = content.count(find_string)

            if occurrences > 0:
                print(f"\nFOUND in: {file_path}")
                print(f"Occurrences: {occurrences}")

                new_content = content.replace(find_string, replace_string)

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

                print(f"REPLACED {occurrences} occurrence(s)")

                files_modified += 1
                total_replacements += occurrences

        except Exception as e:
            print(f"ERROR processing {file_path}: {e}")

# ==============================
# FINAL CHECK
# ==============================

print("\n--- SUMMARY ---")
print(f"Files scanned:      {files_scanned}")
print(f"Files modified:     {files_modified}")
print(f"Total replacements: {total_replacements}")

print("\nRunning final verification...\n")

remaining_issues = []

for root, dirs, files in os.walk(BASE_DIR):
    for file in files:
        if file.endswith(".json"):
            file_path = os.path.join(root, file)

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                if find_string in content:
                    remaining_issues.append(file_path)

            except Exception as e:
                print(f"ERROR during verification {file_path}: {e}")

if not remaining_issues:
    print("✅ SUCCESS: No remaining occurrences found.")
else:
    print("❌ REMAINING FILES STILL CONTAINING THE STRING:")
    for f in remaining_issues:
        print(f"  -> {f}")