# vLLM + EAGLE-4 su DGX Spark (GB10 / aarch64)

Wheel `aarch64` precompilata di vLLM con gli hook EAGLE-4, per NVIDIA DGX Spark
/ GB10 (sm_121) e Python 3.12. È la controparte arm64 delle wheel ufficiali
EAGLE-4, che sono solo x86_64.

La wheel è allegata alla **[release GitHub](https://github.com/Bobbinetor/vllm-eagle4-aarch64-gb10/releases/latest)**,
non è dentro git: 494 MB superano il limite di 100 MB per file dei repository
GitHub. La release contiene anche `SHA256SUMS`, e una GitHub Action riscarica e
verifica ogni asset pubblicato.

> **Non è un rilascio ufficiale** di Eagle AI Corp. o NVIDIA. La wheel è una
> build Apache-2.0 di vLLM. `eagle-harness` e il draft EAGLE-4 sono download
> separati, soggetti alla Eagle 4 Source-Available License.

La guida completa, i benchmark e le note di verifica sono nel
[README principale](README.md) (in inglese).

## Requisiti

- DGX Spark / GB10, aarch64, driver CUDA 13.x
- Docker con GPU (`--gpus all`)
- ~45 GB liberi per l'immagine, ~27 GB per i modelli
- Python 3.12 (solo per i controlli statici)

## Quick start

```bash
# 1. scarica wheel e checksum dalla release GitHub
gh release download v0.1.0 \
  --repo Bobbinetor/vllm-eagle4-aarch64-gb10 \
  --pattern '*.whl' --pattern 'SHA256SUMS'

# senza gh: usa curl
# curl -fLO https://github.com/Bobbinetor/vllm-eagle4-aarch64-gb10/releases/download/v0.1.0/vllm-0.32.0rc1.dev283+eagle.3-cp312-cp312-linux_aarch64.whl
# curl -fLO https://github.com/Bobbinetor/vllm-eagle4-aarch64-gb10/releases/download/v0.1.0/SHA256SUMS

# 2. verifica (il manifest copre anche i file della ricetta, da qui --ignore-missing)
sha256sum -c --ignore-missing SHA256SUMS
python3 scripts/audit_hooks.py vllm-*.whl

# 3. costruisci l'immagine
docker build -f docker/Dockerfile.eagle -t vllm-eagle:gb10 .

# 4. scarica i modelli (una volta sola)
hf download nvidia/Qwen3.8-27B-NVFP4
hf download EAGLE-Corp/Qwen3.8-27B-EAGLE4

# 5. avvia
./scripts/serve.sh
```

Il primo avvio richiede ~10–11 minuti. Nel log devono comparire:

```text
Resolved architecture: LlamaForCausalLMEagle4
eagle-harness: registered speculative method eagle_harness and draft LlamaForCausalLMEagle4
```

Poi:

```bash
./scripts/smoke.sh
```

## Verifica statica (senza GPU)

```bash
python3 scripts/audit_hooks.py vllm-0.32.0rc1.dev283+eagle.3-cp312-cp312-linux_aarch64.whl
```

Controlla i 10 hook richiesti da `eagle-harness` 0.1.4. Il risultato atteso è
`10/10 hooks present` e `RESULT: PASS`.

## Benchmark (misura del maintainer, 30/10/2026)

DGX Spark GB10, Qwen3.8-27B NVFP4, contesto 64K, concorrenza 1, 3 richieste:

| Configurazione | Agentic tok/s | Echo tok/s | TTFT agentic |
|---|---:|---:|---:|
| Base | 12,17 | 12,13 | 141 ms |
| DFlash2 | 29,10 | 29,22 | 138 ms |
| **EAGLE-4** | **35,17** | **53,05** | 239 ms |

Il valore "echo" è un prompt sintetico e ripetitivo: non usarlo come numero
generico. Dettagli e limiti in [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md).

## Documenti originali (italiano)

- [`docs/it/USO-WHEEL-EAGLE4.md`](docs/it/USO-WHEEL-EAGLE4.md) — uso della wheel
  su una seconda macchina
- [`docs/it/EAGLE4-BUILD.md`](docs/it/EAGLE4-BUILD.md) — build da sorgente,
  passo per passo, con tutti gli errori incontrati
- [`docs/VERIFICATION.md`](docs/VERIFICATION.md) — cosa è stato verificato e
  cosa no

## Segnala la tua run

Se lo provi su un DGX Spark, apri una **Discussion** (o un issue con il template
*Run report*) con l'output di `eagle-harness-check` e
`python3 scripts/audit_hooks.py vllm-*.whl`. I risultati verificati vengono
aggiunti al README principale. Anche i risultati negativi sono utili.

## Licenza

La wheel è Apache-2.0 (vedi [`licenses/`](licenses/) e [`NOTICE`](NOTICE)).
`eagle-harness` è sotto Eagle 4 Source-Available License, **non** una licenza
open source OSI, con restrizioni per l'uso commerciale. Leggi
[`docs/LICENSING.md`](docs/LICENSING.md) prima di un uso commerciale.

EAGLE, EAGLE-4 ed EAGLE-Harness sono marchi di Eagle AI Corp. NVIDIA, DGX e
GB10 sono marchi di NVIDIA Corporation. Questa repo non è affiliata né
approvata da nessuna delle due aziende.
