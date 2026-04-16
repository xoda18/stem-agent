import ast
import re


def ast_check(code):
    issues = []

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [{"line": e.lineno or 0, "issue": f"syntax error: {e.msg}"}]

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for d in node.args.defaults + node.args.kw_defaults:
                if d is not None and isinstance(d, (ast.List, ast.Dict, ast.Set, ast.Call)):
                    issues.append({
                        "line": node.lineno,
                        "issue": f"mutable default argument in '{node.name}'"
                    })

        if isinstance(node, ast.ExceptHandler) and node.type is None:
            issues.append({
                "line": node.lineno,
                "issue": "bare except — catch specific exceptions instead"
            })

        if isinstance(node, ast.Assert):
            issues.append({
                "line": node.lineno,
                "issue": "assert used for validation (gets stripped in optimized mode)"
            })

    return issues


def pattern_search(code):
    issues = []
    lines = code.split("\n")

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        if re.search(r'[!=]=\s*None', line):
            if 'is not None' not in line and 'is None' not in line:
                issues.append({"line": i, "issue": "use 'is None' instead of ==/!= None"})

        if re.search(r'(SELECT|INSERT|UPDATE|DELETE|DROP)', line, re.IGNORECASE):
            if re.search(r'(f["\']|\.format\(|%s|%d|\+\s*["\'])', line):
                issues.append({"line": i, "issue": "possible SQL injection — use parameterized queries"})

        if re.search(r'(password|secret|api_key|token)\s*=\s*["\'][^"\']{8,}["\']', line, re.IGNORECASE):
            if not re.search(r'(example|placeholder|xxx|changeme|TODO)', line, re.IGNORECASE):
                issues.append({"line": i, "issue": "possible hardcoded secret"})

    return issues


def security_check(code):
    issues = []
    lines = code.split("\n")

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        if "eval(" in line and "# nosec" not in line:
            issues.append({"line": i, "issue": "eval() can run arbitrary code"})

        if "exec(" in line and "# nosec" not in line:
            issues.append({"line": i, "issue": "exec() can run arbitrary code"})

        if re.search(r'pickle\.(loads?|Unpickler)', line):
            issues.append({"line": i, "issue": "pickle deserialization can run arbitrary code"})

        if 'subprocess' in line and 'shell=True' in line:
            issues.append({"line": i, "issue": "shell=True in subprocess — shell injection risk"})

        if '__import__(' in line:
            issues.append({"line": i, "issue": "dynamic import via __import__"})

    return issues


def complexity_check(code):
    issues = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        branches = 0
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler,
                                  ast.With, ast.BoolOp)):
                branches += 1

        if branches > 8:
            issues.append({
                "line": node.lineno,
                "issue": f"'{node.name}' has high complexity ({branches} branches)"
            })

        if hasattr(node, 'end_lineno') and node.end_lineno:
            length = node.end_lineno - node.lineno
            if length > 50:
                issues.append({
                    "line": node.lineno,
                    "issue": f"'{node.name}' is {length} lines long"
                })

    return issues


def style_check(code):
    issues = []
    lines = code.split("\n")

    for i, line in enumerate(lines, 1):
        if len(line) > 120:
            issues.append({"line": i, "issue": f"line too long ({len(line)} chars)"})

    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                fn = node.value.func
                if isinstance(fn, ast.Name) and fn.id == 'open':
                    issues.append({
                        "line": node.lineno,
                        "issue": "file opened without context manager (use 'with')"
                    })
    except SyntaxError:
        pass

    return issues


TOOL_REGISTRY = {
    "ast_check": ast_check,
    "pattern_search": pattern_search,
    "security_check": security_check,
    "complexity_check": complexity_check,
    "style_check": style_check,
}

TOOL_DESCRIPTIONS = {
    "ast_check": "Parses Python AST — finds mutable defaults, bare excepts, assert misuse",
    "pattern_search": "Regex checks for == None, SQL injection, hardcoded secrets",
    "security_check": "Flags eval(), exec(), pickle, shell injection, dynamic imports",
    "complexity_check": "Measures function complexity (branch count) and length",
    "style_check": "Line length, missing context managers for file handling",
}
