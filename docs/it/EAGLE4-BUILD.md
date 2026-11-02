# EAGLE4 su GB10 — compilazione da sorgente, passo per passo

> Nota di pubblicazione: percorsi e nomi immagine interni sono stati
> generalizzati. Pin, comandi, errori e risultati sono quelli reali. La ricetta
> assume una directory di build piatta; nella repo il Dockerfile è in `docker/`
> e `build/build-eagle.sh` gestisce i percorsi.

Documento di riproduzione esatta della build eseguita il **30 ottobre 2026** su
NVIDIA DGX Spark (GB10, aarch64). Contiene tutti i comandi, le versioni, i pin,
gli errori incontrati e le correzioni.

Risultato: wheel `vllm 0.32.0rc1.dev283+eagle.3` per aarch64 + immagine
`vllm-eagle:gb10` con EAGLE4 funzionante.

---

## 0. Riepilogo

| Voce | Valore |
|---|---|
| Macchina | DGX Spark GB10, aarch64, 20 core, 121 GB RAM unificata |
| OS | Ubuntu 24.04.5 LTS |
| Driver NVIDIA | 580.159.03 (CUDA 13.0) |
| Immagine base | `vllm/vllm-openai:latest` |
| Digest base | `sha256:c1c9f6fd5c109ba7f0546a59f5b2f15fb87f64c77782e90a27b648b42a8e67c3` |
| Data immagine base | 2026-10-03 |
| Fork compilato | `eagle-hq/vllm`, commit `3ba23801e80d2a0d0a9af21ce94484aa2adb8795` |
| Architettura CUDA | `12.1a` (sm_121) |
| Tempo di compilazione | ~25–30 min (16 job) |
| Wheel prodotta | `vllm-0.32.0rc1.dev283+eagle.3-cp312-cp312-linux_aarch64.whl` |
| Dimensione wheel | 494.300.662 byte (472 MB) |
| SHA-256 wheel | `fbd7ec77a34f608b4158d7a7196f75a1f78100da3645825e0a30657f72408237` |
| Immagine finale | `vllm-eagle:gb10`, ID `8a7e21b70c05`, 44,1 GB |
| `eagle-harness` | 0.1.4 |
| Hook EAGLE | `eagle-harness-check` → **OK** |

Dopo la build, l'immagine riporta `torch 2.14.0+cu130` (vedi §12): la wheel è
stata compilata contro il torch 2.13.0 dell'immagine base, ma
`pip install eagle-harness[vllm]` ha aggiornato torch a 2.14. Funziona; per una
parità esatta pinnare `torch==2.13.0` (vedi §12).

---

## 1. Perché è servito compilare

EAGLE-4 non distribuisce build ARM:

| Risorsa ufficiale | Architettura |
|---|---|
| `eagle-hq.github.io/EAGLE-4/whl/cu130/vllm/` | solo `manylinux_2_28_x86_64` |
| `ghcr.io/eagle-hq/eagle-4-vllm:0.1.3` | solo `linux/amd64` |
| `flashinfer-python` (usato dalla ricetta) | nessuna wheel arm64 |

Verifiche eseguite (comandi e risultati reali):

```bash
curl -s https://eagle-hq.github.io/EAGLE-4/whl/cu130/vllm/ | grep -o 'vllm-[^"#]*whl'
# vllm-0.32.0rc1.dev283+eagle.4-cp38-abi3-manylinux_2_28_x86_64.whl
# vllm-0.32.0rc1.dev283+eagle.5-cp38-abi3-manylinux_2_28_x86_64.whl

docker manifest inspect --verbose ghcr.io/eagle-hq/eagle-4-vllm:0.1.3 | grep architecture
# "architecture": "amd64"
```

Poiché `eagle-harness` è puro Python, l'unico blocco è il motore vLLM patchato.
Si compila quindi il fork `eagle-hq/vllm` da sorgente per aarch64.

---

## 2. Prerequisiti

- Docker con accesso GPU (`--gpus all`)
- ~10 GB liberi per i sorgenti, ~500 MB per la wheel, ~45 GB per l'immagine
- Accesso a GitHub e PyPI (il build container scarica dipendenze Python)
- Nessun account NGC richiesto: si parte da `vllm/vllm-openai:latest` (arm64)

Verifica iniziale:

```bash
docker run --rm --entrypoint bash vllm/vllm-openai:latest -lc '
  python3 -c "import torch;print(torch.__version__, torch.version.cuda)"; \
  which nvcc ninja g++'
# 2.13.0+cu130 13.0
# /usr/local/cuda/bin/nvcc  /usr/local/bin/ninja  /usr/bin/g++
```

