# Come usare la wheel EAGLE4 su un'altra macchina

> Nota di pubblicazione: percorsi e nomi immagine interni sono stati
> generalizzati. I comandi e i risultati sono quelli reali.
>
> Nota GitHub: la wheel è un asset della release, non è dentro il repository.
> `SHA256SUMS` copre anche i file della ricetta, quindi usa
> `sha256sum -c --ignore-missing SHA256SUMS` se hai scaricato solo la wheel.

Questo pacchetto contiene tutto il necessario per far girare **EAGLE4 + Qwen3.8-27B
NVFP4** su una seconda macchina **NVIDIA DGX Spark / GB10 (aarch64)** senza
ricompilare vLLM.

## Contenuto dell'archivio

```
EAGLE4-BUILD.md                                  come è stata compilata (per riprodurla)
USO-WHEEL-EAGLE4.md                              questo documento
build-eagle.sh                                   ricetta di build da sorgente (opzionale)
Dockerfile.eagle                                  immagine con wheel + eagle-harness
vllm-0.32.0rc1.dev283+eagle.3-cp312-cp312-linux_aarch64.whl   motore patchato (472 MB)
qwen3.8-27b-eagle.yaml                           profilo di servizio
SHA256SUMS                                       checksum di tutti i file
```

## Requisiti

- NVIDIA DGX Spark / GB10, **aarch64**, driver CUDA 13.x
- Docker funzionante con GPU (`--gpus all`)
- ~45 GB liberi per l'immagine, ~27 GB per i modelli
- Accesso a HuggingFace per scaricare modelli e draft

Verifica architettura:

```bash
uname -m          # deve essere aarch64
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
docker run --rm --gpus all --entrypoint bash vllm/vllm-openai:latest -lc \
  'python3 -c "import torch;print(torch.cuda.is_available())"'   # True
```

## 1. Verifica i file

```bash
sha256sum -c SHA256SUMS
```

Deve risultare `OK` per tutti i file. Se la wheel non corrisponde, non usarla.

## 2. Costruisci l'immagine (2–3 minuti)

```bash
docker build -f Dockerfile.eagle -t vllm-eagle:gb10 .
```

Il Dockerfile installa la wheel e `eagle-harness[vllm]`, poi esegue
`eagle-harness-check`. In output deve comparire:

```
EAGLE HOOKS OK
```

Verifica manuale:

```bash
docker run --rm --entrypoint bash vllm-eagle:gb10 -lc \
  'python3 -c "import vllm,torch;print(vllm.__version__, torch.__version__)"; \
   eagle-harness-check && echo HOOKS_OK'
# atteso: 0.32.0rc1.dev283+eagle.3 2.14.0+cu130
#         HOOKS_OK
```

## 3. Scarica modelli e draft (una volta sola)

```bash
pip install -U huggingface_hub        # se non presente
hf download nvidia/Qwen3.8-27B-NVFP4          # ~21 GB
hf download EAGLE-Corp/Qwen3.8-27B-EAGLE4     # ~5,8 GB
```

Finiscono in `~/.cache/huggingface/hub`.

## 4. Avvia il server

### Opzione A — con lo script incluso

Dalla root della repo:

```bash
./scripts/serve.sh
```

### Opzione B — comando Docker diretto (nessuna dipendenza)

```bash
docker run -d --name vllm-eagle \
  --gpus all --ipc=host --network host \
  -e HF_HUB_OFFLINE=1 \
  -e VLLM_USE_V2_MODEL_RUNNER=1 \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  vllm-eagle:gb10 \
  nvidia/Qwen3.8-27B-NVFP4 \
  --served-model-name qwen3.8-27b-eagle \
  --port 8000 \
  --max-model-len 65536 \
  --gpu-memory-utilization 0.45 \
  --max-num-seqs 4 \
  --speculative-config '{"method":"eagle_harness","model":"EAGLE-Corp/Qwen3.8-27B-EAGLE4","method_config":{"mode":"static","node_top_k":4,"tree_depth":14,"max_verify_width":16}}' \
  --attention-backend CUSTOM \
  --language-model-only \
  --trust-remote-code \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --enable-prefix-caching
```

