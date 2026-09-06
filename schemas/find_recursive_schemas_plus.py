"""
find_recursive_schemas_plus.py
"""

import json
import sys
import os
from pathlib import Path
from collections import defaultdict


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def find_all_schemas(folders):
    schemas = {}
    for folder in folders:
        for path in Path(folder).rglob("*.json"):
            abs_path = str(path.resolve())
            try:
                with open(abs_path, encoding="utf-8") as f:
                    schemas[abs_path] = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(f"  [WARN] Could not load {abs_path}: {e}")
    return schemas


# ---------------------------------------------------------------------------
# $ref extraction
# ---------------------------------------------------------------------------

def extract_refs(obj):
    refs = []
    if isinstance(obj, dict):
        if "$ref" in obj and isinstance(obj["$ref"], str):
            refs.append(obj["$ref"])
        for value in obj.values():
            refs.extend(extract_refs(value))
    elif isinstance(obj, list):
        for item in obj:
            refs.extend(extract_refs(item))
    return refs


def has_root_self_ref(schema):
    for ref in extract_refs(schema):
        if ref in ("#", "#/"):
            return True
    return False


def extract_internal_def_refs(schema):
    defs = schema.get("$defs") or schema.get("definitions") or {}
    graph = defaultdict(set)

    for def_name, def_schema in defs.items():
        for ref in extract_refs(def_schema):
            if not ref.startswith("#"):
                continue
            parts = ref.lstrip("#/").split("/")
            if len(parts) >= 2 and parts[0] in ("$defs", "definitions"):
                target_def = parts[1]
                graph[def_name].add(target_def)

    return graph


def has_internal_cycle(schema):
    def_graph = extract_internal_def_refs(schema)

    visited = set()
    rec_set = set()

    def dfs(node):
        if node in rec_set:
            return True
        if node in visited:
            return False
        visited.add(node)
        rec_set.add(node)

        for neighbor in def_graph.get(node, []):
            if dfs(neighbor):
                return True

        rec_set.remove(node)
        return False

    return any(dfs(n) for n in def_graph)


# ---------------------------------------------------------------------------
# Cross-file ref resolution (fragment-aware)
# ---------------------------------------------------------------------------

def build_id_index(schemas):
    index = {}
    for file_path, schema in schemas.items():
        schema_id = schema.get("$id") or schema.get("id")
        if isinstance(schema_id, str):
            base = schema_id.split("#")[0]
            if base in index:
                print(f"[WARN] Duplicate $id detected: {base}")
            index[base] = file_path
    return index


def resolve_ref(ref, current_file, all_schema_paths, id_index):

    if ref.startswith("#"):
        return (current_file, ref)

    ref_file, _, fragment = ref.partition("#")

    if ref_file.startswith("http://") or ref_file.startswith("https://"):
        target = id_index.get(ref_file)
        if not target:
            print(f"  [WARN] Unresolved URL ref: {ref}")
            return None
        return (target, f"#{fragment}" if fragment else "")

    current_dir = os.path.dirname(current_file)
    resolved = str(Path(current_dir, ref_file).resolve())

    if resolved not in all_schema_paths:
        print(f"  [WARN] Unresolved file ref: {ref} (from {current_file})")
        return None

    return (resolved, f"#{fragment}" if fragment else "")


def build_reference_graph(schemas):
    graph = defaultdict(set)
    all_paths = set(schemas.keys())
    id_index = build_id_index(schemas)

    print(f"Built $id index with {len(id_index)} entr(ies).\n")

    for file_path, schema in schemas.items():
        source = (file_path, "")
        for ref in extract_refs(schema):
            target = resolve_ref(ref, file_path, all_paths, id_index)
            if target:
                graph[source].add(target)

    return graph


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------

def canonical_cycle(cycle):
    cycle = cycle[:-1]
    rotations = [tuple(cycle[i:] + cycle[:i]) for i in range(len(cycle))]
    return min(rotations)


def find_cycles(graph):
    all_nodes = set(graph.keys()) | {n for v in graph.values() for n in v}
    visited = set()
    rec_stack = []
    rec_set = set()
    cycles = []
    seen = set()

    def dfs(node):
        visited.add(node)
        rec_stack.append(node)
        rec_set.add(node)

        for neighbor in graph.get(node, []):
            if neighbor == node:
                key = (node,)
                if key not in seen:
                    seen.add(key)
                    cycles.append([node, node])
            elif neighbor not in visited:
                dfs(neighbor)
            elif neighbor in rec_set:
                start = rec_stack.index(neighbor)
                cycle = rec_stack[start:] + [neighbor]
                key = canonical_cycle(cycle)
                if key not in seen:
                    seen.add(key)
                    cycles.append(cycle)

        rec_stack.pop()
        rec_set.remove(node)

    for n in all_nodes:
        if n not in visited:
            dfs(n)

    return cycles


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def shorten(path, folders):
    for folder in folders:
        try:
            return str(Path(path).relative_to(Path(folder).resolve()))
        except ValueError:
            continue
    return path


def main(folders):
    print(f"\nScanning {len(folders)} folder(s)...\n")
    schemas = find_all_schemas(folders)
    print(f"Loaded {len(schemas)} schema file(s).\n")

    if not schemas:
        print("No schemas found.")
        return

    # Internal recursion
    self_recursive = [
        fp for fp, s in schemas.items()
        if has_internal_cycle(s) or has_root_self_ref(s)
    ]

    if self_recursive:
        print(f"Found {len(self_recursive)} schema(s) with internal recursion:\n")
        for fp in sorted(self_recursive):
            print(f"  [INTERNAL] {shorten(fp, folders)}")
        print()

    # Graph
    graph = build_reference_graph(schemas)
    print(f"Built graph with {len(graph)} nodes.\n")

    cycles = find_cycles(graph)

    if not cycles:
        print("No cross-file circular references found.")
        return

    print(f"Found {len(cycles)} cross-file recursive chain(s):\n")

    for i, cycle in enumerate(cycles, 1):
        if len(cycle) == 2 and cycle[0] == cycle[1]:
            label = "SELF"
        elif len(cycle) == 3:
            label = "PAIR"
        else:
            label = "CHAIN"

        print(f"  Cycle {i} [{label}]:")
        for node, frag in cycle:
            print(f"    -> {shorten(node, folders)} {frag}")
        print()

    involved = {node for cycle in cycles for (node, frag) in cycle}

    print(f"{len(involved)} file(s) involved in recursion:")
    for path in sorted(involved):
        print(f"  {shorten(path, folders)}")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE = r"C:\Users\Leonardo\OneDrive - CEDEO\My Standards\mpai\schemas"

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


if __name__ == "__main__":
    folders = sys.argv[1:] if len(sys.argv) > 1 else TARGET_FOLDERS
    main(folders)