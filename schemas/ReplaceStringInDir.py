"""
string_replace_recursive.py

USAGE:
--------------------------------------------------
1. Run the script:
   python string_replace_recursive.py

2. When prompted, enter:
   - Subfolder under schemas (example: pippo\pluto)
   - String to replace (string1)
   - Replacement string (string2)

3. What the script does:
   - Uses base directory:
     C:\Users\Leonardo\OneDrive - CEDEO\My Standards\mpai\schemas
   - Navigates to the selected subfolder
   - Recursively scans ALL files in that folder and subfolders
   - Replaces every occurrence of string1 with string2
   - Prints modified files
   - Shows total number of modified files

NOTES:
- Only files containing string1 are modified
- Files are processed as UTF-8 text
- Errors are skipped (e.g., binary files)
--------------------------------------------------
"""

import os

# 1. Base directory
base_dir = r"C:\Users\Leonardo\OneDrive - CEDEO\My Standards\mpai\schemas"

# 2. Request subfolder
subfolder = input("Enter subfolder under schemas (e.g. pippo\\pluto): ").strip()
target_dir = os.path.join(base_dir, subfolder)

if not os.path.exists(target_dir):
    print(f"ERROR: Directory does not exist: {target_dir}")
    exit(1)

# 3. Request string1 (to be replaced)
string1 = input("Enter string to replace: ")

# 4. Request string2 (replacement)
string2 = input("Enter replacement string: ")

# 5. Replace recursively
files_modified = 0

for root, dirs, files in os.walk(target_dir):
    for file in files:
        file_path = os.path.join(root, file)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if string1 in content:
                new_content = content.replace(string1, string2)

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)

                files_modified += 1
                print(f"Modified: {file_path}")

        except Exception as e:
            print(f"Skipped (error): {file_path} -> {e}")

print(f"\nDone. Files modified: {files_modified}")
