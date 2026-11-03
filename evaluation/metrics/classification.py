"""Binary classification metrics (escalation labels)."""

from __future__ import annotations


def binary_prf(
    y_true: list[bool],
    y_pred: list[bool],
) -> dict[str, float]:
    """Precision, recall, F1 for the positive class (escalate=True)."""
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred length mismatch")
    tp = fp = fn = 0
    for truth, pred in zip(y_true, y_pred, strict=True):
        if pred and truth:
            tp += 1
        elif pred and not truth:
            fp += 1
        elif (not pred) and truth:
            fn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = binary_f1(precision, recall)
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "support_positive": float(sum(1 for t in y_true if t)),
    }


def binary_f1(precision: float, recall: float) -> float:
    if precision + recall == 0.0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)
