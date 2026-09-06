"""
find_recursive_schemas.py

Scans multiple folders of JSON schemas and detects ALL forms of recursion:

  Internal (within a single file):
    - $defs/Foo -> $defs/Foo  (self-ref inside $defs)
    - $defs/Foo -> $defs/Bar -> $defs/Foo  (indirect cycle between $defs)
    - root -> $defs/Foo -> root  (def refs back to root via "#")
    - $defs/Foo -> "#"  (def directly refs the document root)
    - nested $defs (e.g. #/$defs/Foo/$defs/Bar)

  Cross-file:
    - A -> B -> A  (file cycle via $ref)
    - self-ref file (A -> A via URL $id match)

Supports both relative file path $refs and absolute URL $refs resolved
via each schema's $id field.

Usage:
    python find_recursive_schemas.py <folder1> <folder2> ...

Example:
    python find_recursive_schemas.py ./schemas/a ./schemas/b ./schemas/c
"""

import json
import sys
import os
from pathlib import Path
from collections import defaultdict


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def find_all_schemas(folders: list[str]) -> dict[str, dict]:
    """Load all .json files from the given folders, keyed by resolved absolute path."""
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

def extract_refs(obj) -> list[str]:
    """Recursively extract all $ref string values from a JSON object."""
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


# ---------------------------------------------------------------------------
# Internal cycle detection  (complete rewrite)
# ---------------------------------------------------------------------------

# Sentinel node name representing the schema root document itself
_ROOT = "__ROOT__"


def _collect_all_defs(schema: dict) -> dict[str, dict]:
    """
    Collect every named definition from a schema, handling both
    top-level $defs / definitions and nested ones.

    Returns { "FullPath": sub_schema } where FullPath uses '/' as separator,
    e.g. "Foo", "Foo/Bar", etc.
    """
    result = {}

    def _recurse(obj, prefix: str):
        if not isinstance(obj, dict):
            return
        for key in ("$defs", "definitions"):
            defs_block = obj.get(key)
            if not isinstance(defs_block, dict):
                continue
            for name, sub in defs_block.items():
                full = f"{prefix}/{name}" if prefix else name
                result[full] = sub
                _recurse(sub, full)  # nested $defs inside a $def

    _recurse(schema, "")
    return result


def _ref_to_node(ref: str, all_def_keys: set[str]) -> str | None:
    """
    Interpret a purely-internal $ref (must start with '#') and return the
    logical node name it points to:

      "#"             -> _ROOT  (points to the whole document)
      "#/$defs/Foo"   -> "Foo"
      "#/definitions/Bar/definitions/Baz" -> "Bar/Baz"  (nested)

    Returns None if the ref does not map to any known node.
    """
    if not ref.startswith("#"):
        return None

    fragment = ref.lstrip("#").strip("/")  # e.g. "$defs/Foo" or ""

    if not fragment:
        return _ROOT  # bare "#"

    parts = fragment.split("/")

    # Walk the parts, stripping $defs / definitions keywords to form the path
    def_path_parts = []
    i = 0
    while i < len(parts):
        if parts[i] in ("$defs", "definitions"):
            i += 1  # skip keyword
            if i < len(parts):
                def_path_parts.append(parts[i])
                i += 1
        else:
            # unexpected segment – not a $defs pointer we understand
            return None

    if not def_path_parts:
        return None

    candidate = "/".join(def_path_parts)
    return candidate if candidate in all_def_keys else None


