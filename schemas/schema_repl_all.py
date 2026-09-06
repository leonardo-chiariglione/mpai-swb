import os
import json

"""
FUNCTIONAL DESCRIPTION

This script synchronizes JSON schemas with their corresponding Basic schemas
within a specified subfolder.

It:
- Scans a subfolder for JSON files
- Identifies matching pairs:
    - Target file:        <Name>.json
    - Basic template:     Basic<Name>.json
- For each matching pair:
    - Loads both JSON files
    - Replaces the full structure of the target file with the Basic schema
    - Preserves selected fields from the original target:
        - $id
        - title
        - properties.Header (if present)
- Writes the updated schema back to the original target file

Purpose:
- Ensure structural consistency across schemas
- Enforce use of Basic schema templates
- Retain identity and header definitions specific to each schema

Key characteristics:
- Works at JSON object level (not raw text)
- Automatically processes all matching schema pairs in the folder
- Skips files without corresponding Basic templates
"""

BASE_PATH = r"C:\Users\Leonardo\OneDrive - CEDEO\My Standards\mpai\schemas"


def main():
    subfolder = input("Enter subfolder name: ").strip()
    folder_path = os.path.join(BASE_PATH, subfolder)

    print("\nUsing folder:", folder_path)

    if not os.path.isdir(folder_path):
        print("ERROR: folder not found")
        return

    files = os.listdir(folder_path)

    basic_files = {
        f.replace("Basic", "")
        for f in files
        if f.startswith("Basic") and f.endswith(".json")
    }

    print("\nProcessing matching pairs...\n")

    for file in files:
        if not file.endswith(".json"):
            continue

        if file.startswith("Basic"):
            continue

        if file not in basic_files:
            continue

        target_file = os.path.join(folder_path, file)
        basic_file = os.path.join(folder_path, "Basic" + file)

        # --- Load JSONs safely ---
        with open(target_file, "r", encoding="utf-8") as f:
            target = json.load(f)

        with open(basic_file, "r", encoding="utf-8") as f:
            basic = json.load(f)

        # --- Preserve fields ---
        if "$id" in target:
            basic["$id"] = target["$id"]

        if "title" in target:
            basic["title"] = target["title"]

        if "properties" in target and "Header" in target["properties"]:
            if "properties" not in basic:
                basic["properties"] = {}
            basic["properties"]["Header"] = target["properties"]["Header"]

        # --- Write result ---
        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(basic, f, indent=2)

        print(f"✔ Processed {file}")

    print("\n✔ DONE")


if __name__ == "__main__":
    main()