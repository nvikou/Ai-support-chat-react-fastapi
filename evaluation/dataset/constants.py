"""Fixed knobs for the synthetic evaluation dataset."""

from __future__ import annotations

# Bump when the generator or committed artifacts change meaning.
DATASET_VERSION = "nimbusdesk-v1"

# Same seed → identical docs + questions on every machine.
DATASET_SEED = 7

PRODUCT_NAME = "NimbusDesk"
PRODUCT_DOMAIN = "helpdesk SaaS"

MIN_DOCS = 30
MAX_DOCS = 50
MIN_QUESTIONS = 150
MAX_QUESTIONS = 200

# Target sizes inside the allowed bands (generator asserts these).
TARGET_DOCS = 40
TARGET_QUESTIONS = 180