def build_internal_graph(schema: dict) -> dict[str, set[str]]:
    """
    Build a directed graph of internal references for a single schema.

    Nodes:
      _ROOT  – the top-level schema object
      "Foo"  – the $def named Foo  (nested: "Foo/Bar")

    Edges:
      node A -> node B  means A contains a $ref that resolves to B's location.

    This covers:
      * root -> $defs/Foo        (root body has "$ref": "#/$defs/Foo")
      * $defs/Foo -> $defs/Bar   (Foo has "$ref": "#/$defs/Bar")
      * $defs/Foo -> root        (Foo has "$ref": "#")
      * $defs/Foo -> $defs/Foo   (Foo has "$ref": "#/$defs/Foo"  self-loop)
    """
    all_defs = _collect_all_defs(schema)
    all_def_keys = set(all_defs.keys())

    graph: dict[str, set[str]] = defaultdict(set)

    # Edges from root: scan the entire schema body but NOT inside $defs blocks
    # (those are handled separately per def).
    root_body_refs = _refs_excluding_defs(schema)
    for ref in root_body_refs:
        target = _ref_to_node(ref, all_def_keys)
        if target is not None:
            graph[_ROOT].add(target)

    # Edges from each named def
    for def_key, def_schema in all_defs.items():
        for ref in extract_refs(def_schema):
            target = _ref_to_node(ref, all_def_keys)
            if target is not None:
                if target == def_key:
                    graph[def_key].add(def_key)  # self-loop
                else:
                    graph[def_key].add(target)

    return graph


def _refs_excluding_defs(schema: dict) -> list[str]:
    """
    Extract $ref values from a schema object WITHOUT descending into
    $defs / definitions blocks (those are processed separately).
    """
    refs = []
    if isinstance(schema, dict):
        if "$ref" in schema and isinstance(schema["$ref"], str):
            refs.append(schema["$ref"])
        for k, v in schema.items():
            if k in ("$defs", "definitions"):
                continue  # skip; handled per-def elsewhere
            refs.extend(_refs_excluding_defs(v))
    elif isinstance(schema, list):
        for item in schema:
            refs.extend(_refs_excluding_defs(item))
    return refs


def has_internal_cycle(schema: dict) -> tuple[bool, list[list[str]]]:
    """
    Return (has_cycle, cycles) where cycles is a list of node-name paths
    that form loops, e.g. ["__ROOT__", "Foo", "__ROOT__"].
    """
    graph = build_internal_graph(schema)
    cycles = _find_all_cycles(graph)
    return bool(cycles), cycles


# ---------------------------------------------------------------------------
# Generic cycle finder (works for both internal and cross-file graphs)
# ---------------------------------------------------------------------------

def _find_all_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """
    Find all distinct cycles in a directed graph using iterative DFS.
    Handles self-loops explicitly.
    Returns a list of cycles (each a list of node names forming the loop).
    """
    all_nodes = set(graph.keys()) | {n for nbrs in graph.values() for n in nbrs}
    visited: set[str] = set()
    seen_cycle_keys: set[tuple] = set()
    cycles: list[list[str]] = []

    for start in all_nodes:
        if start in visited:
            continue

        # Iterative DFS with explicit stack: (node, iterator_over_neighbours, path)
        stack: list[tuple[str, iter, list[str]]] = []
        path: list[str] = []
        path_set: set[str] = set()

        def push(node: str):
            stack.append((node, iter(sorted(graph.get(node, []))), path))

        push(start)
        path.append(start)
        path_set.add(start)
        visited.add(start)

        while stack:
            node, nbr_iter, _ = stack[-1]
            try:
                neighbor = next(nbr_iter)

                if neighbor == node:
                    # self-loop
                    key = (node,)
                    if key not in seen_cycle_keys:
                        seen_cycle_keys.add(key)
                        cycles.append([node, node])
                    continue

                if neighbor in path_set:
                    # Found a back-edge -> cycle
                    idx = path.index(neighbor)
                    cycle = path[idx:] + [neighbor]
                    key = tuple(sorted(set(cycle)))
                    if key not in seen_cycle_keys:
                        seen_cycle_keys.add(key)
                        cycles.append(cycle)
                    continue

                if neighbor not in visited:
                    visited.add(neighbor)
                    path.append(neighbor)
                    path_set.add(neighbor)
                    stack.append((neighbor, iter(sorted(graph.get(neighbor, []))), path))

            except StopIteration:
                stack.pop()
                if path and path[-1] == node:
                    path.pop()
                    path_set.discard(node)

    return cycles


# ---------------------------------------------------------------------------
# Cross-file ref resolution
# ---------------------------------------------------------------------------

def build_id_index(schemas: dict[str, dict]) -> dict[str, str]:
    """
    Build a lookup table of { $id URL -> local file path } from all loaded schemas.
    Strips any fragment (#...) from the $id before indexing.
    """
    index = {}
    for file_path, schema in schemas.items():
        schema_id = schema.get("$id") or schema.get("id")
        if isinstance(schema_id, str):
            index[schema_id.split("#")[0]] = file_path
    return index


