# EAGLE-4 on GB10 — building from source, step by step

> Publication note: internal paths and image names were generalized. Pins,
> commands, errors, and results are the real ones. The recipe assumes a flat
> build directory; in this repository the Dockerfile is in `docker/` and
> `build/build-eagle.sh` handles the paths.

Exact-reproduction record of the build performed on **30 October 2026** on an
NVIDIA DGX Spark (GB10, aarch64). It contains all commands, versions, pins,
errors encountered, and fixes.

Result: `vllm 0.32.0rc1.dev283+eagle.3` aarch64 wheel + `vllm-eagle:gb10`
Docker image with working EAGLE-4.

---

## 0. Summary

| Item | Value |
|---|---|
| Machine | DGX Spark GB10, aarch64, 20 cores, 121 GB unified memory |
| OS | Ubuntu 24.04.5 LTS |
| NVIDIA driver | 580.159.03 (CUDA 13.0) |
| Base image | `vllm/vllm-openai:latest` |
| Base digest | `sha256:c1c9f6fd5c109ba7f0546a59f5b2f15fb87f64c77782e90a27b648b42a8e67c3` |
| Base image date | 2026-10-03 |
| Fork built | `eagle-hq/vllm`, commit `3ba23801e80d2a0d0a9af21ce94484aa2adb8795` |
| CUDA architecture | `12.1a` (sm_121) |
| Build time | ~25–30 min (16 jobs) |
| Wheel produced | `vllm-0.32.0rc1.dev283+eagle.3-cp312-cp312-linux_aarch64.whl` |
| Wheel size | 494,300,662 bytes (472 MB) |
| Wheel SHA-256 | `fbd7ec77a34f608b4158d7a7196f75a1f78100da3645825e0a30657f72408237` |
| Final image | `vllm-eagle:gb10`, ID `8a7e21b70c05`, 44.1 GB |
| `eagle-harness` | 0.1.4 |
| EAGLE hooks | `eagle-harness-check` → **OK** |

After the build, the image reports `torch 2.14.0+cu130` (see §12): the wheel
was compiled against the base image's torch 2.13.0, but `pip install
eagle-harness[vllm]` upgraded torch to 2.14. It works; for exact parity, pin
`torch==2.13.0` (see §12).

---

## 1. Why building was necessary

EAGLE-4 does not distribute ARM builds:

| Official resource | Architecture |
|---|---|
| `eagle-hq.github.io/EAGLE-4/whl/cu130/vllm/` | `manylinux_2_28_x86_64` only |
| `ghcr.io/eagle-hq/eagle-4-vllm:0.1.3` | `linux/amd64` only |
| `flashinfer-python` (used by the official recipe) | no arm64 wheel |

Checks performed (real commands and outputs):

```bash
curl -s https://eagle-hq.github.io/EAGLE-4/whl/cu130/vllm/ | grep -o 'vllm-[^"#]*whl'
# vllm-0.32.0rc1.dev283+eagle.4-cp38-abi3-manylinux_2_28_x86_64.whl
# vllm-0.32.0rc1.dev283+eagle.5-cp38-abi3-manylinux_2_28_x86_64.whl

docker manifest inspect --verbose ghcr.io/eagle-hq/eagle-4-vllm:0.1.3 | grep architecture
# "architecture": "amd64"
```

Since `eagle-harness` is pure Python, the only blocker is the patched vLLM
engine. The `eagle-hq/vllm` fork is therefore built from source for aarch64.

---

## 2. Prerequisites

- Docker with GPU access (`--gpus all`)
- ~10 GB free for sources, ~500 MB for the wheel, ~45 GB for the image
- Access to GitHub and PyPI (the build container downloads Python dependencies)
- No NGC account needed: it starts from `vllm/vllm-openai:latest` (arm64)

Initial check:

```bash
docker run --rm --entrypoint bash vllm/vllm-openai:latest -lc '
  python3 -c "import torch;print(torch.__version__, torch.version.cuda)"; \
  which nvcc ninja g++'
