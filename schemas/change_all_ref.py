import os

# ✅ Base directory (defined once)
BASE = r"C:\Users\Leonardo\OneDrive - CEDEO\My Standards\mpai\schemas"

# ✅ Target folders (derived safely from BASE)
TARGET_FOLDERS = [
    os.path.join(BASE, "AIF",  "V3.0", "nrdata"),
    os.path.join(BASE, "AIH1", "V1.0", "nrdata"),
    os.path.join(BASE, "AIP",  "V1.0", "nrdata"),
    os.path.join(BASE, "CAE1", "V2.4", "nrdata"),
    os.path.join(BASE, "CAV2", "V1.1", "nrdata"),
    os.path.join(BASE, "CUI1", "V2.0", "nrdata"),
    os.path.join(BASE, "HMC",  "V2.1", "nrdata"),
    os.path.join(BASE, "MMC",  "V2.5", "nrdata"),
    os.path.join(BASE, "MMM4", "V2.2", "nrdata"),
    os.path.join(BASE, "MMM4", "V2.2", "nraction"),
    os.path.join(BASE, "OSD",  "V1.5", "nrdata"),
    os.path.join(BASE, "PAF",  "V1.6", "nrdata"),
    os.path.join(BASE, "PTF",  "V1.0", "nrdata"),
    os.path.join(BASE, "TFA",  "V1.5", "nrdata"),
    os.path.join(BASE, "TFA",  "V1.5", "nrformats"),
    os.path.join(BASE, "TFA",  "V1.5", "nrtypes"),
]


def process_file(path):
    try:
        with open(path, "rb") as f:
            content = f.read()

        updated = content.replace(b"/data", b"/nrdata")

        if updated != content:
            count = content.count(b"/data")
            print(f"Updating: {path}  (replacements: {count})")

            with open(path, "wb") as f:
                f.write(updated)

    except Exception as e:
        print(f"❌ Error: {path}")
        print(e)


def process_folder(folder):
    if not os.path.isdir(folder):
        print(f"❌ Skipping (not found): {folder}")
        return

    print(f"\n=== Processing folder ===\n{folder}\n")

    for root, _, files in os.walk(folder):
        for name in files:
            if name.endswith(".json"):
                process_file(os.path.join(root, name))


def main():
    print("=== CHANGE REF (BATCH MODE) ===\n")

    for folder in TARGET_FOLDERS:
        process_folder(folder)

    print("\n✅ Done.")


if __name__ == "__main__":
    main()