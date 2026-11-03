# VateCon developer targets. Prefer these over ad-hoc command lines.
PYTHON ?= python
RECALL_AT_5_THRESHOLD ?= 0.35

.PHONY: eval eval-tests help

help:
	@echo "Targets:"
	@echo "  make eval        Run evaluation tests + offline RAG harness"
	@echo "  make eval-tests  Run evaluation/ unit tests only"

eval-tests:
	$(PYTHON) -m pytest evaluation/tests -q --no-cov

# Full quality gate used locally and by .github/workflows/eval.yml.
# Exits non-zero when recall@5 < RECALL_AT_5_THRESHOLD.
eval: eval-tests
	$(PYTHON) evaluation/run_eval.py \
		--threshold $(RECALL_AT_5_THRESHOLD)
