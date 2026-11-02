# Benchmarking and reporting results

This repository does **not** publish a performance claim. The first numbers came
from one DGX Spark, one run, and were not independently reproducible, so they
were withdrawn. What follows is the method, the variables to control, and the
report template — so a result from your machine can be compared with another.

## What to measure

| Metric | Why it matters |
|---|---|
| `ttft_s` | Time to the first streamed content token. Tree verification costs work before the first accepted token. |
| `e2e_tok_s` | Completion tokens divided by total wall time. This is the number most people mean by "tok/s". |
| `decode_tok_s` | (completion tokens − 1) / (end − first token). Separates decode from prefill. |
| `spec_decode.acceptance_rate` | Accepted / draft tokens, when `/metrics` is available. Explains *why* a number moved. |

## Run it

The server must already be up (see the README quick start).

```bash
# Agentic prompt, three requests, one warm-up
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

# Repetitive prompt (synthetic; do not generalise from it)
python3 scripts/bench.py --preset echo --requests 3 --json-out bench-echo.json
```

Run the same command on the same server with `--speculative-config` removed to
get the base number. A comparison is only meaningful when the prompt, the token
budget, the context length, and the concurrency are identical.

## Control these variables

| Variable | Why it changes the result |
|---|---|
| Hardware and power mode | A GB10 at a different power limit or thermal state is a different machine. |
| Driver / CUDA / torch / vLLM / harness versions | Kernel selection and JIT behavior change between versions. |
| `max_model_len`, `gpu_memory_utilization`, `max_num_seqs` | KV cache size and scheduler behavior. |
| `tree_depth`, `node_top_k`, `max_verify_width` | Draft-tree shape: more lookahead is not always faster. |
| Prompt text and `max_tokens` | The echo prompt is a best case, not a workload. |
| Concurrency | A single-stream win can disappear at 8 or 64 concurrent requests. |
| Warm-up | The first request can include CUDA graph capture or PTX JIT. |

## Report template

Open a **Run report** issue (or a Discussion) with:

```text
Hardware:   DGX Spark / GB10, 121 GB, power mode <...>
OS/driver:  Ubuntu <...>, driver <...>
Versions:   vLLM <...>, torch <...>, eagle-harness <...>
Command:    <the exact scripts/bench.py line>
Context:    max_model_len=<...>, gpu_memory_utilization=<...>, max_num_seqs=<...>
Spec config:<tree_depth=..., node_top_k=..., max_verify_width=...> (or "base")
Result:     ttft_s=<...>, e2e_tok_s=<...>, decode_tok_s=<...>, acceptance_rate=<...>
Repeats:    <how many runs; report mean and spread>
Notes:      <anything unusual: JIT, throttling, other workloads>
```

## Rules for adding a result here

- One result is an anecdote; three runs with a spread is a measurement.
- Report the method, not just the best number.
- Say what did **not** improve. A negative result is a valid result.
- Do not compare against the upstream paper's 4×B300 numbers; it is a different
  hardware class and a different workload.
- If a later run contradicts an earlier one, say so and link both.

Verified reports will be added to the README table with the reporter's hardware
and the exact command. Until then, the README stays without numbers.
