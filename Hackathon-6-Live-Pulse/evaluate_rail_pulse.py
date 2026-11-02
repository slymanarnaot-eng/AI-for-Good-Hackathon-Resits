"""Evaluate Rail Pulse sentiment against 50 human labels and a simple word-list baseline.

Run this script from the Rail Pulse project folder using its virtual environment.
It reads human_label_sheet.csv, scores the exact text in that file with the same
Hugging Face model used by Rail Pulse, and writes new CSV/TXT result files.
It does not modify the database or the human-label sheet.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

MODEL_NAME = "nlptown/bert-base-multilingual-uncased-sentiment"
INPUT_CSV = Path("human_label_sheet.csv")
OUT_CSV = Path("evaluation_comparison.csv")
OUT_DISAGREEMENTS = Path("evaluation_disagreements.csv")
OUT_SUMMARY = Path("evaluation_summary.txt")
LABELS = ("negative", "neutral", "positive")

# This baseline deliberately uses evaluative words, not train-disruption terms
# such as "delay" or "storing". A factual announcement of a delay should not
# automatically become negative unless it contains negative evaluative language.
POSITIVE_TERMS = [
    r"\bgoed\w*\b", r"\bgeweldig\w*\b", r"\bfantastisch\w*\b",
    r"\bfijn\w*\b", r"\bprettig\w*\b", r"\btevreden\w*\b",
    r"\buitstekend\w*\b", r"\bprima\b", r"\bblij\w*\b",
    r"\bpracht\w*\b", r"\bmooi\w*\b", r"\bcomfortabel\w*\b",
    r"\btop\b", r"\bleuk\w*\b", r"\bbedankt\b", r"\bdank\w*\b",
    r"\bgood\b", r"\bgreat\b", r"\bexcellent\b", r"\bwonderful\b",
    r"\bnice\b", r"\bpleasant\b", r"\bhappy\b", r"\blove\w*\b",
    r"\bbeautiful\b", r"\bcomfortable\b", r"\bthank you\b", r"\bthanks\b",
    r"\bawesome\b", r"\bamazing\b", r"\benjoy\w*\b", r"\bperfect\b",
]
NEGATIVE_TERMS = [
    r"\bslecht\w*\b", r"\bverschrikkelijk\w*\b", r"\bvervelend\w*\b",
    r"\bbelachelijk\w*\b", r"\bwaardeloos\w*\b", r"\birritant\w*\b",
    r"\bfrustrerend\w*\b", r"\bellende\b", r"\bchaos\b",
    r"\bonbetrouwbaar\w*\b", r"\bteleurgesteld\w*\b", r"\bboos\w*\b",
    r"\bwoedend\w*\b", r"\bkut\b", r"\bklote\b", r"\bafschuwelijk\w*\b",
    r"\bdramatisch\w*\b", r"\bschandalig\w*\b", r"\bonacceptabel\w*\b",
    r"\bteleurstell\w*\b", r"\bjammer\b", r"\bgevaarlijk\w*\b",
    r"\bstress\w*\b", r"\bslecht geregeld\b", r"\bwaardeloze\b",
    r"\bbad\b", r"\bawful\b", r"\bterrible\b", r"\bridiculous\b",
    r"\bfrustrating\b", r"\bannoying\b", r"\bunreliable\b",
    r"\bdisappointed\b", r"\bangry\b", r"\bhate\w*\b",
    r"\bhorrible\b", r"\bdisaster\b", r"\bworst\b", r"\bpoor\b",
    r"\bunsafe\b", r"\bscary\b", r"\bawful\b", r"\bunacceptable\b",
]

POSITIVE_PATTERNS = [re.compile(p, re.I) for p in POSITIVE_TERMS]
NEGATIVE_PATTERNS = [re.compile(p, re.I) for p in NEGATIVE_TERMS]


def normalize_label(value: Any) -> str:
    label = str(value or "").strip().casefold()
    if label not in LABELS:
        raise ValueError(
            f"Invalid or missing human label {value!r}. "
            "Use only positive, neutral, or negative in your_label."
        )
    return label


def word_list_prediction(text: str) -> tuple[str, int, int]:
    positive_hits = sum(len(pattern.findall(text)) for pattern in POSITIVE_PATTERNS)
    negative_hits = sum(len(pattern.findall(text)) for pattern in NEGATIVE_PATTERNS)
    if positive_hits > negative_hits:
        label = "positive"
    elif negative_hits > positive_hits:
        label = "negative"
    else:
        label = "neutral"
    return label, positive_hits, negative_hits


def model_label(prediction: dict[str, Any]) -> tuple[str, int, float]:
    try:
        stars = int(str(prediction.get("label", "")).split()[0])
    except (ValueError, IndexError):
        stars = 3
    if stars <= 2:
        sentiment = "negative"
    elif stars == 3:
        sentiment = "neutral"
    else:
        sentiment = "positive"
    return sentiment, stars, float(prediction.get("score", 0.0))


def metrics(rows: list[dict[str, Any]], prediction_field: str) -> dict[str, Any]:
    correct = sum(row["human_label"] == row[prediction_field] for row in rows)
    confusion = {human: {pred: 0 for pred in LABELS} for human in LABELS}
    for row in rows:
        confusion[row["human_label"]][row[prediction_field]] += 1

    per_class = {}
    for label in LABELS:
        tp = confusion[label][label]
        support = sum(confusion[label].values())
        predicted = sum(confusion[h][label] for h in LABELS)
        precision = tp / predicted if predicted else 0.0
        recall = tp / support if support else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
        per_class[label] = {
            "support": support,
            "predicted": predicted,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    return {
        "correct": correct,
        "total": len(rows),
        "accuracy": correct / len(rows) if rows else 0.0,
        "confusion": confusion,
        "per_class": per_class,
    }


def write_confusion_lines(lines: list[str], title: str, result: dict[str, Any]) -> None:
    lines.append(title)
    lines.append("Rows = human label; columns = predicted label")
    lines.append("human\\predicted," + ",".join(LABELS))
    for human in LABELS:
        values = [str(result["confusion"][human][pred]) for pred in LABELS]
        lines.append(human + "," + ",".join(values))
    lines.append("")


def main() -> int:
    if not INPUT_CSV.exists():
        print(f"ERROR: {INPUT_CSV.resolve()} was not found.")
        print("Put this script beside human_label_sheet.csv in the project folder.")
        return 1

    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"id", "post_text", "your_label"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            print("ERROR: human_label_sheet.csv must contain these columns:", sorted(required))
            print("Found:", reader.fieldnames)
            return 1
        source_rows = list(reader)

    if len(source_rows) != 50:
        print(f"WARNING: expected 50 rows but found {len(source_rows)}. Continuing with all rows.")

    rows: list[dict[str, Any]] = []
    for row in source_rows:
        text = (row.get("post_text") or "").strip()
        if not text:
            print(f"ERROR: ID {row.get('id', '?')} has blank post_text. No results written.")
            return 1
        try:
            human = normalize_label(row.get("your_label"))
        except ValueError as exc:
            print(f"ERROR on ID {row.get('id', '?')}: {exc}")
            return 1
        baseline, pos_hits, neg_hits = word_list_prediction(text)
        rows.append({
            "id": (row.get("id") or "").strip(),
            "post_time": (row.get("post_time") or "").strip(),
            "post_text": text,
            "human_label": human,
            "human_reason_or_notes": (row.get("your_reason_or_notes") or "").strip(),
            "word_list_positive_hits": pos_hits,
            "word_list_negative_hits": neg_hits,
            "word_list_prediction": baseline,
        })

    print(f"Loaded {len(rows)} manually labeled rows from {INPUT_CSV}.")
    print(f"Loading model: {MODEL_NAME}")
    try:
        from transformers import pipeline
        classifier = pipeline("text-classification", model=MODEL_NAME, device=-1)
        predictions = classifier(
            [row["post_text"] for row in rows],
            truncation=True,
            max_length=256,
            batch_size=8,
        )
    except Exception as exc:
        print("ERROR loading/running the Hugging Face model:", repr(exc))
        print("Run this inside the project's activated .venv with transformers/torch installed.")
        return 1

    for row, pred in zip(rows, predictions):
        label, stars, confidence = model_label(pred)
        row["model_prediction"] = label
        row["model_stars"] = stars
        row["model_confidence"] = round(confidence, 4)
        row["model_agrees"] = label == row["human_label"]
        row["word_list_agrees"] = row["word_list_prediction"] == row["human_label"]

    model_metrics = metrics(rows, "model_prediction")
    baseline_metrics = metrics(rows, "word_list_prediction")

    columns = [
        "id", "post_time", "post_text", "human_label", "human_reason_or_notes",
        "model_prediction", "model_stars", "model_confidence", "model_agrees",
        "word_list_positive_hits", "word_list_negative_hits", "word_list_prediction",
        "word_list_agrees",
    ]
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in columns})

    disagreement_columns = [
        "id", "post_time", "post_text", "human_label", "human_reason_or_notes",
        "model_prediction", "model_stars", "model_confidence", "word_list_prediction",
        "word_list_positive_hits", "word_list_negative_hits",
    ]
    disagreements = [row for row in rows if not row["model_agrees"] or not row["word_list_agrees"]]
    with OUT_DISAGREEMENTS.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=disagreement_columns)
        writer.writeheader()
        for row in disagreements:
            writer.writerow({key: row.get(key, "") for key in disagreement_columns})

    lines = [
        "RAIL PULSE — HUMAN EVALUATION",
        f"Input: {INPUT_CSV}",
        f"Rows evaluated: {len(rows)}",
        f"Model: {MODEL_NAME}",
        "Important: predictions in this run were generated on the exact post_text in the human-label CSV.",
        "",
        f"Transformer model agreement: {model_metrics['correct']}/{model_metrics['total']} = {model_metrics['accuracy']:.1%}",
        f"Word-list baseline agreement: {baseline_metrics['correct']}/{baseline_metrics['total']} = {baseline_metrics['accuracy']:.1%}",
        "",
        "PER-CLASS METRICS — TRANSFORMER",
        "class,support,predicted,precision,recall,f1",
    ]
    for label in LABELS:
        item = model_metrics["per_class"][label]
        lines.append(f"{label},{item['support']},{item['predicted']},{item['precision']:.3f},{item['recall']:.3f},{item['f1']:.3f}")
    lines += ["", "PER-CLASS METRICS — WORD-LIST BASELINE", "class,support,predicted,precision,recall,f1"]
    for label in LABELS:
        item = baseline_metrics["per_class"][label]
        lines.append(f"{label},{item['support']},{item['predicted']},{item['precision']:.3f},{item['recall']:.3f},{item['f1']:.3f}")
    lines.append("")
    write_confusion_lines(lines, "CONFUSION MATRIX — TRANSFORMER", model_metrics)
    write_confusion_lines(lines, "CONFUSION MATRIX — WORD-LIST BASELINE", baseline_metrics)
    lines += [
        "LIMITATIONS OF THE WORD-LIST BASELINE",
        "This is a simple rule-based baseline, not a language model. It does not reliably understand negation, sarcasm, mixed feelings, context, or emojis. A neutral result means no listed positive/negative word was found or the hit counts tied.",
        "",
        "FILES CREATED",
        f"- {OUT_CSV}",
        f"- {OUT_DISAGREEMENTS}",
        f"- {OUT_SUMMARY}",
    ]
    OUT_SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\nFinished. Results:")
    print(f"  Transformer: {model_metrics['correct']}/{model_metrics['total']} ({model_metrics['accuracy']:.1%})")
    print(f"  Word-list baseline: {baseline_metrics['correct']}/{baseline_metrics['total']} ({baseline_metrics['accuracy']:.1%})")
    print(f"Created: {OUT_CSV.resolve()}")
    print(f"Created: {OUT_DISAGREEMENTS.resolve()}")
    print(f"Created: {OUT_SUMMARY.resolve()}")
    print("Original database and human-label sheet were not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
