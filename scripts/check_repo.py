#!/usr/bin/env python3
"""Pre-flight checks for the repository itself (no GPU, no wheel required).

Runs on every push in CI and locally with ``make check``:

* every relative Markdown link and image resolves;
* every Python file parses;
* every JSON file parses;
* ``SHA256SUMS`` matches the files that are present (the wheel is allowed to be
  absent, because it is a release asset and not a git object);
* no absolute maintainer paths, tokens, or release placeholders leaked in.

Exit code 0 means the repository is safe to publish. It does not validate the
wheel; ``scripts/audit_hooks.py`` does that.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "__pycache__", ".venv", "dist", "release", "node_modules"}
SELF = Path(__file__).resolve()

# Patterns that must never appear in a public repository. SELF is skipped
# because this file contains the patterns themselves.
FORBIDDEN = (
    (re.compile(r"/Users/[A-Za-z0-9._-]+"), "absolute macOS home path"),
    (re.compile(r"agentlab|labagent"), "private host/user name"),
    (re.compile(r"\bHF_TOKEN\b"), "token variable leaked"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "GitHub token"),
    (re.compile(r"\bhf_[A-Za-z0-9]{30,}"), "Hugging Face token"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "GitHub fine-grained token"),
    (re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"), "private key"),
)

PLACEHOLDERS = ("<namespace>", "<owner>", "<your-user>", "<hf-username>")
LINK_RE = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
SCHEME_RE = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|#|//)")


def iter_files():
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix in {".whl", ".pyc"}:
            continue
        yield path


def check_markdown_links() -> list[str]:
    errors: list[str] = []
    for md in iter_files():
        if md.suffix.lower() not in {".md", ".markdown"}:
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        for match in LINK_RE.finditer(text):
            target = match.group(1).strip()
            if SCHEME_RE.match(target):
                continue
            target = target.split("#", 1)[0]
            if not target:
                continue
            resolved = (md.parent / target).resolve()
            if not resolved.exists():
                errors.append(f"{md.relative_to(ROOT)}: broken link -> {target}")
    return errors


def check_sources() -> list[str]:
    errors: list[str] = []
    for path in iter_files():
        try:
            if path.suffix == ".py":
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            elif path.suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))
        except (SyntaxError, ValueError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: {exc}")
    return errors


def check_sums() -> list[str]:
    manifest = ROOT / "SHA256SUMS"
    if not manifest.exists():
        return ["SHA256SUMS: missing"]
    errors: list[str] = []
    checked = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2:
            errors.append(f"SHA256SUMS: malformed line -> {line}")
            continue
        expected, name = parts
        path = ROOT / name
        if not path.exists():
            if path.suffix == ".whl":
                continue  # release asset, expected to be absent in git
            errors.append(f"SHA256SUMS: missing file -> {name}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            errors.append(f"SHA256SUMS: hash mismatch -> {name}")
        checked += 1
    if checked == 0:
        errors.append("SHA256SUMS: no file could be checked")
    return errors


def check_leaks() -> list[str]:
    errors: list[str] = []
    for path in iter_files():
        if path.resolve() == SELF:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern, label in FORBIDDEN:
            if pattern.search(text):
                errors.append(f"{path.relative_to(ROOT)}: {label}")
        for placeholder in PLACEHOLDERS:
            if placeholder in text and path.suffix in {".md", ".sh", ".yml", ".yaml"}:
                errors.append(f"{path.relative_to(ROOT)}: placeholder {placeholder} left in")
    return errors


def main() -> int:
    groups = {
        "markdown links": check_markdown_links(),
        "sources": check_sources(),
        "checksums": check_sums(),
        "leaks": check_leaks(),
    }
    failed = False
    for name, errors in groups.items():
        if errors:
            failed = True
            print(f"[FAIL] {name}")
            for error in errors:
                print(f"       {error}")
        else:
            print(f"[ok]   {name}")
    print("RESULT:", "FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
