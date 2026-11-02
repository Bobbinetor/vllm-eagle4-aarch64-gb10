# Verification

This document separates what was **statically verified in this repository** from
what was **observed at runtime by the maintainer** on the build machine. It also
lists what was not tested.

## 1. Artifact identity

| Field | Value |
|---|---|
| Filename | `vllm-0.32.0rc1.dev283+eagle.3-cp312-cp312-linux_aarch64.whl` |
| Size | 494,300,662 bytes (471 MiB) |
| SHA-256 | `fbd7ec77a34f608b4158d7a7196f75a1f78100da3645825e0a30657f72408237` |
| Wheel tag | `cp312-cp312-linux_aarch64` |
| Version | `0.32.0rc1.dev283+eagle.3` |
| Unpacked | 1,749,788,179 bytes, 5,542 files |
| Built from | `eagle-hq/vllm` @ `3ba23801e80d2a0d0a9af21ce94484aa2adb8795` (tag `eagle/v0.1.0`, committed 2026-10-20) |
| Base image | `vllm/vllm-openai:latest` @ `sha256:c1c9f6fd5c109ba7f0546a59f5b2f15fb87f64c77782e90a27b648b42a8e67c3` (2026-10-03) |
| Build date | 2026-10-30 |
| Build flags | `TORCH_CUDA_ARCH_LIST=12.1a`, `MAX_JOBS=16`, Python 3.12 |

Upstream's current reference build is `0.32.0rc1.dev283+eagle.5` (`main
074c83a09a` + hooks and fixes). This wheel is `+eagle.3` from tag `eagle/v0.1.0`.
`eagle-harness` 0.1.4 accepts both (`>=0.32.0rc1.dev283,!=0.32.0`), and the hook
surface audited below is the same.

The wheel is a real aarch64 ELF build. Example:

```text
vllm/_C_stable_libtorch.abi3.so: ELF 64-bit LSB shared object, ARM aarch64,
version 1 (GNU/Linux), dynamically linked, with debug_info, not stripped
```

## 2. Static hook audit (reproducible here, no GPU)

`eagle-harness` refuses to register on a vLLM that lacks the hooks in
`eagle_harness.vllm.adapter.HOOK_MAP` (version 0.1.4). The audit opens the wheel
as a zip and checks those exact symbols without importing vLLM:

```bash
python3 scripts/audit_hooks.py vllm-0.32.0rc1.dev283+eagle.3-cp312-cp312-linux_aarch64.whl
```

Result on 2026-10-30:

```text
SHA-256:  fbd7ec77a34f608b4158d7a7196f75a1f78100da3645825e0a30657f72408237  OK
Tag:      cp312-cp312-linux_aarch64  OK
Version:  0.32.0rc1.dev283+eagle.3  OK

Hook audit (eagle-harness 0.1.4 contract)
  [ok     ] algorithm registration       vllm/v1/spec_decode/registry.py (line 80)
  [ok     ] opaque algorithm config      vllm/config/speculative.py (line 413)
  [ok     ] method configure             vllm/v1/spec_decode/registry.py (line 45)
  [ok     ] KV headroom (lookahead)      vllm/v1/spec_decode/registry.py (line 60)
  [ok     ] draft + KV slots (propose)   vllm/v1/worker/gpu/spec_decode/speculator.py (line 84)
  [ok     ] target verify inputs         vllm/v1/worker/gpu/spec_decode/speculator.py (line 134)
  [ok     ] verify accept                vllm/v1/worker/gpu/spec_decode/speculator.py (line 114)
  [ok     ] accepted-path KV compaction  vllm/v1/worker/gpu/spec_decode/speculator.py (line 158)
  [ok     ] GDN tree verify              vllm/model_executor/layers/mamba/gdn/verify_extension.py (line 135)
  [ok     ] tree attention backend       vllm/v1/attention/backends/registry.py (line 165)

