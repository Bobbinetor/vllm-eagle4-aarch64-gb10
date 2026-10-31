# Licensing

This page is a practical map of the licenses around this build. It is not legal
advice. Read the original licenses before commercial use.

## What this repository redistributes

**Only the vLLM wheel and the build/configuration files in this repo.**

The wheel is a modified build of vLLM:

| Item | License | Notes |
|---|---|---|
| vLLM | Apache-2.0 | `licenses/Apache-2.0.txt` |
| `eagle-hq/vllm` hook files | Apache-2.0 | Each file carries `SPDX-License-Identifier: Apache-2.0` |
| FlashAttention (vLLM fork) | BSD-3-Clause | `licenses/BSD-3-Clause-flash-attention.txt` |
| CUTLASS | BSD-3-Clause | `licenses/BSD-3-Clause-CUTLASS.txt` |
| DeepGEMM | MIT | `licenses/MIT-DeepGEMM.txt` |

Apache-2.0 requires that redistributions keep the license, keep notices, and
state significant changes. This repository does that:

- `licenses/Apache-2.0.txt` contains the full license.
- `NOTICE` states the upstream project, the source commit, and the modifications.
- `CHANGELOG.md` and `docs/VERIFICATION.md` record the build changes.

The wheel's `METADATA` declares `License-Expression: Apache-2.0`. No Python
source file in the wheel is marked `LicenseRef-Eagle-4-Source-Available`; the
EAGLE-4 hook files are Apache-2.0.

## What this repository does **not** redistribute

| Component | License | How to get it |
|---|---|---|
| `eagle-harness` | **Eagle 4 Source-Available License** — not OSI open source | `pip install "eagle-harness[vllm]"` from PyPI |
| `EAGLE-Corp/Qwen3.8-27B-EAGLE4` | `license: other` (EAGLE-4 license) | Hugging Face |
| `nvidia/Qwen3.8-27B-NVFP4` | Apache-2.0 | Hugging Face |

### The EAGLE-4 license in one paragraph

The Eagle 4 Source-Available License is **not** an OSI-approved open-source
license. It grants rights for genuine internal evaluation, academic research,
non-profit research, education, and personal non-commercial use, and it
separately addresses commercial use. It also incorporates a trademark policy.
If you plan to use `eagle-harness` or an EAGLE-4 draft in a paid product,
customer-facing service, hosted API, or other commercial context, read the
license and contact Eagle AI Corp. (`licensing@eagle.ai`) first.

Source: <https://github.com/eagle-hq/EAGLE-4/blob/main/LICENSE>

## Trademarks

EAGLE, EAGLE-4, and EAGLE-Harness are trademarks or claimed trademarks of
Eagle AI Corp. NVIDIA, DGX, and GB10 are trademarks of NVIDIA Corporation.

This repository is unofficial. It is not affiliated with, sponsored by, or
endorsed by Eagle AI Corp. or NVIDIA. It uses the names only to describe
compatibility. No company logos are included.

If you fork or redistribute this repository, keep the disclaimer and do not
imply endorsement.

## No warranty

The wheel and scripts are provided "AS IS", without warranty of any kind. See
the Apache License, Version 2.0, for the disclaimer of warranties and limitation
of liability.

## Takedown / upstreaming

If you represent Eagle AI Corp. or NVIDIA and want this build renamed, upstreamed,
or removed, open an issue in this repository. It will be handled promptly.