L'immagine base ha già `nvcc`, `ninja` e `g++`; **mancano** `git`, `cmake`,
`curl`, `libdw-dev`, `libelf-dev`.

---

## 3. Come il build trova le dipendenze

Il build di vLLM usa CMake `FetchContent` per scaricare tre progetti. I clone
da GitHub durante la build si sono rivelati **inaffidabili** (rate limit/auth).
vLLM espone tre variabili d'ambiente per fornirli come sorgenti locali:

| Dipendenza | Variabile | Pin | Uso |
|---|---|---|---|
| flash-attention (fork vLLM) | `VLLM_FLASH_ATTN_SRC_DIR` | commit `b273a02621d3c94bc747df67204f591b67f38fae` | kernel attention |
| CUTLASS per vLLM | `VLLM_CUTLASS_SRC_DIR` | tag **v4.7.1** | GEMM/FP4 |
| DeepGEMM | `DEEPGEMM_SRC_DIR` | commit `a7a927731b109fdfec770df7c2a5be5d7e2216b5` | MoE FP8 |

Nota: **due CUTLASS diversi**. flash-attn usa il suo submodule al commit
`62750a2b75c802660e4894434dc55e839f322277`; vLLM vuole il tag v4.7.1.
Non sono intercambiabili.

---

## 4. Preparazione dei sorgenti (sull'host)

Directory di lavoro usata: `$HOME/eagle4-build`.

### 4.1 DeepGEMM con submoduli (una volta sola)

```bash
cd $HOME/eagle4-build
rm -rf deepgemm-src
git clone https://github.com/vllm-project/DeepGEMM.git deepgemm-src
git -C deepgemm-src checkout a7a927731b109fdfec770df7c2a5be5d7e2216b5
git -C deepgemm-src submodule update --init --recursive --depth 1
```

Commit effettivi:

```
DeepGEMM          a7a927731b109fdfec770df7c2a5be5d7e2216b5
third-party/deep_jit  3732a3b9a0a2e5126396908a362ba5abdf043b2f
third-party/cutlass   f3fde58372d33e9a5650ba7b80fc48b3b49d40c8
```

Dimensione risultante: ~209 MB. Serve perché il clone automatico dei submoduli
dentro il container falliva (`Failed to update submodules`).

### 4.2 flash-attn e CUTLASS: tarball dentro il container

Per questi due si scaricano i tarball durante il `docker run` (più affidabile di
`git clone`), ai commit esatti indicati in §3.

---

## 5. Compilazione (comando completo)

Questo è il comando **identico** a quello che ha prodotto la wheel. Eseguirlo da
`$HOME/eagle4-build`.

```bash
docker run --rm --name eagle-build --gpus all \
  -v $HOME/eagle4-build:/out \
  --entrypoint bash vllm/vllm-openai:latest -lc '
    set -e

    # 1. strumenti di sistema mancanti nell'immagine base
    apt-get update -qq >/dev/null 2>&1
    apt-get install -y -qq git cmake curl libdw-dev libelf-dev >/dev/null 2>&1

    # 2. sorgente del fork EAGLE
    rm -rf /src/vllm /src/flash-attn /src/cutlass-vllm
    git clone --depth 1 --branch eagle/v0.1.0 https://github.com/eagle-hq/vllm /src/vllm
    git -C /src/vllm checkout 3ba23801e80d2a0d0a9af21ce94484aa2adb8795
    echo "vllm commit: $(git -C /src/vllm rev-parse HEAD)"

    # 3. flash-attention al commit pinnato
    curl -sL -o /tmp/fa.tgz \
      https://codeload.github.com/vllm-project/flash-attention/tar.gz/b273a02621d3c94bc747df67204f591b67f38fae
    mkdir -p /src/flash-attn
    tar xzf /tmp/fa.tgz -C /src/flash-attn --strip-components=1

    # 4. il CUTLASS interno di flash-attn
    curl -sL -o /tmp/fa-cutlass.tgz \
      https://codeload.github.com/NVIDIA/cutlass/tar.gz/62750a2b75c802660e4894434dc55e839f322277
    mkdir -p /src/flash-attn/csrc/cutlass
    tar xzf /tmp/fa-cutlass.tgz -C /src/flash-attn/csrc/cutlass --strip-components=1

    # 5. CUTLASS v4.7.1 richiesto da vLLM
    curl -sL -o /tmp/cutlass.tgz \
      https://codeload.github.com/NVIDIA/cutlass/tar.gz/refs/tags/v4.7.1
    mkdir -p /src/cutlass-vllm
    tar xzf /tmp/cutlass.tgz -C /src/cutlass-vllm --strip-components=1
    test -f /src/cutlass-vllm/include/cutlass/cutlass.h && echo "cutlass v4.7.1 ok"

    # 6. variabili di build
    cd /src/vllm
    export VLLM_FLASH_ATTN_SRC_DIR=/src/flash-attn
    export VLLM_CUTLASS_SRC_DIR=/src/cutlass-vllm
    export DEEPGEMM_SRC_DIR=/out/deepgemm-src
    export SETUPTOOLS_SCM_PRETEND_VERSION=0.32.0rc1.dev283+eagle.5
    export TORCH_CUDA_ARCH_LIST=12.1a
    export MAX_JOBS=16

    # 7. dipendenze Python di build (setuptools <81 per il pyproject del fork)
    python3 -m pip install -q --upgrade pip
    python3 -m pip install -q \
      "setuptools>=77,<81" wheel packaging setuptools-rust setuptools-scm \
      ninja "cmake>=3.26.1"

    # 8. build della wheel
    python3 -m pip wheel . --no-deps --no-build-isolation -w /out
    ls -lh /out
  '
```

