#!/usr/bin/env bash
# Start the EAGLE-4 server with the validated profile.
# Override any value with an environment variable, e.g.:
#   PORT=8001 GPU_UTIL=0.40 ./scripts/serve.sh
set -euo pipefail

IMAGE="${IMAGE:-vllm-eagle:gb10}"
CONTAINER="${CONTAINER:-vllm-eagle}"
MODEL="${MODEL:-nvidia/Qwen3.8-27B-NVFP4}"
DRAFT="${DRAFT:-EAGLE-Corp/Qwen3.8-27B-EAGLE4}"
SERVED_NAME="${SERVED_NAME:-qwen3.8-27b-eagle}"
PORT="${PORT:-8000}"
MAX_LEN="${MAX_LEN:-65536}"
GPU_UTIL="${GPU_UTIL:-0.45}"
MAX_SEQS="${MAX_SEQS:-4}"
TREE_DEPTH="${TREE_DEPTH:-14}"
NODE_TOP_K="${NODE_TOP_K:-4}"
MAX_VERIFY_WIDTH="${MAX_VERIFY_WIDTH:-16}"
HF_CACHE="${HF_CACHE:-$HOME/.cache/huggingface}"
OFFLINE="${OFFLINE:-1}"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image $IMAGE not found. Build it first:"
  echo "  docker build -f docker/Dockerfile.eagle -t $IMAGE ."
  exit 1
fi

if docker container inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "Container $CONTAINER already exists. Remove it with: docker rm -f $CONTAINER"
  exit 1
fi

spec_config=$(printf '{"method":"eagle_harness","model":"%s","method_config":{"mode":"static","node_top_k":%s,"tree_depth":%s,"max_verify_width":%s}}' \
  "$DRAFT" "$NODE_TOP_K" "$TREE_DEPTH" "$MAX_VERIFY_WIDTH")

docker run -d --name "$CONTAINER" \
  --gpus all --ipc=host --network host \
  -e HF_HUB_OFFLINE="$OFFLINE" \
  -e VLLM_USE_V2_MODEL_RUNNER=1 \
  -v "$HF_CACHE:/root/.cache/huggingface" \
  "$IMAGE" \
  "$MODEL" \
  --served-model-name "$SERVED_NAME" \
  --port "$PORT" \
  --max-model-len "$MAX_LEN" \
  --gpu-memory-utilization "$GPU_UTIL" \
  --max-num-seqs "$MAX_SEQS" \
  --speculative-config "$spec_config" \
  --attention-backend CUSTOM \
  --language-model-only \
  --trust-remote-code \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --enable-prefix-caching

echo "Started $CONTAINER. First start takes ~10-11 minutes."
echo "Follow: docker logs -f $CONTAINER"
echo "Health: curl -s http://127.0.0.1:$PORT/health"
