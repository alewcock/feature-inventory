#!/usr/bin/env python3
"""
extract_symbols.py — Tree-sitter based symbol extraction for the Feature Inventory plugin.

Extracts functions, classes, imports, variables, calls, and connection hints from source
files across multiple languages. Outputs JSONL (one JSON object per symbol/hint/summary).

Usage:
    python3 extract_symbols.py --files file1.js,file2.py --output index.jsonl --repo-root /repo
    python3 extract_symbols.py --manifest manifest.json --output index.jsonl --repo-root /repo
    python3 extract_symbols.py --validate-only index.jsonl --repo-root /repo

CRITICAL: Symbol names are extracted via node.text.decode('utf-8'), never manual byte slicing.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

try:
    import tree_sitter_languages
except ImportError:
    print("ERROR: tree-sitter-languages is required. Install with: pip install tree-sitter-languages", file=sys.stderr)
    sys.exit(1)

# --- Language configuration ---

EXTENSION_TO_LANG = {
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "tsx",
    ".cs": "c_sharp",
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp",
    ".py": "python", ".pyi": "python",
    ".sql": "sql",
}

# Node types we care about per language family
LANG_SYMBOL_TYPES = {
    "javascript": {
        "function_declaration", "arrow_function", "method_definition", "class_declaration",
        "import_statement", "variable_declarator", "call_expression", "export_statement",
    },
    "typescript": {
        "function_declaration", "arrow_function", "method_definition", "class_declaration",
        "import_statement", "interface_declaration", "type_alias_declaration",
        "enum_declaration", "variable_declarator", "call_expression", "export_statement",
    },
    "tsx": {
        "function_declaration", "arrow_function", "method_definition", "class_declaration",
        "import_statement", "interface_declaration", "type_alias_declaration",
        "enum_declaration", "variable_declarator", "call_expression", "export_statement",
    },
    "c_sharp": {
        "method_declaration", "class_declaration", "struct_declaration",
        "interface_declaration", "enum_declaration", "property_declaration",
        "using_directive", "attribute", "field_declaration",
    },
    "c": {
        "function_definition", "function_declaration", "struct_specifier",
        "preproc_include", "preproc_def",
    },
    "cpp": {
        "function_definition", "function_declaration", "class_specifier",
        "struct_specifier", "preproc_include", "preproc_def",
    },
    "python": {
        "function_definition", "class_definition", "import_statement",
        "import_from_statement", "decorated_definition", "assignment",
    },
    "sql": {
        "create_table_statement", "create_function_statement", "create_procedure_statement",
        "create_trigger_statement", "create_view_statement", "create_index_statement",
        "column_definition", "foreign_key_constraint",
    },
}

# Mapping from tree-sitter node types to our symbol types
NODE_TYPE_MAP = {
    "function_declaration": "function", "function_definition": "function",
    "arrow_function": "function",
    "method_definition": "method", "method_declaration": "method",
    "class_declaration": "class", "class_definition": "class",
    "class_specifier": "class", "struct_specifier": "struct",
    "struct_declaration": "struct",
    "interface_declaration": "interface",
    "enum_declaration": "enum",
    "type_alias_declaration": "type_alias",
    "import_statement": "import", "import_from_statement": "import",
    "using_directive": "import",
    "variable_declarator": "variable",
    "property_declaration": "property",
    "field_declaration": "field",
    "attribute": "decorator",
    "decorated_definition": "decorated",
    "assignment": "variable",
    "export_statement": "export",
    "call_expression": "call",
    "preproc_include": "import", "preproc_def": "constant",
    "create_table_statement": "table", "create_view_statement": "view",
    "create_function_statement": "procedure", "create_procedure_statement": "procedure",
    "create_trigger_statement": "procedure", "create_index_statement": "index",
    "column_definition": "field", "foreign_key_constraint": "constraint",
}

# Connection hint patterns
HINT_CALLEE_PATTERNS = {
    "data_store_access": {
        "redis", "memcached", "s3", "dynamodb", "mongo", "mongoose",
        "sequelize", "knex", "prisma", "typeorm", "query", "execute",
        "createConnection", "getConnection",
    },
}

HINT_DECORATOR_PATTERNS = {
    "framework_magic": {
        "Route", "Get", "Post", "Put", "Delete", "Patch",
        "Controller", "Injectable", "Component", "Service",
        "app.get", "app.post", "app.put", "app.delete", "app.use",
        "router.get", "router.post", "router.put", "router.delete",
    },
}


# --- Helpers ---

def _text(node):
    """Safely decode node text. CRITICAL: always use node.text, never byte slicing."""
    if node is None:
        return None
    return node.text.decode("utf-8")


def _name(node):
    """Extract the name from a node via the 'name' field."""
    if node is None:
        return None
    name_node = node.child_by_field_name("name")
    if name_node:
        return _text(name_node)
    # Fallback: for some node types try 'declarator'
    decl = node.child_by_field_name("declarator")
    if decl:
        inner_name = decl.child_by_field_name("name")
        if inner_name:
            return _text(inner_name)
        return _text(decl)
    return None


def _child_by_type(node, type_name):
    """Find first direct child of a given type."""
    for child in node.children:
        if child.type == type_name:
            return child
    return None


def _children_by_type(node, type_name):
    """Find all direct children of a given type."""
    return [c for c in node.children if c.type == type_name]


def _is_async(node):
    """Check if a function node is async."""
    if node is None:
        return False
    txt = _text(node)
    if txt and txt.startswith("async "):
        return True
    for child in node.children:
        if child.type == "async":
            return True
    return False


def _visibility(node):
    """Try to extract visibility (public/private/protected) from node or parent."""
    if node is None:
        return None
    for child in node.children:
        if child.type in ("public", "private", "protected", "accessibility_modifier"):
            return _text(child)
    # JS/TS: check for # prefix (private field)
    n = _name(node)
    if n and n.startswith("#"):
        return "private"
    return None


def _extract_params(node):
    """Extract function parameters."""
    params = []
    param_node = node.child_by_field_name("parameters") or node.child_by_field_name("formal_parameters")
    if param_node is None:
        # Try to find by type
        param_node = _child_by_type(node, "formal_parameters") or _child_by_type(node, "parameters")
    if param_node is None:
        return params
    for child in param_node.children:
        if child.type in ("required_parameter", "optional_parameter", "parameter",
                          "identifier", "typed_parameter", "default_parameter",
                          "typed_default_parameter", "rest_parameter",
                          "simple_formal_parameter"):
            pname = _name(child) or _text(child)
            ptype = None
            type_ann = child.child_by_field_name("type")
            if type_ann:
                ptype = _text(type_ann)
            if pname and pname not in ("(", ")", ","):
                params.append({"name": pname, "type": ptype})
    return params


def _return_type(node):
    """Extract return type annotation if present."""
    rt = node.child_by_field_name("return_type")
    if rt:
        return _text(rt).lstrip(": ").strip()
    # TS type annotation on arrow function
    type_ann = node.child_by_field_name("type")
    if type_ann:
        return _text(type_ann)
    return None


# --- Call extraction ---

def _extract_calls_from_body(node):
    """Recursively find all call_expression nodes within a function body."""
    calls = []
    _walk_calls(node, calls)
    return calls


def _walk_calls(node, calls):
    if node.type == "call_expression":
        callee = node.child_by_field_name("function") or (node.children[0] if node.children else None)
        if callee:
            name = _text(callee)
            # Simplify: take last segment for member expressions
            if name and "." in name:
                # Keep full qualified name but also note it
                pass
            if name:
                calls.append({"name": name, "line": node.start_point[0] + 1})
    for child in node.children:
        _walk_calls(child, calls)


# --- Connection hint detection ---

def _detect_hints(node, file_path, source_lines):
    """Detect connection hints from a node."""
    hints = []
    _walk_hints(node, file_path, source_lines, hints)
    return hints


def _walk_hints(node, file_path, source_lines, hints):
    # Dynamic property access: obj[variable]()
    if node.type == "subscript_expression" or node.type == "computed_property_name":
        parent = node.parent
        if parent and parent.type == "call_expression":
            hints.append({
                "hint_type": "dynamic_call",
                "file": file_path,
                "line": node.start_point[0] + 1,
                "text": _text(node)[:120] if _text(node) else None,
            })
        else:
            # String dispatch: handlers["key"]
            hints.append({
                "hint_type": "string_key_dispatch",
                "file": file_path,
                "line": node.start_point[0] + 1,
                "text": _text(node)[:120] if _text(node) else None,
            })

    # Reflection patterns
    if node.type == "call_expression":
        callee = node.child_by_field_name("function") or (node.children[0] if node.children else None)
        if callee:
            cname = _text(callee) or ""
            # Data store access
            for pattern in HINT_CALLEE_PATTERNS.get("data_store_access", set()):
                if pattern.lower() in cname.lower():
                    hints.append({
                        "hint_type": "data_store_access",
                        "file": file_path,
                        "line": node.start_point[0] + 1,
                        "text": cname[:120],
                    })
                    break
            # Reflection
            if any(r in cname for r in ("getattr", "setattr", "Reflect.", "eval(", "getPrototypeOf",
                                         "GetType()", ".GetMethod(", "Activator.CreateInstance")):
                hints.append({
                    "hint_type": "reflection",
                    "file": file_path,
                    "line": node.start_point[0] + 1,
                    "text": cname[:120],
                })

    # Decorators / attributes
    if node.type in ("decorator", "attribute"):
        dec_text = _text(node) or ""
        for pattern in HINT_DECORATOR_PATTERNS.get("framework_magic", set()):
            if pattern in dec_text:
                hints.append({
                    "hint_type": "framework_magic",
                    "file": file_path,
                    "line": node.start_point[0] + 1,
                    "text": dec_text[:120],
                })
                break

    for child in node.children:
        _walk_hints(child, file_path, source_lines, hints)


# --- Main extraction per node ---

def _extract_symbol(node, lang, rel_path, source_lines, parent_name=None):
    """Extract a symbol dict from a tree-sitter node. Returns symbol dict or None."""
    ntype = node.type
    sym_type = NODE_TYPE_MAP.get(ntype)
    if sym_type is None:
        return None

    # Skip call expressions at top level — we extract calls within function bodies
    if sym_type == "call":
        return None

    # Skip exports — we handle export info on the child
    if sym_type == "export":
        return None

    # Decorated definitions: extract the inner definition
    if sym_type == "decorated":
        for child in node.children:
            if child.type in ("function_definition", "class_definition", "function_declaration",
                              "class_declaration", "method_definition"):
                sym = _extract_symbol(child, lang, rel_path, source_lines, parent_name)
                if sym:
                    # Collect decorator names
                    decorators = []
                    for dec in _children_by_type(node, "decorator"):
                        decorators.append(_text(dec))
                    sym["decorators"] = decorators
                return sym
        return None

    name = _name(node)

    # For arrow functions assigned to variables: get name from parent variable_declarator
    if ntype == "arrow_function" and name is None:
        if node.parent and node.parent.type == "variable_declarator":
            name = _name(node.parent)

    # For imports
    if sym_type == "import":
        return _extract_import(node, rel_path)

    # If still no name, skip
    if not name:
        return None

    # Variable declarator containing arrow_function: promote to function
    arrow_child = None
    if ntype == "variable_declarator":
        value_node = node.child_by_field_name("value")
        if value_node and value_node.type == "arrow_function":
            sym_type = "function"
            arrow_child = value_node

    # Python module-level assignment: only capture if at module root
    if ntype == "assignment" and lang == "python":
        if node.parent and node.parent.type not in ("module", "block"):
            return None
        left = node.child_by_field_name("left")
        name = _text(left) if left else name

    qualified_name = f"{parent_name}.{name}" if parent_name else name
    line_start = node.start_point[0] + 1
    line_end = node.end_point[0] + 1

    symbol = {
        "type": sym_type,
        "name": name,
        "qualified_name": qualified_name,
        "file": rel_path,
        "line_start": line_start,
        "line_end": line_end,
    }

    # Functions / methods (including promoted arrow functions)
    if sym_type in ("function", "method"):
        func_node = arrow_child if arrow_child else node
        symbol["signature"] = {
            "params": _extract_params(func_node),
            "return_type": _return_type(func_node),
        }
        symbol["is_async"] = _is_async(func_node)
        vis = _visibility(node)
        if vis:
            symbol["visibility"] = vis

        # Extract calls from body
        body = func_node.child_by_field_name("body") or _child_by_type(func_node, "statement_block") or _child_by_type(func_node, "block")
        if body:
            symbol["calls"] = _extract_calls_from_body(body)

    # Classes / structs / interfaces / enums
    elif sym_type in ("class", "struct", "interface", "enum"):
        vis = _visibility(node)
        if vis:
            symbol["visibility"] = vis
        # Extends / implements
        superclass = node.child_by_field_name("superclass")
        if superclass:
            symbol["extends"] = _text(superclass)
        # Body members — extract nested symbols
        body = node.child_by_field_name("body") or _child_by_type(node, "class_body") or _child_by_type(node, "declaration_list") or _child_by_type(node, "enum_body")
        if body:
            members = []
            for child in body.children:
                child_sym = _extract_symbol(child, lang, rel_path, source_lines, parent_name=name)
                if child_sym:
                    members.append(child_sym)
            if members:
                symbol["members"] = members

    # Variables / properties / fields
    elif sym_type in ("variable", "property", "field", "constant"):
        type_ann = node.child_by_field_name("type")
        if type_ann:
            symbol["value_type"] = _text(type_ann)

    # SQL types
    elif sym_type in ("table", "view", "procedure", "index"):
        pass  # name and line info is sufficient

    # Export info: check if parent is export_statement
    if node.parent and node.parent.type == "export_statement":
        # Check for default
        parent_text = _text(node.parent) or ""
        if "default" in parent_text[:30]:
            symbol["exports"] = ["default"]
        else:
            symbol["exports"] = ["named"]

    return symbol


def _extract_import(node, rel_path):
    """Extract import statement info."""
    sym = {
        "type": "import",
        "file": rel_path,
        "line_start": node.start_point[0] + 1,
        "line_end": node.end_point[0] + 1,
    }

    source_node = node.child_by_field_name("source") or node.child_by_field_name("module_name")
    if source_node:
        sym["source"] = _text(source_node).strip("'\"")
    else:
        # For C/Python imports, try full text
        full = _text(node) or ""
        sym["source"] = full.strip()

    # Try to extract imported names
    names = []
    for child in node.children:
        if child.type == "import_clause":
            for sub in child.children:
                if sub.type == "identifier":
                    names.append(_text(sub))
                elif sub.type in ("named_imports", "import_specifier"):
                    for spec in sub.children:
                        if spec.type == "import_specifier":
                            n = _name(spec)
                            if n:
                                names.append(n)
                        elif spec.type == "identifier":
                            names.append(_text(spec))
        elif child.type == "dotted_name":
            names.append(_text(child))
        elif child.type == "import_specifier":
            n = _name(child)
            if n:
                names.append(n)
    if names:
        sym["names"] = names

    # Set name to source for consistency
    sym["name"] = sym.get("source", _text(node)[:80] if _text(node) else "unknown")

    return sym


# --- File processing ---

def process_file(file_path, repo_root, lang_override=None):
    """Parse a single file and return (symbols, hints, error_msg)."""
    file_path = Path(file_path).resolve()
    repo_root = Path(repo_root).resolve()

    try:
        rel_path = str(file_path.relative_to(repo_root))
    except ValueError:
        rel_path = str(file_path)

    ext = file_path.suffix.lower()
    lang = lang_override or EXTENSION_TO_LANG.get(ext)
    if not lang:
        return [], [], f"No language mapping for extension '{ext}'"

    try:
        parser = tree_sitter_languages.get_parser(lang)
    except Exception as e:
        return [], [], f"Grammar not available for '{lang}': {e}"

    try:
        source_bytes = file_path.read_bytes()
    except Exception as e:
        return [], [], f"Cannot read file: {e}"

    try:
        tree = parser.parse(source_bytes)
    except Exception as e:
        return [], [], f"Parse error: {e}"

    source_text = source_bytes.decode("utf-8", errors="replace")
    source_lines = source_text.splitlines()

    symbols = []
    symbol_types = LANG_SYMBOL_TYPES.get(lang, set())

    # Node types that define a function scope — don't recurse into these for
    # top-level symbol discovery (calls are extracted separately by _extract_symbol)
    FUNCTION_SCOPE_TYPES = {
        "arrow_function", "function_declaration", "function_definition",
        "method_definition", "method_declaration",
    }

    def walk(node, parent_class_name=None, export_tag=None):
        ntype = node.type

        # For export_statement, set export tag and recurse into children
        if ntype == "export_statement":
            et = _text(node) or ""
            tag = ["default"] if "default" in et[:30] else ["named"]
            for child in node.children:
                walk(child, parent_class_name, export_tag=tag)
            return

        # Unwrap lexical_declaration / variable_declaration to reach variable_declarators
        if ntype in ("lexical_declaration", "variable_declaration"):
            for child in node.children:
                walk(child, parent_class_name, export_tag=export_tag)
            return

        # Process symbol-type nodes
        if ntype in symbol_types:
            sym = _extract_symbol(node, lang, rel_path, source_lines, parent_name=parent_class_name)
            if sym:
                if export_tag:
                    sym["exports"] = export_tag
                symbols.append(sym)
                # Don't recurse into class members — _extract_symbol handles that
                # Don't recurse into function bodies — we only want top-level symbols
                return

        # Don't recurse into function bodies for top-level walking
        if ntype in FUNCTION_SCOPE_TYPES:
            return

        for child in node.children:
            walk(child, parent_class_name, export_tag=export_tag)

    walk(tree.root_node)

    # Extract hints from the whole tree
    hints = _detect_hints(tree.root_node, rel_path, source_lines)

    return symbols, hints, None


# --- Validation ---

def validate_symbols(symbols, repo_root):
    """Validate that each symbol name appears on its source line. Returns (passed, errors)."""
    errors = []
    repo_root = Path(repo_root).resolve()

    # Group by file
    by_file = {}
    for sym in symbols:
        f = sym.get("file", "")
        by_file.setdefault(f, []).append(sym)

    for rel_file, file_syms in by_file.items():
        full_path = repo_root / rel_file
        try:
            source_lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception as e:
            errors.append(f"{rel_file}: cannot read for validation: {e}")
            continue

        for sym in file_syms:
            if sym["type"] == "import":
                continue  # imports don't always have a name on the line
            name = sym.get("name")
            if not name:
                continue
            line_idx = sym.get("line_start", 0) - 1
            if line_idx < 0 or line_idx >= len(source_lines):
                errors.append(f"{rel_file}:{sym.get('line_start')}: line out of range for symbol '{name}'")
                continue
            source_line = source_lines[line_idx]
            if name not in source_line:
                # Check a few lines around (some declarations span lines)
                found = False
                for offset in range(-2, 3):
                    idx = line_idx + offset
                    if 0 <= idx < len(source_lines) and name in source_lines[idx]:
                        found = True
                        break
                if not found:
                    errors.append(
                        f"{rel_file}:{sym.get('line_start')}: symbol '{name}' not found on source line: "
                        f"'{source_line.strip()[:80]}'"
                    )
            # Case corruption check
            elif name and source_line and name[0].islower():
                # Check if source actually starts uppercase
                idx = source_line.find(name)
                if idx >= 0:
                    pass  # found as-is, OK

    return len(errors) == 0, errors


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(description="Extract symbols from source code using tree-sitter.")
    parser.add_argument("--files", help="Comma-separated list of file paths")
    parser.add_argument("--manifest", help="JSON manifest with files list")
    parser.add_argument("--output", help="Output JSONL file path")
    parser.add_argument("--hints-output", help="Hints output JSONL file path")
    parser.add_argument("--repo-root", help="Repository root for relative path calculation", default=".")
    parser.add_argument("--validate-only", help="Validate an existing JSONL file", metavar="JSONL_FILE")

    args = parser.parse_args()

    # Validate-only mode
    if args.validate_only:
        return _run_validate_only(args.validate_only, args.repo_root)

    # Normal extraction mode
    if not args.files and not args.manifest:
        parser.error("Either --files or --manifest is required")
    if not args.output:
        parser.error("--output is required")

    files_to_process = []

    if args.files:
        for f in args.files.split(","):
            f = f.strip()
            if f:
                files_to_process.append({"path": f, "language": None})

    if args.manifest:
        try:
            with open(args.manifest, "r") as mf:
                manifest = json.load(mf)
            for entry in manifest.get("files", []):
                files_to_process.append({
                    "path": entry["path"],
                    "language": entry.get("language"),
                })
        except Exception as e:
            log.error(f"Cannot read manifest: {e}")
            sys.exit(1)

    repo_root = Path(args.repo_root).resolve()
    all_symbols = []
    all_hints = []
    files_processed = 0
    files_failed = 0
    total_calls = 0

    for entry in files_to_process:
        fpath = entry["path"]
        lang = entry.get("language")
        # Map language names to tree-sitter names
        if lang:
            lang_map = {"javascript": "javascript", "typescript": "typescript", "tsx": "tsx",
                        "csharp": "c_sharp", "c_sharp": "c_sharp", "c#": "c_sharp",
                        "c": "c", "cpp": "cpp", "c++": "cpp",
                        "python": "python", "sql": "sql", "mysql": "sql"}
            lang = lang_map.get(lang.lower(), lang)

        symbols, hints, error = process_file(fpath, repo_root, lang_override=lang)

        if error:
            log.warning(f"Skipping {fpath}: {error}")
            files_failed += 1
            continue

        # Validate symbols for this file
        passed, val_errors = validate_symbols(symbols, repo_root)
        if not passed:
            for ve in val_errors:
                log.error(f"VALIDATION FAILED: {ve}")
            log.error(f"File {fpath} failed validation — writing ZERO symbols")
            files_failed += 1
            continue

        # Count calls (including nested members)
        for sym in symbols:
            total_calls += len(sym.get("calls", []))
            for member in sym.get("members", []):
                total_calls += len(member.get("calls", []))

        all_symbols.extend(symbols)
        all_hints.extend(hints)
        files_processed += 1

    # Write output
    with open(args.output, "w") as out:
        for sym in all_symbols:
            out.write(json.dumps(sym, ensure_ascii=False) + "\n")

        # Summary
        summary = {
            "type": "summary",
            "files_processed": files_processed,
            "files_failed": files_failed,
            "symbols_extracted": len(all_symbols),
            "calls_extracted": total_calls,
            "hints_flagged": len(all_hints),
            "validation_passed": files_failed == 0,
        }
        out.write(json.dumps(summary, ensure_ascii=False) + "\n")

    log.info(f"Wrote {len(all_symbols)} symbols to {args.output}")
    log.info(f"Summary: {json.dumps(summary)}")

    # Write hints
    if args.hints_output and all_hints:
        with open(args.hints_output, "w") as hf:
            for hint in all_hints:
                hf.write(json.dumps(hint, ensure_ascii=False) + "\n")
        log.info(f"Wrote {len(all_hints)} hints to {args.hints_output}")

    if files_failed > 0:
        log.error(f"{files_failed} file(s) failed validation")
        sys.exit(1)


def _run_validate_only(jsonl_path, repo_root):
    """Validate an existing JSONL file."""
    symbols = []
    try:
        with open(jsonl_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if obj.get("type") != "summary":
                    symbols.append(obj)
    except Exception as e:
        log.error(f"Cannot read JSONL file: {e}")
        sys.exit(1)

    passed, errors = validate_symbols(symbols, repo_root)
    if passed:
        log.info(f"Validation passed: {len(symbols)} symbols OK")
        sys.exit(0)
    else:
        for e in errors:
            log.error(f"VALIDATION FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
