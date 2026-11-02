#!/usr/bin/env python3
"""OpenAI-compatible benchmark for the EAGLE-4 vLLM server.

Measures TTFT, end-to-end tok/s, and decode tok/s with streaming. Optionally
scrapes vLLM's Prometheus endpoint to report speculative-decoding acceptance.

The original measurements used a private harness and were withdrawn because
they were not independently reproducible. This script is the reproducible
method: run it on your machine and report the result (see docs/BENCHMARKING.md).

Usage:
    python3 scripts/bench.py --preset agentic --requests 3
    python3 scripts/bench.py --preset echo --requests 3 --metrics-url http://127.0.0.1:8000/metrics
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

PRESETS = {
    "agentic": (
        "You are a careful software engineer. Explain, in about 200 words, why "
        "automated tests matter for a production LLM serving stack. Be concrete "
        "and mention at least three failure modes that tests catch."
    ),
    "echo": (
        "Repeat the following sentence exactly, without any commentary, 40 times: "
        "\"The quick brown fox jumps over the lazy dog.\""
    ),
    "code": (
        "Write a Python function that merges two sorted lists into one sorted list. "
        "Include a docstring, type hints, and three unit tests. Then explain the "
        "time complexity in two sentences."
    ),
}


def post_stream(url: str, payload: dict, api_key: str | None, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    t0 = time.perf_counter()
    ttft = None
    usage = None
    text_parts: list[str] = []
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    break
                obj = json.loads(chunk)
                if obj.get("usage"):
                    usage = obj["usage"]
                for choice in obj.get("choices") or []:
                    delta = choice.get("delta") or {}
                    content = delta.get("content")
                    if content:
                        if ttft is None:
                            ttft = time.perf_counter() - t0
                        text_parts.append(content)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc

    end = time.perf_counter()
    if ttft is None:
        ttft = end - t0

    completion_tokens = (usage or {}).get("completion_tokens")
    prompt_tokens = (usage or {}).get("prompt_tokens")
    e2e = end - t0
    decode_s = max(end - t0 - ttft, 1e-9)

    return {
        "ttft_s": ttft,
        "e2e_s": e2e,
        "completion_tokens": completion_tokens,
        "prompt_tokens": prompt_tokens,
        "e2e_tok_s": (completion_tokens / e2e) if completion_tokens else None,
        "decode_tok_s": ((completion_tokens - 1) / decode_s) if completion_tokens and completion_tokens > 1 else None,
        "chars": sum(len(p) for p in text_parts),
    }


def scrape_metrics(url: str, timeout: float = 10.0) -> dict[str, float]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", "replace")
    except Exception as exc:  # metrics are optional; never fail the benchmark
        print(f"warning: could not scrape {url}: {exc}", file=sys.stderr)
        return {}
    values: dict[str, float] = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            values[parts[0]] = float(parts[1])
        except ValueError:
            continue
    return values


def spec_decode_delta(before: dict[str, float], after: dict[str, float]) -> dict[str, float]:
    keys = [k for k in after if "spec_decode" in k]
    delta = {k: after[k] - before.get(k, 0.0) for k in keys}
    draft_key = min((k for k in delta if "draft_tokens_total" in k), key=len, default=None)
    accepted_key = min((k for k in delta if k.endswith("accepted_tokens_total")), key=len, default=None)
    draft = delta[draft_key] if draft_key else None
    accepted = delta[accepted_key] if accepted_key else None
    if draft and accepted is not None and draft > 0:
        delta["acceptance_rate"] = accepted / draft
    return delta


def summarize(values: list[float]) -> dict[str, float] | None:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return {
        "mean": statistics.fmean(clean),
        "median": statistics.median(clean),
        "min": min(clean),
        "max": max(clean),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Benchmark an OpenAI-compatible EAGLE-4 server.")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--model", default="qwen3.8-27b-eagle")
    ap.add_argument("--preset", choices=sorted(PRESETS) + ["custom"], default="agentic")
    ap.add_argument("--prompt", default=None, help="prompt for --preset custom")
    ap.add_argument("--requests", type=int, default=3)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--timeout", type=float, default=600.0)
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--metrics-url", default=None, help="e.g. http://127.0.0.1:8000/metrics")
    ap.add_argument("--label", default="")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args(argv)

    if args.preset == "custom":
        if not args.prompt:
            ap.error("--preset custom requires --prompt")
        prompt = args.prompt
    else:
        prompt = PRESETS[args.preset]

    url = args.base_url.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    print(f"model={args.model} preset={args.preset} requests={args.requests} max_tokens={args.max_tokens}")
    for i in range(args.warmup):
        print(f"warmup {i + 1}/{args.warmup} ...", flush=True)
        post_stream(url, payload, args.api_key, args.timeout)

    before = scrape_metrics(args.metrics_url) if args.metrics_url else {}
    results = []
    for i in range(args.requests):
        try:
            r = post_stream(url, payload, args.api_key, args.timeout)
        except Exception as exc:
            print(f"request {i + 1} failed: {exc}", file=sys.stderr)
            return 1
        results.append(r)
        e2e = f"{r['e2e_tok_s']:.2f}" if r["e2e_tok_s"] else "?"
        dec = f"{r['decode_tok_s']:.2f}" if r["decode_tok_s"] else "?"
        print(
            f"  {i + 1}/{args.requests}: ttft={r['ttft_s'] * 1000:.0f} ms  "
            f"e2e={e2e} tok/s  decode={dec} tok/s  tokens={r['completion_tokens']}",
            flush=True,
        )
    after = scrape_metrics(args.metrics_url) if args.metrics_url else {}

    summary = {
        "ttft_s": summarize([r["ttft_s"] for r in results]),
        "e2e_tok_s": summarize([r["e2e_tok_s"] for r in results]),
        "decode_tok_s": summarize([r["decode_tok_s"] for r in results]),
        "completion_tokens": summarize([r["completion_tokens"] for r in results]),
    }
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "label": args.label,
        "host": platform.node(),
        "platform": platform.platform(),
        "base_url": args.base_url,
        "model": args.model,
        "preset": args.preset,
        "requests": args.requests,
        "warmup": args.warmup,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "results": results,
        "summary": summary,
        "spec_decode": spec_decode_delta(before, after) if args.metrics_url else None,
    }

    print("\nSummary")
    for key, label in (("ttft_s", "TTFT (ms)"), ("e2e_tok_s", "end-to-end tok/s"), ("decode_tok_s", "decode tok/s")):
        s = summary[key]
        if not s:
            continue
        if key == "ttft_s":
            print(f"  {label:<18} mean={s['mean'] * 1000:.0f}  median={s['median'] * 1000:.0f}  min={s['min'] * 1000:.0f}  max={s['max'] * 1000:.0f}")
        else:
            print(f"  {label:<18} mean={s['mean']:.2f}  median={s['median']:.2f}  min={s['min']:.2f}  max={s['max']:.2f}")

    if report["spec_decode"]:
        print("\nSpeculative decoding (Prometheus delta)")
        for key, value in sorted(report["spec_decode"].items()):
            if key == "acceptance_rate":
                print(f"  acceptance_rate: {value:.3f}")
            elif "accepted_tokens_total" in key or "draft_tokens_total" in key:
                print(f"  {key}: {value:.0f}")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"\nwrote {args.json_out}")
    else:
        print("\nJSON")
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
