import os

BASE_DIR = r"C:\Users\Leonardo\OneDrive - CEDEO\My Standards\mpai\schemas"


def remove_bom(file_path):
    with open(file_path, "rb") as f:
        content = f.read()

    # UTF-8 BOM
    if content.startswith(b'\xef\xbb\xbf'):
        print(f"Removing BOM: {file_path}")
        content = content[3:]

        with open(file_path, "wb") as f:
            f.write(content)


def main():
    print("=== REMOVE BOM (FULL TREE) ===")
    print("Base directory:")
    print(BASE_DIR)
    print("\nProcessing all files...\n")

    for root, _, files in os.walk(BASE_DIR):
        for name in files:
            file_path = os.path.join(root, name)
            try:
                remove_bom(file_path)
            except Exception as e:
                print(f"❌ Error: {file_path}")
                print(e)

    print("\n✅ Done.")


if __name__ == "__main__":
    main()