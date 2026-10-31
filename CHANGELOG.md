# Changelog

All notable changes to this repository. The wheel is attached to each GitHub
Release; it is never committed to git.

## v0.1.0 — 2026-11-01

First public GitHub Release. The artifact is the wheel built and tested on
2026-10-30.

### Added

- Release packaging for GitHub: `docs/releases/v0.1.0.md`, `scripts/release.sh`
  (dry run by default), and a manual `release` workflow that verifies the wheel
  before creating a draft release.
- `release-verify` workflow: re-downloads every published asset, checks
  `SHA256SUMS`, and re-runs the 10-hook static audit. The badge in the README is
  its result.
- `ci` workflow and `scripts/check_repo.py`: links, Python/JSON syntax, tracked
  checksums, and a leak scan for tokens and private paths.
- Issue forms for run reports and bugs, plus `CONTRIBUTING.md`, `SECURITY.md`,
  and `CODE_OF_CONDUCT.md`.
- `scripts/verify.sh` now tolerates a source-only checkout and points to the
  release download when the wheel is absent.

### Artifact

- `vllm-0.32.0rc1.dev283+eagle.3-cp312-cp312-linux_aarch64.whl`
  (494,300,662 bytes; SHA-256
  `fbd7ec77a34f608b4158d7a7196f75a1f78100da3645825e0a30657f72408237`).
- Built from `eagle-hq/vllm` @ `3ba23801e80d2a0d0a9af21ce94484aa2adb8795`
  (tag `eagle/v0.1.0`).
- Base image: `vllm/vllm-openai:latest` @
  `sha256:c1c9f6fd5c109ba7f0546a59f5b2f15fb87f64c77782e90a27b648b42a8e67c3`.
- `TORCH_CUDA_ARCH_LIST=12.1a`, `MAX_JOBS=16`, Python 3.12.
- `eagle-harness-check`: every hook present (10/10 static audit).
- Runtime smoke: health, models, chat, tool calls, streaming, 64K context.
- Single-stream benchmark on DGX Spark (GB10), Qwen3.8-27B NVFP4:
  - base 12.17 tok/s agentic / 12.13 tok/s echo
  - DFlash2 29.10 / 29.22
  - EAGLE-4 35.17 / 53.05, TTFT 239 ms agentic

### Known deltas

- The wheel reports `+eagle.3` even when the build sets
  `SETUPTOOLS_SCM_PRETEND_VERSION=...+eagle.5`; the fork's local version scheme
  wins. `eagle-harness` 0.1.4 accepts it (`>=0.32.0rc1.dev283,!=0.32.0`).
  Upstream's current reference build is `+eagle.5` (`main 074c83a09a` + hooks and
  fixes); the hook contract is the same. Rebuild from that commit if you need
  exact reference parity.
- The wheel is built against torch 2.13.0 but the final image runs
  torch 2.14.0+cu130 because `pip install "eagle-harness[vllm]"` resolves a
  newer torch. This is the tested combination.
- `flashinfer_cutedsl` is not used: there is no `flashinfer-python` arm64 wheel.
  The default linear backend is used.
