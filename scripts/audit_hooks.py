#!/usr/bin/env python3
"""Static audit of an EAGLE-4 vLLM wheel.

Checks the wheel tag, version and SHA-256, then verifies every hook that
``eagle-harness`` 0.1.4 resolves at load time (``eagle_harness.vllm.adapter``).
It reads the wheel as a zip: no vLLM import, no CUDA, no GPU required.

Usage:
    python3 scripts/audit_hooks.py vllm-*.whl
    python3 scripts/audit_hooks.py vllm-*.whl --json
    python3 scripts/audit_hooks.py vllm-*.whl --skip-hash
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

EXPECTED_SHA256 = "fbd7ec77a34f608b4158d7a7196f75a1f78100da3645825e0a30657f72408237"
EXPECTED_TAG = "cp312-cp312-linux_aarch64"
EXPECTED_VERSION = "0.32.0rc1.dev283+eagle.3"

# Mirrors eagle_harness.vllm.adapter.HOOK_MAP in eagle-harness 0.1.4.
# (need, file inside the wheel, regex that proves the symbol is present)
HOOKS = (
    ("algorithm registration", "vllm/v1/spec_decode/registry.py", r"def\s+register_speculative_method\b"),
    ("opaque algorithm config", "vllm/config/speculative.py", r"\bmethod_config\s*:"),
    ("method configure", "vllm/v1/spec_decode/registry.py", r"(?:\bconfigure\s*:|def\s+configure\b)"),
    ("KV headroom (lookahead)", "vllm/v1/spec_decode/registry.py", r"\bnum_lookahead_tokens\b"),
    ("draft + KV slots (propose)", "vllm/v1/worker/gpu/spec_decode/speculator.py", r"def\s+propose\b"),
    ("target verify inputs", "vllm/v1/worker/gpu/spec_decode/speculator.py", r"def\s+prepare_verify_inputs\b"),
    ("verify accept", "vllm/v1/worker/gpu/spec_decode/speculator.py", r"def\s+make_rejection_sampler\b"),
    ("accepted-path KV compaction", "vllm/v1/worker/gpu/spec_decode/speculator.py", r"def\s+post_accept\b"),
    ("GDN tree verify", "vllm/model_executor/layers/mamba/gdn/verify_extension.py", r"def\s+forward_spec_rows\b"),
    ("tree attention backend", "vllm/v1/attention/backends/registry.py", r"\bCUSTOM\b"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_member(zf: zipfile.ZipFile, suffix: str) -> str:
    for name in zf.namelist():
        if name.endswith(suffix):
            return zf.read(name).decode("utf-8", "replace")
    raise KeyError(suffix)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Audit the EAGLE-4 hook surface of a vLLM wheel.")
    ap.add_argument("wheel", type=Path, help="path to the vllm-*.whl file")
    ap.add_argument("--expected-sha256", default=EXPECTED_SHA256, help="override the expected SHA-256")
    ap.add_argument("--skip-hash", action="store_true", help="skip the SHA-256 check (not recommended)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    if not args.wheel.is_file():
        ap.error(f"no such file: {args.wheel}")

    result: dict[str, object] = {"wheel": str(args.wheel), "ok": True, "hooks": []}

    actual_hash = None if args.skip_hash else sha256(args.wheel)
    hash_ok = args.skip_hash or actual_hash == args.expected_sha256
    result["sha256"] = actual_hash
    result["sha256_expected"] = None if args.skip_hash else args.expected_sha256
    result["sha256_ok"] = hash_ok

    with zipfile.ZipFile(args.wheel) as zf:
        wheel_meta = read_member(zf, ".dist-info/WHEEL")
        metadata = read_member(zf, ".dist-info/METADATA")
        tag_match = re.search(r"^Tag:\s*(\S+)$", wheel_meta, re.MULTILINE)
        version_match = re.search(r"^Version:\s*(\S+)$", metadata, re.MULTILINE)
        tag = tag_match.group(1) if tag_match else "unknown"
        version = version_match.group(1) if version_match else "unknown"
        result["tag"] = tag
        result["tag_ok"] = tag == EXPECTED_TAG
        result["version"] = version
        result["version_ok"] = version == EXPECTED_VERSION
        if tag != EXPECTED_TAG:
            result["ok"] = False
        if version != EXPECTED_VERSION:
            result["ok"] = False

        for need, member, pattern in HOOKS:
            try:
                source = zf.read(member).decode("utf-8", "replace")
                match = re.search(pattern, source)
                found = match is not None
                line = source[: match.start()].count("\n") + 1 if match else None
            except KeyError:
                found, line = False, None
            result["hooks"].append({"need": need, "file": member, "found": found, "line": line})
            if not found:
                result["ok"] = False

    if not hash_ok:
        result["ok"] = False

    if args.json:
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1

    print(f"Wheel:    {args.wheel}")
    print(f"Size:     {args.wheel.stat().st_size:,} bytes")
    if args.skip_hash:
        print("SHA-256:  skipped")
    else:
        print(f"SHA-256:  {actual_hash}  {'OK' if hash_ok else 'MISMATCH'}")
        if not hash_ok:
            print(f"Expected: {args.expected_sha256}")
    print(f"Tag:      {tag}  {'OK' if result['tag_ok'] else f'UNEXPECTED (expected {EXPECTED_TAG})'}")
    print(f"Version:  {version}  {'OK' if result['version_ok'] else f'UNEXPECTED (expected {EXPECTED_VERSION})'}")
    print()
    print("Hook audit (eagle-harness 0.1.4 contract)")
    for hook in result["hooks"]:
        status = "ok" if hook["found"] else "MISSING"
        where = f" (line {hook['line']})" if hook["line"] else ""
        print(f"  [{status:7}] {hook['need']:<28} {hook['file']}{where}")
    present = sum(1 for h in result["hooks"] if h["found"])
    print()
    print(f"{present}/{len(result['hooks'])} hooks present")
    print("RESULT: PASS" if result["ok"] else "RESULT: FAIL")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
