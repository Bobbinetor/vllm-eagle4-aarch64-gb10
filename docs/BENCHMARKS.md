# Benchmarks

## TL;DR

Single DGX Spark (GB10), Qwen3.8-27B NVFP4, 64K context, **concurrency 1**,
3 requests, temperature 0, `max_tokens=256`:

| Configuration | Agentic tok/s | Echo tok/s | TTFT (agentic) |
|---|---:|---:|---:|
| Base (no speculative decoding) | 12.17 | 12.13 | 141 ms |
| DFlash2 | 29.10 | 29.22 | 138 ms |
| **EAGLE-4** | **35.17** | **53.05** | 239 ms |

These are **end-to-end** completion tokens divided by wall time, not decode-only
tok/s. The aggregate record is
[`bench/aggregate-2026-10-30.json`](../bench/aggregate-2026-10-30.json).

## What the numbers mean

- **EAGLE-4 vs base:** ~2.9× on the agentic prompt, ~4.4× on the synthetic echo
  prompt.
- **EAGLE-4 vs DFlash2:** ~1.2× on agentic, ~1.8× on echo.
- **TTFT:** EAGLE-4 is slower to first token (239 ms vs 138 ms for DFlash2)
  because tree verification does work before the first accepted token. For
  short, latency-sensitive prompts, DFlash2 can feel better. For decode-bound
  work, EAGLE-4 is faster.
- **The echo prompt is synthetic.** It repeats one sentence 40 times, which is
  close to the best case for any speculative decoder. Do not quote 53 tok/s as
  a general-purpose number.

## Method

| Item | Value |
|---|---|
| Machine | NVIDIA DGX Spark, GB10, 121 GB unified memory |
| OS | Ubuntu 24.04.5 LTS |
| Driver | 580.159.03 (CUDA 13.0) |
| Image | `vllm-eagle:gb10` |
| vLLM | `0.32.0rc1.dev283+eagle.3` |
| torch | `2.14.0+cu130` |
| Harness | `eagle-harness` 0.1.4 |
| Target | `nvidia/Qwen3.8-27B-NVFP4` |
| Draft | `EAGLE-Corp/Qwen3.8-27B-EAGLE4` |
| Context | 65536 |
| GPU memory utilization | 0.45 |
| Max sequences | 4 |
| Concurrency | 1 |
| Requests per preset | 3 |
| Temperature | 0 |
| Max tokens | 256 |

The original run used a private benchmark harness. It did not retain per-request
samples, and it did not log acceptance rate. The values above are aggregates.

## Reproduce the method

`scripts/bench.py` is a self-contained, standard-library reimplementation of the
same method: streaming chat completions, `stream_options.include_usage`, TTFT
from the first content delta, end-to-end tok/s from `usage.completion_tokens`.
It uses different prompt text, so expect small differences.

```bash
python3 scripts/bench.py \
  --base-url http://127.0.0.1:8000 \
  --model qwen3.8-27b-eagle \
  --preset agentic \
  --requests 3 \
  --warmup 1 \
  --max-tokens 256 \
  --temperature 0 \
  --metrics-url http://127.0.0.1:8000/metrics \
  --json-out bench-agentic.json
```

The script reports:

- `ttft_s` — time to first streamed content token.
- `e2e_tok_s` — completion tokens / total wall time.
- `decode_tok_s` — (completion tokens − 1) / (end − first token).
- `spec_decode.acceptance_rate` — accepted / draft tokens, from the Prometheus
  counter delta, when `--metrics-url` is supplied.

For a fair comparison, run the same script against the same server with
`--speculative-config` removed (base) and with the DFlash2 profile.

## Caveats

1. **One machine, one run.** No error bars, no second DGX Spark.
2. **Concurrency 1.** This says nothing about throughput at 4, 8, or 64
   concurrent requests.
3. **Synthetic prompts.** The agentic prompt is a fixed 200-word explanation;
   the echo prompt is deliberately repetitive.
4. **No acceptance-rate data** in the original run. The tree shape
   (`tree_depth=14`, `node_top_k=4`, `max_verify_width=16`) was not tuned per
   workload.
5. **Not comparable to the EAGLE-4 paper.** Upstream reports 2.83× for vLLM on
   4×B300 with multi-user workloads; this is a single GB10.
6. **torch mismatch.** The wheel was built against torch 2.13.0; the final image
   runs 2.14.0+cu130 after installing `eagle-harness[vllm]`. That is the tested
   combination, but it is not a controlled A/B of torch versions.

## Upstream reference

The EAGLE-4 install guide reports:

| Engine | GPUs | 1 request | 8 concurrent | 64 concurrent |
|---|---|---:|---:|---:|
| SGLang | 4× B300 | 3.42× | 2.09× | 1.39× |
| vLLM | 4× B300 | 2.83× | 1.72× | 1.14× |
| TokenSpeed | 4× B300 | 3.09× | 2.02× | 1.41× |

Use those numbers for the upstream claim; use the table at the top of this page
for the GB10 / aarch64 build.