# 2.13.0+cu130 13.0
# /usr/local/cuda/bin/nvcc  /usr/local/bin/ninja  /usr/bin/g++
```

The base image already has `nvcc`, `ninja`, and `g++`; it is **missing** `git`,
`cmake`, `curl`, `libdw-dev`, `libelf-dev`.

---

## 3. How the build finds its dependencies

The vLLM build uses CMake `FetchContent` to download three projects. GitHub
clones during the build proved **unreliable** (rate limit/auth). vLLM exposes
three environment variables to provide them from local sources:

| Dependency | Variable | Pin | Used for |
|---|---|---|---|
| flash-attention (vLLM fork) | `VLLM_FLASH_ATTN_SRC_DIR` | commit `b273a02621d3c94bc747df67204f591b67f38fae` | attention kernels |
| CUTLASS for vLLM | `VLLM_CUTLASS_SRC_DIR` | tag **v4.7.1** | GEMM/FP4 |
| DeepGEMM | `DEEPGEMM_SRC_DIR` | commit `a7a927731b109fdfec770df7c2a5be5d7e2216b5` | MoE FP8 |

Note: **two different CUTLASS versions**. flash-attn uses its own submodule at
commit `62750a2b75c802660e4894434dc55e839f322277`; vLLM wants tag v4.7.1. They
are not interchangeable.

---

## 4. Source preparation (on the host)

Working directory used: `$HOME/eagle4-build`.

### 4.1 DeepGEMM with submodules (once)

```bash
cd $HOME/eagle4-build
rm -rf deepgemm-src
git clone https://github.com/vllm-project/DeepGEMM.git deepgemm-src
git -C deepgemm-src checkout a7a927731b109fdfec770df7c2a5be5d7e2216b5
git -C deepgemm-src submodule update --init --recursive --depth 1
```

Actual commits:

```
DeepGEMM          a7a927731b109fdfec770df7c2a5be5d7e2216b5
third-party/deep_jit  3732a3b9a0a2e5126396908a362ba5abdf043b2f
third-party/cutlass   f3fde58372d33e9a5650ba7b80fc48b3b49d40c8
```

Resulting size: ~209 MB. Needed because the automatic submodule clone inside
the container failed (`Failed to update submodules`).

### 4.2 flash-attn and CUTLASS: tarballs inside the container

For these two, download the tarballs during the `docker run` (more reliable
than `git clone`), at the exact commits given in §3.

---

## 5. Compilation (full command)

This is the **identical** command that produced the wheel. Run it from
`$HOME/eagle4-build`.

```bash
docker run --rm --name eagle-build --gpus all \
  -v $HOME/eagle4-build:/out \
  --entrypoint bash vllm/vllm-openai:latest -lc '
    set -e

    # 1. system tools missing from the base image
    apt-get update -qq >/dev/null 2>&1
    apt-get install -y -qq git cmake curl libdw-dev libelf-dev >/dev/null 2>&1

    # 2. EAGLE fork source
    rm -rf /src/vllm /src/flash-attn /src/cutlass-vllm
    git clone --depth 1 --branch eagle/v0.1.0 https://github.com/eagle-hq/vllm /src/vllm
    git -C /src/vllm checkout 3ba23801e80d2a0d0a9af21ce94484aa2adb8795
    echo "vllm commit: $(git -C /src/vllm rev-parse HEAD)"

    # 3. flash-attention at the pinned commit
    curl -sL -o /tmp/fa.tgz \
      https://codeload.github.com/vllm-project/flash-attention/tar.gz/b273a02621d3c94bc747df67204f591b67f38fae
    mkdir -p /src/flash-attn
    tar xzf /tmp/fa.tgz -C /src/flash-attn --strip-components=1

    # 4. flash-attn's internal CUTLASS
    curl -sL -o /tmp/fa-cutlass.tgz \
      https://codeload.github.com/NVIDIA/cutlass/tar.gz/62750a2b75c802660e4894434dc55e839f322277
    mkdir -p /src/flash-attn/csrc/cutlass
    tar xzf /tmp/fa-cutlass.tgz -C /src/flash-attn/csrc/cutlass --strip-components=1

    # 5. CUTLASS v4.7.1 required by vLLM
    curl -sL -o /tmp/cutlass.tgz \
      https://codeload.github.com/NVIDIA/cutlass/tar.gz/refs/tags/v4.7.1
    mkdir -p /src/cutlass-vllm
    tar xzf /tmp/cutlass.tgz -C /src/cutlass-vllm --strip-components=1
    test -f /src/cutlass-vllm/include/cutlass/cutlass.h && echo "cutlass v4.7.1 ok"

    # 6. build variables
    cd /src/vllm
    export VLLM_FLASH_ATTN_SRC_DIR=/src/flash-attn
    export VLLM_CUTLASS_SRC_DIR=/src/cutlass-vllm
    export DEEPGEMM_SRC_DIR=/out/deepgemm-src
    export SETUPTOOLS_SCM_PRETEND_VERSION=0.32.0rc1.dev283+eagle.5
    export TORCH_CUDA_ARCH_LIST=12.1a
    export MAX_JOBS=16

    # 7. build-time Python dependencies (setuptools <81 for the fork pyproject)
    python3 -m pip install -q --upgrade pip
    python3 -m pip install -q \
      "setuptools>=77,<81" wheel packaging setuptools-rust setuptools-scm \
      ninja "cmake>=3.26.1"

    # 8. wheel build
    python3 -m pip wheel . --no-deps --no-build-isolation -w /out
    ls -lh /out
  '
