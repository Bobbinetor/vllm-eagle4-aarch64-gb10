# Contributing

This repository distributes a **prebuilt binary** and the evidence around it.
The most valuable contributions are not code changes: they are run reports that
confirm or contradict the numbers, and fixes to the build recipe when a pin
drifts.

## Before you open a PR

```bash
make check
bash -n scripts/*.sh build/*.sh
python3 scripts/audit_hooks.py vllm-*.whl   # if you have the wheel
```

`make check` verifies links, Python/JSON syntax, the tracked-file checksums, and
that no token or private path leaked. CI runs the same checks.

## What is welcome

- **Run reports** on other DGX Spark units, with `eagle-harness-check` and
  `scripts/audit_hooks.py` output. Open a Discussion or the *Run report* issue
  form; verified results are added to the README.
- **Build-recipe fixes**: a pin that moved, a missing system package, a cleaner
  workaround for one of the seven documented failures.
- **Script fixes** that make verification or benchmarking more reliable.
- **Documentation fixes** for the README, the build record, and the verification docs.
- **Negative results** with enough detail to reproduce the failure.

## What is not accepted

- The wheel, model weights, or any file above GitHub's 100 MB limit. The wheel
  is a release asset; models are downloaded from their official repositories.
- `eagle-harness` source or binaries. It is source-available, not OSI open
  source, and is installed from PyPI.
- Re-licensing, removing the "unofficial" disclaimer, or implying endorsement by
  Eagle AI Corp. or NVIDIA.
- Marketing copy, "first" claims, or benchmark numbers without a method.

## Licensing

By contributing you agree that your contribution is licensed under
**Apache-2.0**, the license of this repository and of the vLLM build. Do not
paste code under a different license. See [`docs/LICENSING.md`](docs/LICENSING.md)
and [`NOTICE`](NOTICE).

## Releases

Releases are cut by the maintainer with `scripts/release.sh` (dry run by
default) or the manual **release** workflow. The wheel is never committed; it is
attached to the GitHub Release and re-verified by `release-verify.yml`.