10/10 hooks present
RESULT: PASS
```

The hook files carry `SPDX-License-Identifier: Apache-2.0` and copyright the
vLLM contributors. The wheel's `METADATA` declares `License-Expression:
Apache-2.0`.

### Why these ten hooks

| Hook | Used for |
|---|---|
| `register_speculative_method` | Register `eagle_harness` as an out-of-tree method |
| `SpeculativeConfig.method_config` | Pass opaque EAGLE-4 options (`tree_depth`, `node_top_k`, ...) |
| `SpeculativeMethodSpec.configure` | Fill token budget / draft config from those options |
| `SpeculativeMethodSpec.num_lookahead_tokens` | Reserve KV headroom for the tree |
| `DraftModelSpeculator.propose` | Run the draft and allocate KV slots |
| `BaseSpeculator.prepare_verify_inputs` | Build target-verify positions and tree mask |
| `BaseSpeculator.make_rejection_sampler` | Accept/reject verification |
| `BaseSpeculator.post_accept` | Compact the accepted path's KV |
| `LinearAttnVerifyExtension.forward_spec_rows` | GDN tree verify for hybrid models |
| `AttentionBackendEnum.CUSTOM` | Tree attention backend |

The contract is pinned to `eagle-harness` 0.1.4. A future harness release may
add or rename hooks; re-run the audit after upgrading.

## 3. Runtime evidence (maintainer, 2026-10-30)

Internal image/tag names are generalized; the versions and results are unchanged.

Environment:

| Field | Value |
|---|---|
| Machine | DGX Spark GB10, aarch64, 20 cores, 121 GB unified memory |
| OS | Ubuntu 24.04.5 LTS |
| Driver | 580.159.03 (CUDA 13.0) |
| Image | `vllm-eagle:gb10` (built from this wheel) |
| vLLM in image | `0.32.0rc1.dev283+eagle.3` |
| torch in image | `2.14.0+cu130` |
| Draft | `EAGLE-Corp/Qwen3.8-27B-EAGLE4` |
| Target | `nvidia/Qwen3.8-27B-NVFP4` |

`eagle-harness-check` exited 0 and the wrapper printed `HOOKS_OK`. The exact
per-host report was not captured; only the exit status and the `HOOKS_OK` marker
are recorded.

Server log lines:

```text
Resolved architecture: LlamaForCausalLMEagle4
eagle-harness: registered speculative method eagle_harness and draft LlamaForCausalLMEagle4
```

Smoke suite (`scripts/smoke.sh`): **6/6 PASS** — health, models, chat, tool_call,
streaming, long_context.

Agent test: a tool-use run with the `shell` tool (`echo EAGLE4-OK`) completed
with one tool call.

Throughput and TTFT: **not a published claim**. The initial single-machine
numbers were withdrawn because they were not independently reproducible. No
performance number in this document is verified. `scripts/bench.py` implements
the method; [`BENCHMARKING.md`](BENCHMARKING.md) has the controlled variables and
the report template. Verified community results will be added to the README with
the reporter's hardware and command.

## 4. What was not verified

- Independent reproduction on a second DGX Spark.
- Multi-user / high-concurrency throughput.
- Sustained load, thermal behavior, or long-running stability.
- Acceptance rate and per-position acceptance (the original run did not log
  them; `scripts/bench.py --metrics-url` can collect them).
- Other target models or other EAGLE-4 drafts.
- x86_64, GH200, Grace Hopper, Jetson, or any non-sm_121 GPU.
- A full 64K-token prompt: the smoke suite's long-context case passed, but the
  exact token count and needle-in-a-haystack behavior were not recorded.
- The claim that every compiled kernel has a native sm_121 cubin. The build was
  configured with `TORCH_CUDA_ARCH_LIST=12.1a`; a cubin-level audit was not
  performed.

If you need any of these before production use, measure them. The scripts are
here so your result can be added without guessing.

## 5. Reproduce the checks

```bash
# checksums + tag + hooks
./scripts/verify.sh

# static hook audit only
python3 scripts/audit_hooks.py vllm-*.whl

# runtime smoke (server must be up)
BASE_URL=http://127.0.0.1:8000 ./scripts/smoke.sh

# optional: measure on your machine and report (no published claim)
python3 scripts/bench.py --preset agentic --requests 3 \
  --metrics-url http://127.0.0.1:8000/metrics \
  --json-out bench-$(date +%Y%m%d-%H%M%S).json
```

## 6. Release asset verification (GitHub Actions)

The wheel is a GitHub Release asset, not a git object. Two workflows keep the
published artifact honest:

| Workflow | When | What it proves |
|---|---|---|
| `ci.yml` | every push / PR | links, sources, tracked checksums, no leaked paths or tokens |
| `release-verify.yml` | after a release is published | the **published** wheel downloads, matches `SHA256SUMS`, and passes the 10-hook audit |

`release-verify` does not trust the build machine: it fetches the asset from the
release URL with the GitHub token, runs `sha256sum -c --ignore-missing
SHA256SUMS`, and then runs `scripts/audit_hooks.py` on the downloaded file. The
badge in the README is that job's status. A failed run means the release asset
does not match the manifest: do not run it.

To reproduce the same check locally on the published file:

```bash
gh release download v0.1.0 --pattern '*.whl' --pattern 'SHA256SUMS'
sha256sum -c --ignore-missing SHA256SUMS
python3 scripts/audit_hooks.py vllm-*.whl
```
