#!/usr/bin/env bash
# Verify the wheel, the host, and (if installed) the EAGLE-4 hooks.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

fail=0
ok()   { printf '  [ok]   %s\n' "$*"; }
warn() { printf '  [warn] %s\n' "$*"; }
bad()  { printf '  [FAIL] %s\n' "$*"; fail=1; }

echo "== Host =="
os="$(uname -s)"
arch="$(uname -m)"
if [[ "$os" == "Linux" && ( "$arch" == "aarch64" || "$arch" == "arm64" ) ]]; then
  ok "platform: $os/$arch"
else
  bad "platform: $os/$arch (this wheel is linux_aarch64 only)"
fi

if command -v nvidia-smi >/dev/null 2>&1; then
  gpu="$(nvidia-smi --query-gpu=name,driver_version --format=csv,noheader | head -1 || true)"
  ok "GPU: $gpu"
  if [[ "$gpu" != *GB10* && "$gpu" != *"DGX Spark"* ]]; then
    warn "not a GB10 / DGX Spark; this build targets sm_121 and may not run"
  fi
else
  warn "nvidia-smi not found; skipping GPU check"
fi

if command -v python3 >/dev/null 2>&1; then
  py="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
  if [[ "$py" == "3.12" ]]; then
    ok "python: $py"
  else
    warn "python: $py (the wheel is cp312; use a 3.12 environment)"
  fi
fi

echo
echo "== Checksums =="
# The manifest covers the wheel (a release asset) and the recipe files. The
# wheel may legitimately be absent in a source-only checkout, so it is checked
# only when present; missing recipe files are still an error.
if command -v sha256sum >/dev/null 2>&1; then
  if sha256sum -c --ignore-missing SHA256SUMS; then
    ok "SHA256SUMS (files present)"
  else
    bad "SHA256SUMS"
  fi
else
  rc=0
  python3 - <<'PY' || rc=$?
import hashlib
import pathlib
import sys

bad = 0
for line in pathlib.Path("SHA256SUMS").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    expected, name = line.split()
    path = pathlib.Path(name)
    if not path.exists():
        if path.suffix == ".whl":
            print(f"  [skip] {name} (release asset, not downloaded)")
        else:
            print(f"  [FAIL] {name} missing")
            bad = 1
        continue
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        print(f"  [FAIL] {name} hash mismatch")
        bad = 1
    else:
        print(f"  [ok]   {name}")
sys.exit(bad)
PY
  if [[ "$rc" -eq 0 ]]; then
    ok "SHA256SUMS (files present)"
  else
    bad "SHA256SUMS"
  fi
fi

echo
echo "== Wheel =="
wheel="$(ls -1 vllm-*.whl 2>/dev/null | head -1 || true)"
if [[ -z "$wheel" ]]; then
  bad "no vllm-*.whl in the repository root"
  echo "         Download it from the GitHub Release:"
  echo "         gh release download --pattern '*.whl' --pattern 'SHA256SUMS'"
else
  ok "wheel: $wheel"
  python3 scripts/audit_hooks.py "$wheel" || fail=1
fi

echo
echo "== EAGLE-4 hooks (runtime) =="
if command -v eagle-harness-check >/dev/null 2>&1; then
  if eagle-harness-check; then
    ok "eagle-harness-check"
  else
    bad "eagle-harness-check"
  fi
else
  warn "eagle-harness-check not installed (run inside the image or a venv with eagle-harness[vllm])"
fi

echo
if [[ "$fail" -eq 0 ]]; then
  echo "RESULT: PASS"
else
  echo "RESULT: FAIL"
fi
exit "$fail"
