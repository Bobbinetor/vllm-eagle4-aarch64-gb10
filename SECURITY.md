# Security

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting:

**Security → Advisories → [Report a vulnerability](https://github.com/Bobbinetor/vllm-eagle4-aarch64-gb10/security/advisories/new)**

Do not open a public issue for a suspected vulnerability. Include the release
tag, the wheel SHA-256, the command you ran, and the smallest reproduction you
can produce. You should get an answer within 7 days.

## What is in scope

- The published wheel (`vllm-*.whl`) and its checksum manifest.
- The Dockerfile and scripts in this repository.
- The GitHub Actions workflows that build or verify a release.

## What is not in scope

- Vulnerabilities in upstream vLLM, PyTorch, CUDA, or `eagle-harness`. Report
  those to their maintainers; this repository only redistributes a build.
- The EAGLE-4 draft model or the Qwen3.8-27B model weights. They are downloaded
  from their official repositories and are not part of this release.
- "It runs code from a model with `--trust-remote-code`". That flag is required
  by the upstream serving recipe and is documented in the README.

## Verifying an artifact

Before running a downloaded wheel:

```bash
sha256sum -c --ignore-missing SHA256SUMS
python3 scripts/audit_hooks.py vllm-*.whl
```

The expected SHA-256 is also printed on the release page and in
[`docs/VERIFICATION.md`](docs/VERIFICATION.md). The `release-verify` workflow
re-downloads every published asset and re-runs these checks; its badge is in the
README. If a checksum ever fails, stop and open an issue.