```

Expected output (real excerpt):

```
vllm commit: 3ba23801e80d2a0d0a9af21ce94484aa2adb8795
cutlass v4.7.1 ok
...
Building wheel for vllm (pyproject.toml): finished with status 'done'
Created wheel for vllm: filename=vllm-0.32.0rc1.dev283+eagle.3-cp312-cp312-linux_aarch64.whl
  size=494300662 sha256=fbd7ec77a34f608b4158d7a7196f75a1f78100da3645825e0a30657f72408237
total 472M
-rw-r--r-- 1 root root 472M vllm-0.32.0rc1.dev283+eagle.3-cp312-cp312-linux_aarch64.whl
```

**Version note**: despite
`SETUPTOOLS_SCM_PRETEND_VERSION=...+eagle.5`, the fork produced `+eagle.3`
(its own local-version scheme). That is fine: `eagle-harness` requires
`vllm>=0.32.0rc1.dev283,!=0.32.0`, and `+eagle.3` satisfies the requirement.

---

## 6. Docker image with EAGLE-4

File `$HOME/eagle4-build/Dockerfile.eagle` (exact content):

```dockerfile
FROM vllm/vllm-openai:latest

USER root
COPY *.whl /tmp/wheels/
RUN python3 -m pip install --no-cache-dir /tmp/wheels/*.whl \
 && python3 -m pip install --no-cache-dir "eagle-harness[vllm]" \
 && rm -rf /tmp/wheels

# The build stops if the hooks are missing: an image without hooks is useless
# for EAGLE-4.
RUN eagle-harness-check && echo "EAGLE HOOKS OK"
```

Build:

```bash
cd $HOME/eagle4-build
docker build -f Dockerfile.eagle -t vllm-eagle:gb10 .
```

Expected output:

```
Successfully installed eagle-harness-0.1.4
...
eagle-harness: registered speculative method eagle_harness
EAGLE HOOKS OK
naming to docker.io/library/vllm-eagle:gb10 done
```

Check versions inside the image:

```bash
docker run --rm --entrypoint bash vllm-eagle:gb10 -lc \
  'python3 -c "import vllm,torch;print(vllm.__version__, torch.__version__)"; \
   eagle-harness-check && echo HOOKS_OK'
# 0.32.0rc1.dev283+eagle.3 2.14.0+cu130
# HOOKS_OK
```

---

## 7. Service profile

`$HOME/eagle4-build/profiles/qwen3.8-27b-eagle.yaml`:

```yaml
name: qwen3.8-27b-eagle
image: vllm-eagle:gb10
model: nvidia/Qwen3.8-27B-NVFP4
served_name: qwen3.8-27b-eagle
port: 8000
max_model_len: 65536
gpu_mem_util: 0.45
max_num_seqs: 4
startup_timeout_s: 1800
env:
  - VLLM_USE_V2_MODEL_RUNNER=1
speculative_config: '{"method":"eagle_harness","model":"EAGLE-Corp/Qwen3.8-27B-EAGLE4","method_config":{"mode":"static","node_top_k":4,"tree_depth":14,"max_verify_width":16}}'
speculative_default: "on"
extra_args:
  - --attention-backend
  - CUSTOM
  - --language-model-only
  - --trust-remote-code
  - --enable-auto-tool-choice
  - --tool-call-parser
  - qwen3_coder
  - --enable-prefix-caching
```

The YAML profile is included for launchers that read `env:` and pass
`-e KEY=VALUE` to the container. If your launcher does not support `env:`, use
the Docker command in the README or `./scripts/serve.sh`.

Start (from the repository root):

```bash
./scripts/serve.sh
# expected: server ready after ~650 s, model qwen3.8-27b-eagle
```

Key log lines (`./logs/server-qwen3.8-27b-eagle.log`):

```
Resolved architecture: LlamaForCausalLMEagle4
eagle-harness: registered speculative method eagle_harness and draft LlamaForCausalLMEagle4
```

---

## 8. Verification

```bash
./scripts/smoke.sh
# 6/6 PASS (health, models, chat, tool_call, streaming, long_context)

# optional: measure on your machine and report (no published claim)
python3 scripts/bench.py --preset agentic --requests 3 --label eagle4-agentic
python3 scripts/bench.py --preset echo    --requests 3 --label eagle4-echo
```

No benchmark is published: the initial measurements (one machine, one run) were
withdrawn. Run `scripts/bench.py` and open a run report; verified results will
be added to the README with hardware and command.

Agent test: passed, 1 tool call (`echo EAGLE4-OK` via the shell tool).

---

## 9. All errors encountered (and the fix)

This is the real chronology: each attempt stopped on a different point.

| # | Exact error | Cause | Fix |
|---|---|---|---|
| 1 | `ModuleNotFoundError: No module named 'setuptools_rust'` | build dependency missing | `pip install setuptools-rust setuptools-scm` |
| 2 | `Failed to update submodules in '/src/vllm/.deps/vllm-flash-attn-src'` | cutlass submodule clone during CMake | `VLLM_FLASH_ATTN_SRC_DIR` with a local source |
| 3 | `fatal: could not read Username for 'https://github.com'` | GitHub clone rejected/rate-limited in the container | use `codeload.github.com` tarballs at the pinned commits |
| 4 | `CMake Error ... cutlass ... FetchContent_MakeAvailable` | vLLM downloads CUTLASS v4.7.1 | `VLLM_CUTLASS_SRC_DIR` with the v4.7.1 tarball |
| 5 | `fatal error: elfutils/libdwfl.h: No such file or directory` (DeepGEMM) | elfutils headers missing | `apt-get install libdw-dev libelf-dev` |
| 6 | `Failed to update submodules in '/src/vllm/.deps/deepgemm-src'` | unstable DeepGEMM submodule clone | pre-clone on the host + `DEEPGEMM_SRC_DIR` |
| 7 | image: `pip check` exit 1 (`opentelemetry-sdk`, `nvidia-cusparselt-cu13 not supported`) | pre-existing dependencies of the base image | removed `pip check` from the Dockerfile; hooks verified with `eagle-harness-check` |

None of these errors involve the EAGLE code: they are all build dependencies.

---

## 10. Observed resource usage

| Phase | Time | Notes |
|---|---|---|
| source download (once) | 2–3 min | DeepGEMM 209 MB + tarballs |
| compilation | ~25–30 min | 16 CPU jobs, ~12.5 GB RAM, 395 objects |
| image export | ~2.5 min | 472 MB layer + pip |
| first model start | 646 s | loads target 22 GB + draft 5.8 GB |
| disk | ~45 GB image + 0.5 GB wheel + 0.2 GB sources | |

---

## 11. Reproducing from zero (checklist)

```bash
# 1. DeepGEMM sources
cd $HOME/eagle4-build
git clone https://github.com/vllm-project/DeepGEMM.git deepgemm-src
git -C deepgemm-src checkout a7a927731b109fdfec770df7c2a5be5d7e2216b5
git -C deepgemm-src submodule update --init --recursive --depth 1

# 2. build (command from §5)
# 3. image (Dockerfile from §6)
# 4. profile (YAML from §7)
# 5. verification (commands from §8)
```

Alternatively, the ready-made script:

```bash
$HOME/eagle4-build/build-eagle.sh
```

The script contains the same pins and the same command; it is the maintained
version of this procedure.

---

## 12. Notes and limits

1. **torch upgraded**: the wheel is compiled against torch 2.13.0 (base
   image), but the final image uses torch **2.14.0+cu130** because `pip
   install eagle-harness[vllm]` resolves its dependencies. It works and has
   been exercised. For exact parity, add `torch==2.13.0` to the Dockerfile
   before the wheel and use `--no-deps` for `eagle-harness`.
2. **`flashinfer_cutedsl` not used**: the official recipe passes it as the
   `--linear-backend`; on arm64 `flashinfer-python` does not exist. The default
   linear backend is used instead.
3. **KV cache not quantized**: required by tree verification; do not use
   `--kv-cache-dtype fp8` with EAGLE-4.
4. **Local image**: `vllm-eagle:gb10` is not on a registry. After a reset it
   must be rebuilt (wheel + Dockerfile are in `$HOME/eagle4-build`).
5. **Experimental fork**: the `eagle/v0.1.0` branch can change; the commit is
   pinned in the script. Do not update without redoing smoke + verification.
6. **One model at a time**: EAGLE-4 occupies ~28 GB between target and draft;
   added to the KV cache, it does not coexist with a second server.

---

## 13. Files produced

```
$HOME/eagle4-build/
├── build-eagle.sh                                  full recipe
├── Dockerfile.eagle                                image with wheel + harness
├── deepgemm-src/                                   DeepGEMM source + submodules
├── vllm-0.32.0rc1.dev283+eagle.3-cp312-cp312-linux_aarch64.whl
└── (Docker image vllm-eagle:gb10)

$HOME/eagle4-build/profiles/qwen3.8-27b-eagle.yaml  service profile
./logs/build-eagle.log                  full build log
```
