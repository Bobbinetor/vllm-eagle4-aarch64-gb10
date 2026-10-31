# Troubleshooting

Every build error below was observed while producing this wheel. Runtime errors
are the ones most likely to appear on a fresh DGX Spark.

## Build-time errors

| # | Exact error | Cause | Fix |
|---|---|---|---|
| 1 | `ModuleNotFoundError: No module named 'setuptools_rust'` | Build dependency missing | `pip install setuptools-rust setuptools-scm` |
| 2 | `Failed to update submodules in '/src/vllm/.deps/vllm-flash-attn-src'` | CMake tried to clone the flash-attn submodule | Point `VLLM_FLASH_ATTN_SRC_DIR` at a local source tree |
| 3 | `fatal: could not read Username for 'https://github.com'` | GitHub clone refused or rate-limited inside the container | Download tarballs from `codeload.github.com` at the pinned commits |
| 4 | `CMake Error ... cutlass ... FetchContent_MakeAvailable` | vLLM tried to fetch CUTLASS v4.7.1 | Set `VLLM_CUTLASS_SRC_DIR` to a local v4.7.1 tarball |
| 5 | `fatal error: elfutils/libdwfl.h: No such file or directory` (DeepGEMM) | Missing elfutils headers | `apt-get install libdw-dev libelf-dev` |
| 6 | `Failed to update submodules in '/src/vllm/.deps/deepgemm-src'` | Unstable DeepGEMM submodule clone | Pre-clone on the host and set `DEEPGEMM_SRC_DIR` |
| 7 | `pip check` exits 1 (`opentelemetry-sdk`, `nvidia-cusparselt-cu13 not supported`) | Pre-existing base-image dependency mismatch | Not fatal; the Dockerfile does not gate on `pip check`. Gate on `eagle-harness-check` instead |

Two different CUTLASS checkouts are required and they are **not**
interchangeable:

- flash-attention wants its submodule at
  `62750a2b75c802660e4894434dc55e839f322277`;
- vLLM wants tag `v4.7.1`.

## Runtime errors

### `eagle-harness-check` exits 1 (the image build stops)

The installed vLLM is not the patched build, or pip replaced it.

```bash
python3 -c "import vllm; print(vllm.__version__, vllm.__file__)"
python3 scripts/audit_hooks.py /path/to/vllm-*.whl
eagle-harness-check
```

Fix:

```bash
pip uninstall -y vllm
pip install --no-deps /path/to/vllm-0.32.0rc1.dev283+eagle.3-cp312-cp312-linux_aarch64.whl
eagle-harness-check
```

Do not run `pip install -U vllm` or `pip install vllm==0.32.0` inside the image:
the stock wheel does not carry the hooks.

### `Resolved architecture` is not `LlamaForCausalLMEagle4`

The draft model was not found or the wrong model path was passed.

```bash
ls ~/.cache/huggingface/hub | grep -i eagle
curl -s http://127.0.0.1:8000/v1/models | python3 -m json.tool
```

Fix: download `EAGLE-Corp/Qwen3.8-27B-EAGLE4`, check the exact `--speculative-config`
model string, and make sure `HF_HUB_OFFLINE=1` is only set after the download.

### OOM at startup

`gpu-memory-utilization` is too high for the target + draft + KV cache.

```bash
# try 0.40, then 0.42
--gpu-memory-utilization 0.40
```

EAGLE-4 uses ~28 GB for target + draft before KV cache. Do not run a second
server on the same GB10.

### High TTFT

Tree verification costs work before the first accepted token. Reduce the tree:

```json
{"mode":"static","node_top_k":2,"tree_depth":8,"max_verify_width":8}
```

Or use DFlash2 for short, latency-sensitive prompts. Measure both with
`scripts/bench.py --metrics-url .../metrics`.

### `flashinfer_cutedsl` not available

There is no `flashinfer-python` arm64 wheel. This is expected. This build uses
the default linear backend. Do not add `--linear-backend flashinfer_cutedsl`.

### `libcudart.so.12: cannot open shared object file`

A CUDA 12 wheel slipped into the environment. The DGX Spark needs CUDA 13
userspace.

```bash
pip list | grep -E "vllm|torch|nvidia"
```

Use the provided image, or rebuild the venv from the CUDA 13 base. Do not
`pip install vllm` from PyPI into this image.

### `pip check` complains about `opentelemetry-sdk` / `nvidia-cusparselt-cu13`

Pre-existing in the base image. It does not affect EAGLE-4. The real gate is:

```bash
eagle-harness-check && echo HOOKS_OK
```

### Tool calls come back as plain text

The server was started without the tool-call parser, or the model name does not
match.

```bash
--enable-auto-tool-choice --tool-call-parser qwen3_coder
```

Check `GET /v1/models` and use the same `model` value in the request.

### `--attention-backend CUSTOM` rejected

The `eagle_harness` plugin did not register the custom backend, usually because
the hooks are missing or the plugin was not loaded. Check:

```bash
eagle-harness-check
docker logs vllm-eagle | grep -i "eagle-harness"
```

You should see:

```text
eagle-harness: registered speculative method eagle_harness and draft LlamaForCausalLMEagle4
```

### Container cannot see the GPU

```bash
docker run --rm --gpus all --entrypoint bash vllm-eagle:gb10 -lc \
  'python3 -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"'
```

Expected: `True NVIDIA GB10`. If not, check the NVIDIA Container Toolkit and the
driver (`nvidia-smi` on the host).

### First start takes forever / times out

Expected: ~10–11 minutes on a cold cache (CUDA graph capture + 27 GB of weights).
Use `startup_timeout_s: 1800` in your launcher, or just wait and follow the logs.

### Context length errors

The profile sets `--max-model-len 65536`. If you lower it, keep it above your
prompt + `max_tokens`. EAGLE-4's tree verification reserves extra KV slots; a
context that barely fits without speculation may OOM with it.

## Diagnostic bundle

If you open an issue, include:

```bash
uname -a
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
docker version --format '{{.Server.Version}}'
python3 -c "import vllm, torch; print(vllm.__version__, torch.__version__)"
eagle-harness-check
docker logs --tail 200 vllm-eagle
```

Plus the output of `scripts/audit_hooks.py` and `scripts/bench.py`.
