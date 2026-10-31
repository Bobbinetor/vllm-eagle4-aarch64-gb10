WHEEL := $(wildcard vllm-*.whl)
IMAGE ?= vllm-eagle:gb10
BASE_URL ?= http://127.0.0.1:8000
VERSION ?= v0.1.0

.PHONY: help check verify verify-static audit image serve smoke bench release-dry release clean

help:
	@echo "make check        - repo checks: links, sources, checksums, leaks"
	@echo "make verify       - checksums, wheel tag, static hook audit (full host check)"
	@echo "make verify-static- artifact only: checksums + tag + hook audit"
	@echo "make audit        - static hook audit only"
	@echo "make image        - build $(IMAGE) from the prebuilt wheel"
	@echo "make serve        - start the container with the validated profile"
	@echo "make smoke        - run the OpenAI-compatible smoke test"
	@echo "make bench        - run the agentic benchmark"
	@echo "make release-dry  - run every release check, publish nothing"
	@echo "make release      - create a draft GitHub Release (needs --publish)"
	@echo "make clean        - remove __pycache__ and local bench output"

check:
	python3 scripts/check_repo.py
	bash -n scripts/*.sh build/*.sh

verify:
	./scripts/verify.sh

verify-static:
	./scripts/verify.sh --static

audit:
	python3 scripts/audit_hooks.py $(WHEEL)

image:
	docker build -f docker/Dockerfile.eagle -t $(IMAGE) .

serve:
	./scripts/serve.sh

smoke:
	BASE_URL=$(BASE_URL) ./scripts/smoke.sh

bench:
	python3 scripts/bench.py --base-url $(BASE_URL) --preset agentic --requests 3 --json-out bench-$$(date +%Y%m%d-%H%M%S).json

release-dry:
	./scripts/release.sh --version $(VERSION)

release:
	./scripts/release.sh --version $(VERSION) --publish

clean:
	rm -rf scripts/__pycache__ __pycache__
	rm -f bench-*.json
