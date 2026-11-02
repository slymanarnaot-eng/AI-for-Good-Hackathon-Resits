import csv
import random
import re
import sqlite3
from pathlib import Path

db_path = Path("rail_pulse_clean.db")

rail_pattern = re.compile(
    r"\b(?:"
    r"trein\w*|spoor\w*|wisselstoring|seinstoring|stroomstoring|"
    r"bovenleiding|prorail|sprinter\w*|intercity\w*|perron\w*|"
    r"nederlandse spoorwegen|ns\.nl|ns app|ns abonnement|"
    r"ov[- ]?chipkaart|ovpay|arriva|blauwnet|"
    r"railway\w*|railroad\w*|commuter rail|"
    r"train\w*|stranded train|rail replacement bus"
    r")\b",
    re.IGNORECASE,
)

with sqlite3.connect(db_path) as con:
    rows = con.execute(
        "SELECT id, post_time, post_text, sentiment "
        "FROM posts ORDER BY id"
    ).fetchall()

# Use clear railway references and remove exact duplicate text from the sample.
eligible = {}
for post_id, post_time, post_text, sentiment in rows:
    if not post_text or not rail_pattern.search(post_text):
        continue
    normalized = " ".join(post_text.lower().split())
    if normalized not in eligible:
        eligible[normalized] = (
            post_id, post_time, post_text, sentiment
        )

sample_pool = list(eligible.values())
if len(sample_pool) < 50:
    raise SystemExit(
        f"Only {len(sample_pool)} distinct rail-related posts found; "
        "no evaluation files were created."
    )

random.Random(42).shuffle(sample_pool)
sample = sample_pool[:50]

with open("human_label_sheet.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow([
        "id",
        "post_time",
        "post_text",
        "your_label",
        "your_reason_or_notes",
    ])
    for post_id, post_time, post_text, sentiment in sample:
        writer.writerow([post_id, post_time, post_text, "", ""])

with open(
    "model_predictions_for_sample.csv",
    "w",
    newline="",
    encoding="utf-8-sig",
) as f:
    writer = csv.writer(f)
    writer.writerow(["id", "model_sentiment"])
    for post_id, post_time, post_text, sentiment in sample:
        writer.writerow([post_id, sentiment])

print("Evaluation sample prepared successfully.")
print("Distinct rail-related posts available:", len(eligible))
print("Posts in your manual-label sheet:", len(sample))
print("File 1: human_label_sheet.csv")
print("File 2: model_predictions_for_sample.csv")
print()
print("IMPORTANT: Open human_label_sheet.csv first.")
print("Do not open the model-predictions file until you finish your labels.")
print("Use only: positive, neutral, or negative.")
print("Your database has not been changed.")
