"""
Script: Schema Merge with Value Preservation (FINAL)

Purpose:
--------
For each FileName.json:
- If BasicFileName.json exists:
    → Use BasicFileName.json as the structural base
    → Replace selected values using FileName.json

Applied Transformations:
------------------------
- Replace ONLY the values of:
    * "$id"
    * "title"

- For "Header":
    → DO NOT replace the whole object
    → ONLY replace the "pattern" value
    → Preserve type, description, and structure

Behavior:
---------
- Uses BasicFileName.json as base structure
- Preserves formatting and alignment exactly
- Skips silently if no matching Basic file
- Overwrites FileName.json with merged result
"""

import os
import re

BASE_DIR = r"C:\Users\Leonardo\OneDrive - CEDEO\My Standards\mpai\schemas"


def replace_value(text, key, new_value):
    """
    Replace ONLY the value of a key, preserving spacing/alignment.
    """
    match = re.search(rf'"{key}"\s*:\s*"[^"]*"', text)
    if not match:
        return text

    full = match.group(0)
    replaced = re.sub(r'"[^"]*"$', new_value, full)

    return text.replace(full, replaced, 1)


def merge_header(base, original):
    """
    Update ONLY the 'pattern' field of Header.
    Keep all other fields (type, description, etc.).
    """

    # pattern from original file
    orig_pattern = re.search(
        r'"Header"\s*:\s*\{.*?"pattern"\s*:\s*"([^"]*)"',
        original,
        re.DOTALL
    )

    # Header block in base file
    base_header = re.search(
        r'("Header"\s*:\s*\{.*?\})',
        base,
        re.DOTALL
    )

    if not (orig_pattern and base_header):
        return base

    pattern_value = orig_pattern.group(1)
    header_block = base_header.group(1)

    # replace ONLY pattern value inside base header
    updated_header = re.sub(
        r'("pattern"\s*:\s*)"[^"]*"',
        rf'\1"{pattern_value}"',
        header_block
    )

    return base.replace(header_block, updated_header, 1)


def process_file(path):
    try:
        filename = os.path.basename(path)

        # skip Basic files
        if filename.startswith("Basic"):
            return

        folder = os.path.dirname(path)
        base_path = os.path.join(folder, "Basic" + filename)

        # process only if Basic exists
        if not os.path.isfile(base_path):
            return

        with open(path, "r", encoding="utf-8") as f:
            original = f.read()

        with open(base_path, "r", encoding="utf-8") as f:
            base = f.read()

        # extract values from original
        id_match = re.search(r'"\$id"\s*:\s*(".*?")', original)
        title_match = re.search(r'"title"\s*:\s*(".*?")', original)

        if not (id_match and title_match):
            return

        id_value = id_match.group(1)
        title_value = title_match.group(1)

        # replace values (alignment preserved)
        base = replace_value(base, r'\$id', id_value)
        base = replace_value(base, 'title', title_value)

        # merge Header (pattern only)
        base = merge_header(base, original)

        with open(path, "w", encoding="utf-8") as f:
            f.write(base)

        print(f"✅ Updated: {path}")

    except Exception as e:
        print(f"❌ Error: {path}")
        print(e)


def main():
    subpath = input("Enter subfolder: ").strip()
    target = os.path.normpath(os.path.join(BASE_DIR, subpath))

    if not os.path.isdir(target):
        print("❌ Invalid folder.")
        return

    print("\nProcessing...\n")

    for root, _, files in os.walk(target):
        for name in files:
            if name.endswith(".json"):
                process_file(os.path.join(root, name))

    print("\n✅ Done.")


if __name__ == "__main__":
    main()