import json
import os

BASE_PATH = r"C:\Users\Leonardo\OneDrive - CEDEO\My Standards\mpai\schemas"

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    subfolder = input("Enter subfolder name: ").strip()
    schema_name = input("Enter schema name (e.g., AudioObject): ").strip()

    folder_path = os.path.join(BASE_PATH, subfolder)

    if not os.path.isdir(folder_path):
        print(f"Error: folder not found -> {folder_path}")
        return

    target_file = os.path.join(folder_path, f"{schema_name}.json")
    basic_file = os.path.join(folder_path, f"Basic{schema_name}.json")

    if not os.path.exists(target_file):
        print(f"Error: {schema_name}.json not found")
        return

    if not os.path.exists(basic_file):
        print(f"Error: Basic{schema_name}.json not found")
        return

    target_schema = load_json(target_file)
    basic_schema = load_json(basic_file)

    preserved_id = target_schema.get("id")
    preserved_title = target_schema.get("title")

    new_schema = json.loads(json.dumps(basic_schema))

    if preserved_id is not None:
        new_schema["id"] = preserved_id

    if preserved_title is not None:
        new_schema["title"] = preserved_title

    save_json(target_file, new_schema)

    print("\n✔ Success")
    print(f"Updated: {schema_name}.json")
    print(f"Using  : Basic{schema_name}.json")
    print("Preserved: id, title")

if __name__ == "__main__":
    main()