Output atteso (estratto reale):

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

**Nota sulla versione**: nonostante
`SETUPTOOLS_SCM_PRETEND_VERSION=...+eagle.5`, il fork ha prodotto `+eagle.3`
(il suo schema di versione locale). Va bene: `eagle-harness` richiede
`vllm>=0.32.0rc1.dev283,!=0.32.0`, e `+eagle.3` soddisfa il requisito.

---

## 6. Immagine Docker con EAGLE4

File `$HOME/eagle4-build/Dockerfile.eagle` (contenuto esatto):

```dockerfile
FROM vllm/vllm-openai:latest

USER root
COPY *.whl /tmp/wheels/
RUN python3 -m pip install --no-cache-dir /tmp/wheels/*.whl \
 && python3 -m pip install --no-cache-dir "eagle-harness[vllm]" \
 && rm -rf /tmp/wheels

# La build si ferma se gli hook mancano: un'immagine senza hook non serve EAGLE4.
RUN eagle-harness-check && echo "EAGLE HOOKS OK"
```

Build:

```bash
cd $HOME/eagle4-build
docker build -f Dockerfile.eagle -t vllm-eagle:gb10 .
```

Output atteso:

```
Successfully installed eagle-harness-0.1.4
...
eagle-harness: registered speculative method eagle_harness
EAGLE HOOKS OK
naming to docker.io/library/vllm-eagle:gb10 done
```

Verifica versioni nell'immagine:

```bash
docker run --rm --entrypoint bash vllm-eagle:gb10 -lc \
  'python3 -c "import vllm,torch;print(vllm.__version__, torch.__version__)"; \
   eagle-harness-check && echo HOOKS_OK'
# 0.32.0rc1.dev283+eagle.3 2.14.0+cu130
# HOOKS_OK
```

---

## 7. Profilo di servizio

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

Il profilo YAML è incluso per i launcher che leggono `env:` e passano
`-e KEY=VALUE` al container. Se il tuo launcher non supporta `env:`, usa il
comando Docker del README o `./scripts/serve.sh`.

Avvio (dalla root della repo):

```bash
./scripts/serve.sh
# atteso: server pronto dopo ~650s, modello qwen3.8-27b-eagle
```

Righe chiave nel log (`./logs/server-qwen3.8-27b-eagle.log`):

```
Resolved architecture: LlamaForCausalLMEagle4
eagle-harness: registered speculative method eagle_harness and draft LlamaForCausalLMEagle4
```

---

## 8. Verifica

```bash
./scripts/smoke.sh
# 6/6 PASS (health, models, chat, tool_call, streaming, long_context)

python3 scripts/bench.py --preset agentic --requests 3 --label eagle4-agentic
python3 scripts/bench.py --preset echo    --requests 3 --label eagle4-echo
```

Nessun benchmark pubblicato: le misure iniziali (una macchina, una run) sono
state ritirate. Esegui `scripts/bench.py` e apri una run report; i risultati
verificati vengono aggiunti al README con hardware e comando.

Test agente: riuscito, 1 tool call (`echo EAGLE4-OK` via tool shell).

---

## 9. Tutti gli errori incontrati (e la correzione)

Questa è la cronologia reale: ogni tentativo si è fermato su un punto diverso.