Attesa: **~10–11 minuti** al primo avvio (compile + caricamento).
Segui con:

```bash
docker logs -f vllm-eagle
```

Righe che confermano EAGLE4 attivo:

```
Resolved architecture: LlamaForCausalLMEagle4
eagle-harness: registered speculative method eagle_harness and draft LlamaForCausalLMEagle4
```

## 5. Verifica che funzioni

```bash
# health e modello
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/v1/models | python3 -m json.tool

# chat semplice
curl -s http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3.8-27b-eagle","messages":[{"role":"user","content":"Rispondi solo OK"}],"max_tokens":32}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['choices'][0]['message']['content'])"

# tool call (deve restituire tool_calls, non testo)
curl -s http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3.8-27b-eagle","messages":[{"role":"user","content":"Meteo a Roma? usa get_weather"}],"tools":[{"type":"function","function":{"name":"get_weather","parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}}],"max_tokens":512}' \
  | python3 -c "import sys,json;m=json.load(sys.stdin)['choices'][0]['message'];print(m.get('tool_calls'))"
```

### Benchmark rapido

```bash
python3 - <<'PY'
import json,time,urllib.request
t0=time.time(); n=0
p={"model":"qwen3.8-27b-eagle","messages":[{"role":"user","content":"Scrivi 200 parole sull'importanza dei test."}],"max_tokens":256,"temperature":0}
r=urllib.request.Request("http://127.0.0.1:8000/v1/chat/completions",data=json.dumps(p).encode(),headers={"Content-Type":"application/json"})
d=json.load(urllib.request.urlopen(r,timeout=600))
u=d["usage"]; dt=time.time()-t0
print(f"{u['completion_tokens']} token in {dt:.1f}s = {u['completion_tokens']/dt:.1f} tok/s")
PY
```

Valori attesi su GB10 (concorrenza 1): **~35 tok/s** su prompt agentico,
**~53 tok/s** su output ripetitivo, TTFT ~240 ms.

## 6. Parametri modificabili

| Parametro | Effetto | Dove |
|---|---|---|
| `--max-model-len` | contesto (default 65536) | comando/profilo |
| `--gpu-memory-utilization` | memoria riservata (0.45 consigliato) | comando/profilo |
| `--max-num-seqs` | concorrenza | comando/profilo |
| `tree_depth`, `node_top_k`, `max_verify_width` | forma dell'albero EAGLE4 | `--speculative-config` |
| `--enforce-eager` | disabilita CUDA graphs (debug) | aggiungere al comando |

Per disattivare EAGLE4: togliere `--speculative-config` e `VLLM_USE_V2_MODEL_RUNNER`.

## 7. Problemi noti

| Sintomo | Causa | Rimedio |
|---|---|---|
| la build si ferma a `eagle-harness-check` | wheel sbagliata o pip ha sostituito vLLM | reinstallare la wheel con `--no-deps`, poi `eagle-harness-check` |
| `Resolved architecture: ...` diversa da `LlamaForCausalLMEagle4` | draft non trovato | controllare `~/.cache/huggingface` e `HF_HUB_OFFLINE` |
| OOM all'avvio | `gpu_memory_utilization` troppo alta | abbassare a 0.40–0.45 |
| TTFT alto | verifica ad albero EAGLE | ridurre `tree_depth` o usare DFlash2 |
| `flashinfer_cutedsl` non disponibile | non esiste per arm64 | è normale: si usa il backend lineare di default |

## 8. Vuoi ricompilare da zero?

L'archivio contiene anche la ricetta completa:

```bash
./build-eagle.sh    # ~30-40 min, richiede rete e 10 GB liberi
```

Dettagli, errori e pin: `EAGLE4-BUILD.md`.
