#!/usr/bin/env bash
# OpenAI-compatible smoke test for the EAGLE-4 server.
# Usage: BASE_URL=http://127.0.0.1:8000 MODEL=qwen3.8-27b-eagle ./scripts/smoke.sh
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
MODEL="${MODEL:-qwen3.8-27b-eagle}"
fail=0
ok()  { printf '  [ok]   %s\n' "$*"; }
bad() { printf '  [FAIL] %s\n' "$*"; fail=1; }

echo "== Health =="
if curl -fsS --max-time 30 "$BASE_URL/health" >/dev/null; then
  ok "/health"
else
  bad "/health"
fi

echo "== Models =="
if curl -fsS --max-time 30 "$BASE_URL/v1/models" | python3 -c "import sys,json; d=json.load(sys.stdin); ids=[m['id'] for m in d.get('data',[])]; assert '$MODEL' in ids, ids; print('  model:', '$MODEL')"; then
  ok "/v1/models lists $MODEL"
else
  bad "/v1/models does not list $MODEL"
fi

echo "== Chat =="
chat_resp="$(curl -fsS --max-time 120 "$BASE_URL/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with OK only\"}],\"max_tokens\":16,\"temperature\":0}")" || true
if [[ -n "$chat_resp" ]] && echo "$chat_resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['choices'][0]['message']['content'])"; then
  ok "chat completion"
else
  bad "chat completion"
fi

echo "== Tool call =="
tool_resp="$(curl -fsS --max-time 120 "$BASE_URL/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Weather in Rome? Use get_weather.\"}],\"tools\":[{\"type\":\"function\",\"function\":{\"name\":\"get_weather\",\"parameters\":{\"type\":\"object\",\"properties\":{\"city\":{\"type\":\"string\"}},\"required\":[\"city\"]}}}],\"max_tokens\":256,\"temperature\":0}")" || true
if [[ -n "$tool_resp" ]] && echo "$tool_resp" | python3 -c "import sys,json; m=json.load(sys.stdin)['choices'][0]['message']; assert m.get('tool_calls'), m; print(m['tool_calls'][0]['function']['name'])"; then
  ok "tool_calls returned"
else
  bad "tool_calls missing (check --enable-auto-tool-choice and --tool-call-parser qwen3_coder)"
fi

echo "== Streaming =="
stream_out="$(curl -fsS -N --max-time 120 "$BASE_URL/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Count from 1 to 5.\"}],\"max_tokens\":64,\"temperature\":0,\"stream\":true}" || true)"
if [[ "$(grep -c '^data: ' <<<"$stream_out" || true)" -ge 2 ]] && grep -q '\[DONE\]' <<<"$stream_out"; then
  ok "SSE stream with [DONE]"
else
  bad "streaming did not produce SSE chunks"
fi

if [[ "${LONG_CONTEXT:-0}" == "1" ]]; then
  echo "== Long context (optional) =="
  tmp_json="$(mktemp)"
  python3 - "$MODEL" >"$tmp_json" <<'PY'
import json, sys
prompt = "The quick brown fox jumps over the lazy dog. " * 4000 + " Reply with OK."
print(json.dumps({"model": sys.argv[1], "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 16, "temperature": 0}))
PY
  long_resp="$(curl -fsS --max-time 600 "$BASE_URL/v1/chat/completions" \
    -H 'Content-Type: application/json' -d @"$tmp_json")" || true
  rm -f "$tmp_json"
  if [[ -n "$long_resp" ]] && echo "$long_resp" | python3 -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'])"; then
    ok "long-context completion"
  else
    bad "long-context completion"
  fi
fi

echo
if [[ "$fail" -eq 0 ]]; then
  echo "RESULT: PASS"
else
  echo "RESULT: FAIL"
fi
exit "$fail"
