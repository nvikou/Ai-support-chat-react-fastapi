"""Materialize the seeded NimbusDesk evaluation dataset.

Run from the repository root:

    python evaluation/scripts/generate_dataset.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.dataset.constants import (  # noqa: E402
    DATASET_SEED,
    DATASET_VERSION,
    MAX_DOCS,
    MAX_QUESTIONS,
    MIN_DOCS,
    MIN_QUESTIONS,
)
from evaluation.dataset.knowledge import build_knowledge_docs  # noqa: E402
from evaluation.dataset.questions import (  # noqa: E402
    build_labeled_questions,
)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def generate(output_dir: Path, seed: int) -> dict[str, object]:
    """Write knowledge markdown, questions.jsonl, and manifest."""
    rng = random.Random(seed)
    docs = build_knowledge_docs(rng)
    questions = build_labeled_questions(docs, rng)

    if not (MIN_DOCS <= len(docs) <= MAX_DOCS):
        raise SystemExit(f"doc count {len(docs)} outside band")
    if not (MIN_QUESTIONS <= len(questions) <= MAX_QUESTIONS):
        raise SystemExit(f"question count {len(questions)} outside band")

    knowledge_dir = output_dir / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    for old in knowledge_dir.glob("*.md"):
        old.unlink()

    doc_hashes: dict[str, str] = {}
    for doc in docs:
        text = doc.to_markdown()
        path = knowledge_dir / f"{doc.doc_id}.md"
        path.write_text(text, encoding="utf-8", newline="\n")
        doc_hashes[doc.doc_id] = _sha256_text(text)

    questions_path = output_dir / "questions.jsonl"
    lines = [json.dumps(item.to_json_row(), ensure_ascii=False) for item in questions]
    payload = "\n".join(lines) + "\n"
    questions_path.write_text(payload, encoding="utf-8", newline="\n")

    categories: dict[str, int] = {}
    escalate_true = 0
    for item in questions:
        categories[item.category] = categories.get(item.category, 0) + 1
        if item.should_escalate:
            escalate_true += 1

    manifest = {
        "dataset_version": DATASET_VERSION,
        "seed": seed,
        "product": "NimbusDesk",
        "doc_count": len(docs),
        "question_count": len(questions),
        "should_escalate_true": escalate_true,
        "categories": dict(sorted(categories.items())),
        "questions_sha256": _sha256_text(payload),
        "knowledge_sha256": {key: doc_hashes[key] for key in sorted(doc_hashes)},
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output_dir / "VERSION").write_text(
        DATASET_VERSION + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seed",
        type=int,
        default=DATASET_SEED,
        help=f"PRNG seed (default {DATASET_SEED})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evaluation" / "dataset",
        help="Dataset output directory",
    )
    args = parser.parse_args()
    manifest = generate(args.output, args.seed)
    print(
        "Wrote dataset",
        manifest["dataset_version"],
        f"docs={manifest['doc_count']}",
        f"questions={manifest['question_count']}",
        f"seed={manifest['seed']}",
    )


if __name__ == "__main__":
    main()
