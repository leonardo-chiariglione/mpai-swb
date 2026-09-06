import os
import re

"""
FUNCTIONAL DESCRIPTION

This script updates a target JSON schema using its corresponding Basic schema.

It:
- Loads a target schema (e.g., AudioObject.json)
- Loads the corresponding Basic schema (e.g., BasicAudioObject.json)
- Copies the full structure from the Basic schema
- Preserves the original $id and title from the target schema
- Replaces only the values of $id and title while keeping alignment unchanged

Key characteristic:
- Operates on raw text (not parsed JSON) to preserve exact formatting and alignment
- Ensures schema normalization using Basic templates without altering layout
"""

BASE_PATH = r"C:\Users\Leonardo\OneDrive - CEDEO\My Standards\mpai\schemas"


# --- Extract full field line (kept exactly) ---
def extract_field(text, field):
    pattern = rf'"{re.escape(field)}"\s*:\s*(".*?"|\{{.*?\}}|\[.*?\]|[^,\n]+)'
    match = re.search(pattern, text, re.DOTALL)
    return match.group(0) if match else None


# --- Replace ONLY the value (preserves alignment) ---
def replace_value(text, field, new_line):
    # Extract only the value part
    value_match = re.search(r':\s*(.*)', new_line)
    if not value_match:
        return text

    new_value = value_match.group(1).strip()

    # Replace only the value, keep formatting from Basic file
    pattern = rf'("{re.escape(field)}"\s*:\s*)(.*?)(?=,\n|\n|\r\n)'

    def replacer(match):
        return match.group(1) + new_value

    return re.sub(pattern, replacer, text, count=1)


def main():
    subfolder   = input("Enter subfolder name: ").strip()
    schema_name = input("Enter schema name (e.g., AudioObject): ").strip()

    folder_path = os.path.join(BASE_PATH, subfolder)

    print("\nUsing folder:", folder_path)

    if not os.path.isdir(folder_path):
        print("ERROR: folder not found")
        return

    target_file = os.path.join(folder_path, f"{schema_name}.json")
    basic_file  = os.path.join(folder_path, f"Basic{schema_name}.json")

    print("Target file:", target_file)
    print("Basic file :", basic_file)

    # --- Check files ---
    if not os.path.exists(target_file):
        print(f"\nERROR: {schema_name}.json not found")
        print("\nAvailable JSON files:")
        for f in os.listdir(folder_path):
            if f.endswith(".json"):
                print(" -", f)
        return

    if not os.path.exists(basic_file):
        print(f"\nERROR: Basic{schema_name}.json not found")
        return

    # --- Read files as text (preserve formatting) ---
    with open(target_file, "r", encoding="utf-8") as f:
        target_text = f.read()

    with open(basic_file, "r", encoding="utf-8") as f:
        basic_text = f.read()

    # --- Extract original values ---
    id_line    = extract_field(target_text, "$id") or extract_field(target_text, "id")
    title_line = extract_field(target_text, "title")

    if not id_line:
        print("WARNING: $id not found in original file")
    if not title_line:
        print("WARNING: title not found in original file")

    # --- Start from Basic schema ---
    new_text = basic_text

    # --- Replace ONLY values (preserve alignment) ---
    if id_line:
        new_text = replace_value(new_text, "$id", id_line)

    if title_line:
        new_text = replace_value(new_text, "title", title_line)

    # --- Write back ---
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(new_text)

    print("\n✔ SUCCESS")
    print("✔ Structure copied from Basic schema")
    print("✔ $id preserved from original")
    print("✔ title preserved from original")
    print("✔ Alignment preserved")


if __name__ == "__main__":
    main()