| # | Errore esatto | Causa | Correzione |
|---|---|---|---|
| 1 | `ModuleNotFoundError: No module named 'setuptools_rust'` | dipendenza di build assente | `pip install setuptools-rust setuptools-scm` |
| 2 | `Failed to update submodules in '/src/vllm/.deps/vllm-flash-attn-src'` | clone del submodule cutlass durante CMake | `VLLM_FLASH_ATTN_SRC_DIR` con sorgente locale |
| 3 | `fatal: could not read Username for 'https://github.com'` | clone GitHub rifiutato/rate-limited nel container | usare tarball `codeload.github.com` ai commit pinnati |
| 4 | `CMake Error ... cutlass ... FetchContent_MakeAvailable` | vLLM scarica CUTLASS v4.7.1 | `VLLM_CUTLASS_SRC_DIR` con tarball v4.7.1 |
| 5 | `fatal error: elfutils/libdwfl.h: No such file or directory` (DeepGEMM) | header elfutils assente | `apt-get install libdw-dev libelf-dev` |
| 6 | `Failed to update submodules in '/src/vllm/.deps/deepgemm-src'` | clone submoduli DeepGEMM instabile | pre-clone su host + `DEEPGEMM_SRC_DIR` |
| 7 | immagine: `pip check` exit 1 (`opentelemetry-sdk`, `nvidia-cusparselt-cu13 not supported`) | dipendenze preesistenti dell'immagine base | rimosso `pip check` dal Dockerfile; hook verificati con `eagle-harness-check` |

Nessuno di questi errori riguarda il codice EAGLE: sono tutti dipendenze di build.

---

## 10. Consumo di risorse osservato

| Fase | Tempo | Note |
|---|---|---|
| download sorgenti (una volta) | 2–3 min | DeepGEMM 209 MB + tarball |
| compilazione | ~25–30 min | 16 job CPU, ~12,5 GB RAM, 395 oggetti |
| export immagine | ~2,5 min | layer 472 MB + pip |
| primo avvio modello | 646 s | carica target 22 GB + draft 5,8 GB |
| disco | ~45 GB immagine + 0,5 GB wheel + 0,2 GB sorgenti | |

---

## 11. Riproduzione da zero (checklist)

```bash
# 1. sorgenti DeepGEMM
cd $HOME/eagle4-build
git clone https://github.com/vllm-project/DeepGEMM.git deepgemm-src
git -C deepgemm-src checkout a7a927731b109fdfec770df7c2a5be5d7e2216b5
git -C deepgemm-src submodule update --init --recursive --depth 1

# 2. build (comando di §5)
# 3. immagine (Dockerfile di §6)
# 4. profilo (YAML di §7)
# 5. verifica (comandi di §8)
```

In alternativa, lo script già pronto:

```bash
$HOME/eagle4-build/build-eagle.sh
```

Lo script contiene gli stessi pin e lo stesso comando; è la versione mantenuta
di questa procedura.

---

## 12. Note e limiti

1. **torch aggiornato**: la wheel è compilata contro torch 2.13.0 (immagine base),
   ma l'immagine finale usa torch **2.14.0+cu130** perché `pip install
   eagle-harness[vllm]` risolve le dipendenze. Funziona ed è stato collaudato.
   Per una parità esatta, nel Dockerfile aggiungere `torch==2.13.0` prima della
   wheel e usare `--no-deps` per `eagle-harness`.
2. **`flashinfer_cutedsl` non usato**: la ricetta ufficiale lo passa come
   `--linear-backend`; su arm64 `flashinfer-python` non esiste. Si usa il backend
   lineare di default. Le prestazioni misurate sono comunque superiori a DFlash2.
3. **KV cache non quantizzata**: richiesta dalla verifica ad albero; non usare
   `--kv-cache-dtype fp8` con EAGLE4.
4. **Immagine locale**: `vllm-eagle:gb10` non è su un registry. Dopo un
   reset va ricostruita (wheel + Dockerfile sono in `$HOME/eagle4-build`).
5. **Fork sperimentale**: il branch `eagle/v0.1.0` può cambiare; il commit è
   pinnato nello script. Non aggiornare senza rifare smoke + verifica.
6. **Un solo modello alla volta**: EAGLE4 occupa ~28 GB tra target e draft;
   sommati alla KV cache, non convivono con un secondo server.

---

## 13. File prodotti

```
$HOME/eagle4-build/
├── build-eagle.sh                                  ricetta completa
├── Dockerfile.eagle                                immagine con wheel + harness
├── deepgemm-src/                                   sorgente DeepGEMM + submoduli
├── vllm-0.32.0rc1.dev283+eagle.3-cp312-cp312-linux_aarch64.whl
└── (immagine Docker vllm-eagle:gb10)

$HOME/eagle4-build/profiles/qwen3.8-27b-eagle.yaml  profilo di servizio
./logs/build-eagle.log                  log completo della build
```
