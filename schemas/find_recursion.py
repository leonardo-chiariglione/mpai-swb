print("=== INTERACTIVE MODE ===")

import os
import json
import sys

# =====================================================
# BASE FOLDER
# =====================================================
BASE_DIR = r"C:\Users\Leonardo\OneDrive - CEDEO\My Standards\mpai\schemas"

# =====================================================
# ASK USER
# =====================================================
SUB_DIR = input("Enter subfolder after 'schemas': ").strip()
ROOT_DIR = os.path.join(BASE_DIR, SUB_DIR)

print(f"\n✅ Full path:\n{ROOT_DIR}\n")

if not os.path.exists(ROOT_DIR):
    print("❌ Folder does not exist.")
    exit()

# =====================================================
# REPORT FILE + SCREEN OUTPUT
# =====================================================
log = open("recursion_report.txt", "w", encoding="utf-8")

class Tee:
    def write(self, s):
        sys.__stdout__.write(s)
        log.write(s)
    def flush(self):
        log.flush()

sys.stdout = Tee()

# =====================================================
# HELPER: extract all $ref values
# =====================================================
def extract_refs(obj, refs):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "$ref" and isinstance(v, str):
                refs.append(v)
            else:
                extract_refs(v, refs)
    elif isinstance(obj, list):
        for item in obj:
            extract_refs(item, refs)

# =====================================================
# FINAL RECURSION DETECTOR
# Detects:
# - same-file recursion via URL (independent of data/nrdata)
# - $defs self-reference
# =====================================================
def detect_internal_recursion(file_path, data):
    refs = []
    extract_refs(data, refs)

    filename = os.path.basename(file_path).lower()
    defs = data.get("$defs", {})

    for ref in refs:
        ref_name = ref.split("/")[-1].lower()

        # ✅ Case 1: same-file recursion (core fix)
        if ref_name == filename:
            return True

        # ✅ Case 2: $defs recursion
        if ref.startswith("#/$defs/"):
            def_name = ref.split("/")[-1]
            if def_name in defs and ref == f"#/$defs/{def_name}":
                return True

    return False

# =====================================================
# SCAN FILES
# =====================================================
all_files = []

for current_dir, _, files in os.walk(ROOT_DIR):
    for file in files:
        if file.endswith(".json"):
            all_files.append(os.path.join(current_dir, file))

# =====================================================
# PROCESS FILES
# =====================================================
files_with_recursion = []

for file_path in all_files:
    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        if detect_internal_recursion(file_path, data):
            files_with_recursion.append(file_path)

    except Exception as e:
        print(f"Error: {file_path} → {e}")

# =====================================================
# FINAL REPORT
# =====================================================
print("\n==============================")
print("FILES WITH INTERNAL RECURSION")
print("==============================\n")

if files_with_recursion:
    for f in files_with_recursion:
        print(f)
else:
    print("No recursion detected.")

print("\n✅ Done.")