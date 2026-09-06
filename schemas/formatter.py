import json
import os

BRACE_COL = 32


# -----------------------------
# Alignment
# -----------------------------

def align_key(key, indent):
    key_str = f'"{key}":'
    return " " * indent + key_str.ljust(BRACE_COL - indent)


# -----------------------------
# Simple detection helpers
# -----------------------------

def is_simple_object(obj):
    return isinstance(obj, dict) and all(not isinstance(v, (dict, list)) for v in obj.values())


def is_simple_array(arr):
    return isinstance(arr, list) and all(not isinstance(x, (dict, list)) for x in arr)


def is_structural_triple(obj):
    return (
        isinstance(obj, dict)
        and obj.get("type") == "object"
        and obj.get("additionalProperties") is False
        and "properties" in obj
    )


def is_array_anyof(obj):
    return (
        isinstance(obj, dict)
        and obj.get("type") == "array"
        and isinstance(obj.get("items"), dict)
        and "anyOf" in obj["items"]
    )


# -----------------------------
# Inline formatting
# -----------------------------

def format_inline(obj):
    if isinstance(obj, dict):
        return "{ " + ", ".join(f'"{k}": {format_inline(v)}' for k, v in obj.items()) + " }"
    elif isinstance(obj, list):
        return "[ " + ", ".join(format_inline(x) for x in obj) + " ]"
    else:
        return json.dumps(obj)


# -----------------------------
# Core formatter
# -----------------------------

def format_object(obj, indent=0, force_left=False):
    """
    force_left=True → always align keys at semantic column
    (used inside 'properties')
    """

    lines = []
    items = list(obj.items())

    for i, (key, value) in enumerate(items):

        prefix = align_key(key, indent)

        # ✅ simple cases
        if is_simple_object(value):
            line = f"{prefix}{format_inline(value)}"

        elif is_simple_array(value):
            line = f"{prefix}{format_inline(value)}"

        # ✅ ARRAY ANYOF (core pattern)
        elif is_array_anyof(value):

            header = f'{prefix}{{ "type": "array", "items": {{ "anyOf": ['
            lines.append(header)

            rhs_indent = BRACE_COL

            for j, item in enumerate(value["items"]["anyOf"]):

                # ✅ structural triple → inline
                if is_structural_triple(item):

                    lines.append(
                        " " * rhs_indent
                        + '{ "type": "object", "additionalProperties": false, "properties": {'
                    )
                    lines.append("")

                    # ❗ IMPORTANT: reset to LEFT alignment
                    inner = format_object(item["properties"], indent + 6, True)
                    lines.append(inner)

                    closing = " " * rhs_indent + "} }"

                else:
                    lines.append(" " * rhs_indent + "{")
                    inner = format_object(item, indent + 6, True)
                    lines.append(inner)
                    closing = " " * rhs_indent + "}"

                if j < len(value["items"]["anyOf"]) - 1:
                    closing += ","

                lines.append(closing)

            line = " " * indent + "] } }"

        # ✅ structural triple (outside arrays)
        elif is_structural_triple(value):

            line = (
                f'{prefix}{{ "type": "object", '
                f'"additionalProperties": false, "properties": {{'
            )
            lines.append(line)
            lines.append("")

            inner = format_object(value["properties"], indent + 2, True)
            lines.append(inner)

            line = " " * indent + "} }"

        # ✅ properties / defs
        elif key in ("properties", "$defs"):
            lines.append(f"{prefix}{{")
            lines.append("")

            inner = format_object(value, indent + 2, True)
            lines.append(inner)

            line = " " * indent + "}"

        # ✅ generic dict
        elif isinstance(value, dict):
            line = f"{prefix}{format_inline(value)}"

        else:
            line = f"{prefix}{json.dumps(value)}"

        if i < len(items) - 1:
            line += ","

        lines.append(line)

    return "\n".join(lines)


# -----------------------------
# Cleanup (Rule: no orphan braces)
# -----------------------------

def cleanup(text):
    lines = text.split("\n")
    result = []

    for line in lines:
        stripped = line.strip()

        if stripped and all(c in "}] ," for c in stripped) and result:
            result[-1] += " " + stripped
        else:
            result.append(line)

    return "\n".join(result)


# -----------------------------
# Output path
# -----------------------------

def derive_output_path(data):
    url = data["$id"]

    if "://" in url:
        path = url.split("://", 1)[1]
        path = path.split("/", 1)[1]
    else:
        path = url

    folder = os.path.dirname(path)
    name = os.path.basename(path)

    base, ext = os.path.splitext(name)
    out_name = f"{base}1{ext if ext else '.json'}"

    full = os.path.join(folder, out_name)
    os.makedirs(os.path.dirname(full), exist_ok=True)

    return full


# -----------------------------
# Main
# -----------------------------

def main():
    print("Paste JSON → ENTER twice:\n")

    lines = []
    while True:
        l = input()
        if l.strip() == "":
            break
        lines.append(l)

    if not lines:
        print("No input.")
        return

    data = json.loads("\n".join(lines))

    raw = "{\n" + format_object(data, 2) + "\n}"
    result = cleanup(raw)

    path = derive_output_path(data)

    with open(path, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"\n✅ Written to: {path}")


if __name__ == "__main__":
    main()