#!/usr/bin/env bash
# build-eagle.sh - ricostruisce la wheel vLLM patchata EAGLE4 per aarch64/GB10.
#
# Impiega ~40 minuti su 20 core. Produce, nella root della repo:
#   vllm-0.32.0rc1.dev283+eagle.3-cp312-cp312-linux_aarch64.whl
# e poi l'immagine:
#   vllm-eagle:gb10
#
# Note:
# - il fork eagle-hq/vllm e' pinnato al commit usato il 30/10/2026
# - le dipendenze di build (flash-attn, CUTLASS v4.7.1, DeepGEMM) sono fornite
#   come sorgenti locali per evitare i clone di rete instabili
# - TORCH_CUDA_ARCH_LIST=12.1a e' l'architettura della GB10
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
DEEPGEMM_DIR="$REPO_ROOT/build/deepgemm-src"

VLLM_COMMIT=3ba23801e80d2a0d0a9af21ce94484aa2adb8795
FA_COMMIT=b273a02621d3c94bc747df67204f591b67f38fae
FA_CUTLASS_COMMIT=62750a2b75c802660e4894434dc55e839f322277
DEEPGEMM_COMMIT=a7a927731b109fdfec770df7c2a5be5d7e2216b5

# DeepGEMM con submoduli, pre-clonato (evita FetchContent instabile)
if [[ ! -d "$DEEPGEMM_DIR/third-party/deep_jit" ]]; then
  rm -rf "$DEEPGEMM_DIR"
  git clone https://github.com/vllm-project/DeepGEMM.git "$DEEPGEMM_DIR"
  git -C "$DEEPGEMM_DIR" checkout "$DEEPGEMM_COMMIT"
  git -C "$DEEPGEMM_DIR" submodule update --init --recursive
fi

docker run --rm --name eagle-build --gpus all \
  -v "$REPO_ROOT:/out" \
  --entrypoint bash vllm/vllm-openai:latest -lc "
    set -e
    apt-get update -qq >/dev/null 2>&1
    apt-get install -y -qq git cmake curl libdw-dev libelf-dev >/dev/null 2>&1
    rm -rf /src/vllm /src/flash-attn /src/cutlass-vllm
    git clone https://github.com/eagle-hq/vllm /src/vllm
    git -C /src/vllm checkout $VLLM_COMMIT
    echo \"vllm commit: \$(git -C /src/vllm rev-parse HEAD)\"
    curl -sL -o /tmp/fa.tgz https://codeload.github.com/vllm-project/flash-attention/tar.gz/$FA_COMMIT
    mkdir -p /src/flash-attn && tar xzf /tmp/fa.tgz -C /src/flash-attn --strip-components=1
    curl -sL -o /tmp/fa-cutlass.tgz https://codeload.github.com/NVIDIA/cutlass/tar.gz/$FA_CUTLASS_COMMIT
    mkdir -p /src/flash-attn/csrc/cutlass && tar xzf /tmp/fa-cutlass.tgz -C /src/flash-attn/csrc/cutlass --strip-components=1
    curl -sL -o /tmp/cutlass.tgz https://codeload.github.com/NVIDIA/cutlass/tar.gz/refs/tags/v4.7.1
    mkdir -p /src/cutlass-vllm && tar xzf /tmp/cutlass.tgz -C /src/cutlass-vllm --strip-components=1
    cd /src/vllm
    export VLLM_FLASH_ATTN_SRC_DIR=/src/flash-attn
    export VLLM_CUTLASS_SRC_DIR=/src/cutlass-vllm
    export DEEPGEMM_SRC_DIR=/out/build/deepgemm-src
    export SETUPTOOLS_SCM_PRETEND_VERSION=0.32.0rc1.dev283+eagle.5
    export TORCH_CUDA_ARCH_LIST=12.1a
    export MAX_JOBS=16
    python3 -m pip install -q --upgrade pip
    python3 -m pip install -q 'setuptools>=77,<81' wheel packaging setuptools-rust setuptools-scm ninja 'cmake>=3.26.1'
    python3 -m pip wheel . --no-deps --no-build-isolation -w /out
    ls -lh /out
  "

docker build -f docker/Dockerfile.eagle -t vllm-eagle:gb10 .
echo "Immagine pronta: vllm-eagle:gb10"