def resolve_ref(ref: str, current_file: str,
                all_schema_paths: set[str],
                id_index: dict[str, str]) -> str | None:
    """
    Resolve a $ref to an absolute local file path.
    Returns None for purely internal refs ("#/...") or unresolvable refs.
    """
    if ref.startswith("#"):
        return None

    ref_file = ref.split("#")[0]
    if not ref_file:
        return None

    if ref_file.startswith("http://") or ref_file.startswith("https://"):
        return id_index.get(ref_file)

    current_dir = os.path.dirname(current_file)
    resolved = str(Path(current_dir, ref_file).resolve())
    return resolved if resolved in all_schema_paths else None


def build_reference_graph(schemas: dict[str, dict]) -> dict[str, set[str]]:
    """
    Build a directed cross-file graph: file -> set of files it references.
    """
    graph: dict[str, set[str]] = defaultdict(set)
    all_paths = set(schemas.keys())
    id_index = build_id_index(schemas)

    print(f"Built $id index with {len(id_index)} entr(ies).\n")

    for file_path, schema in schemas.items():
        for ref in extract_refs(schema):
            target = resolve_ref(ref, file_path, all_paths, id_index)
            if target:
                graph[file_path].add(target)

    return graph


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------

def shorten(path: str, folders: list[str]) -> str:
    """Make a path relative to the nearest input folder for readability."""
    for folder in folders:
        try:
            return str(Path(path).relative_to(Path(folder).resolve()))
        except ValueError:
            continue
    return path


def _format_internal_cycle(cycle: list[str]) -> str:
    """Pretty-print an internal cycle using human-readable node names."""
    def label(n):
        return "«root»" if n == _ROOT else f"$defs/{n}"
    return " → ".join(label(n) for n in cycle)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(folders: list[str]):
    print(f"\nScanning {len(folders)} folder(s)...\n")
    schemas = find_all_schemas(folders)
    print(f"Loaded {len(schemas)} schema file(s).\n")

    if not schemas:
        print("No schemas found. Check your folder paths.")
        return

    # ── 1. Internal $defs / root recursion (within a single file) ──────────
    print("=" * 60)
    print("STEP 1 – Internal recursion check")
    print("=" * 60)

    internal_hits = []
    for fp, schema in schemas.items():
        found, cycles = has_internal_cycle(schema)
        if found:
            internal_hits.append((fp, cycles))

    if internal_hits:
        print(f"\nFound {len(internal_hits)} schema(s) with internal recursive references:\n")
        for fp, cycles in sorted(internal_hits):
            print(f"  FILE: {shorten(fp, folders)}")
            for c in cycles:
                print(f"    [CYCLE] {_format_internal_cycle(c)}")
            print()
    else:
        print("\nNo internal recursive references found.\n")

    # ── 2. Cross-file reference cycles ─────────────────────────────────────
    print("=" * 60)
    print("STEP 2 – Cross-file reference cycle check")
    print("=" * 60)

    graph = build_reference_graph(schemas)
    print(f"\nBuilt reference graph with {len(graph)} file(s) that have outgoing $refs.\n")

    cycles = _find_all_cycles(graph)

    if not cycles:
        print("No cross-file circular references found.\n")
    else:
        print(f"Found {len(cycles)} cross-file circular reference chain(s):\n")
        for i, cycle in enumerate(cycles, 1):
            if len(cycle) == 2 and cycle[0] == cycle[1]:
                print(f"  Cycle {i}: [SELF-FILE] {shorten(cycle[0], folders)}")
            else:
                arrow = " →\n    ".join(shorten(p, folders) for p in cycle)
                print(f"  Cycle {i}:\n    {arrow}\n")

        involved = {path for cycle in cycles for path in cycle}
        print(f"{len(involved)} file(s) involved in cross-file circular references:")
        for path in sorted(involved):
            print(f"  {shorten(path, folders)}")
        print()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

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

if __name__ == "__main__":
    folders = sys.argv[1:] if len(sys.argv) > 1 else TARGET_FOLDERS
    main(folders)
