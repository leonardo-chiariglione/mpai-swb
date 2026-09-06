import os
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox

r"""
===============================================================================
REPLACE STRING IN DIRECTORY TOOL (GUI VERSION)
===============================================================================

FUNCTIONAL DESCRIPTION
---------------------
This tool performs a recursive string replacement in all text files located in
a selected folder and all its subfolders.

- It is designed to work inside the MPAI schemas directory:
  C:\Users\Leonardo\OneDrive - CEDEO\My Standards\mpai\schemas

- It replaces ALL occurrences of a given string (string1) with another string
  (string2) across all readable files.

- Binary or unreadable files are automatically skipped.

-------------------------------------------------------------------------------

USAGE STEPS
-----------
1. Run the script (double-click or run with Python)

2. Select a folder:
   - A folder selection window will open
   - It starts inside the schemas directory
   - Example selections:
       XRV1
       XRV1\V1.0

3. Enter the strings:
   - First popup → string to replace
   - Second popup → replacement string

4. Confirm operation:
   - A summary dialog is shown
   - Click YES to proceed

5. Result:
   - All matching files are updated
   - A final message shows how many files were modified

-------------------------------------------------------------------------------

NOTES / BEHAVIOR
----------------
- Only files containing the search string are modified
- Files are processed as UTF-8 text
- Non-text files are ignored safely
- Replacement is case-sensitive
- Replacement is global (all occurrences in each file)

-------------------------------------------------------------------------------

TYPICAL USE CASES
-----------------
- Updating schema version strings across many files
- Changing reference URLs or identifiers
- Bulk renaming JSON keys or values
- Migrating specification text across folder trees

-------------------------------------------------------------------------------

IMPORTANT LIMITATIONS
---------------------
- No undo: changes are written directly to files
- No preview: modifications are applied immediately after confirmation
- Case-sensitive matching (no automatic case handling)

-------------------------------------------------------------------------------

RECOMMENDATION
--------------
Before performing large operations:
- Ensure your files are under version control (e.g., Git)
- Or manually copy the folder as backup

===============================================================================
"""

# ✅ Base directory
BASE_DIR = r"C:\Users\Leonardo\OneDrive - CEDEO\My Standards\mpai\schemas"

# Start GUI
root = tk.Tk()
root.withdraw()

# ✅ Select folder
folder = filedialog.askdirectory(
    title="Select folder under schemas",
    initialdir=BASE_DIR
)

if not folder:
    messagebox.showinfo("Cancelled", "No folder selected")
    exit()

# ✅ Robust path validation
base_real = os.path.realpath(BASE_DIR)
folder_real = os.path.realpath(folder)

try:
    common = os.path.commonpath([base_real, folder_real])
except ValueError:
    common = ""

if common != base_real:
    messagebox.showerror(
        "Error",
        f"Folder must be inside:\n{BASE_DIR}\n\nSelected:\n{folder}"
    )
    exit()

# ✅ Input strings
string1 = simpledialog.askstring("Input", "Enter string to replace:")
if string1 is None:
    exit()

string2 = simpledialog.askstring("Input", "Enter replacement string:")
if string2 is None:
    exit()

# ✅ Confirmation
confirm = messagebox.askyesno(
    "Confirm",
    f"Replace:\n\n{string1}\n\nWITH:\n\n{string2}\n\nIN:\n{folder}\n\nProceed?"
)

if not confirm:
    exit()

# ✅ Processing
files_modified = 0

for root_dir, dirs, files in os.walk(folder):
    for file in files:
        path = os.path.join(root_dir, file)

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            if string1 in content:
                new_content = content.replace(string1, string2)

                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)

                files_modified += 1

        except Exception:
            # Skip unreadable or binary files
            pass

# ✅ Result
messagebox.showinfo("Done", f"Files modified: {files_modified}")