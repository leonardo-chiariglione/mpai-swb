import os
import re

BASE_PATH = r"C:\Users\Leonardo\OneDrive - CEDEO\My Standards\mpai\schemas"

def extract_field(text, field):
    pattern = rf'"{field}"\s*:\s*("[^"]*"|\{{.*?\}}|\[.*?\]|[^,\n]+)'
    match = re.search(pattern, text, re.DOTALL)
    return match.group(0) if match else None

def replace_field(text, field, new_line):
    pattern = rf'"{field}"\s*:\s*("[^"]*"|\{{.*?\}}|\[.*?\]|[^,\n]+)'
    return re.sub(pattern, new_line, text, count=1, flags=re.DOTALL)

def main():
    subfolder = input("Enter subfolder name: ").strip()
    schema_name = input("Enter schema name (e.g., AudioObject): ").strip()

    folder_path = os.path.join(BASE_PATH, subfolder)

    target_file = os.path.join(folder_path, f"{schema_name}.json")
    basic_file = os.path.join(folder_path, f"Basic{schema_name}.json")

    if not os.path.exists(target_file):
        print(f"Error: {schema_name}.json not found")
        return

    if not os.path.exists(basic_file):
        print(f"Error: Basic{schema_name}.json not found")
        return

    with open(target_file, "r", encoding="utf-8") as f:
        target_text = f.read()

    with open(basic_file, "r", encoding="utf-8") as f:
        basic_text = f.read()

    id_line = extract_field(target_text, "id")
    title_line = extract_field(target_text, "title")

    if id_line:
        basic_text = replace_field(basic_text, "id", id_line)

    if title_line:
        basic_text = replace_field(basic_text, "title", title_line)

    with open(target_file, "w", encoding="utf-8") as f:
        f.write(basic_text)

    print("\n✔ Success (format preserved)")
    print(f"Updated: {schema_name}.json")

if __name__ == "__main__":
    main()
