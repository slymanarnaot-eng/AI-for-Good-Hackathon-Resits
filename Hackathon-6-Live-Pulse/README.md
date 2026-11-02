# Rail Pulse — Dutch Railway Passenger Sentiment

Rail Pulse is a student prototype that collects public text about railway service and passenger experience in the Netherlands, applies a locally run sentiment model, stores results in SQLite, and displays changes over time in a Streamlit dashboard.

## Problem, user, and decision

Railway communications or service-quality analysts may need to notice recurring passenger concerns, such as delays, broken lifts, overcrowding, or poor information. Rail Pulse provides a searchable view of collected public posts and news items to help an analyst decide **which issue or time period to inspect more closely**. It is a monitoring aid; it does not replace service reports, direct passenger feedback, or human review.

## SDG 9 relevance

This project relates to **UN Sustainable Development Goal 9: Industry, Innovation and Infrastructure** because railways are transport infrastructure, and Rail Pulse explores whether a continuously running data tool can help an analyst spot potential service-quality issues. The project is a prototype and does not claim to measure the experience of all railway passengers.

## Data sources and source terms

The collector uses:

- **Bluesky** public search and Jetstream endpoints.
- **Mastodon** public hashtag endpoints on configured instances.
- **RSS feeds** from news and rail-related publishers, including NOS, regional broadcasters, NS Nieuws, and Treinreiziger.nl.
- **Hacker News** public search comments as a supplementary English-language source.

The project uses public endpoints and feeds configured in `listen.py`; it does not intentionally bypass access controls. Public availability does not automatically grant permission to republish content or to ignore source rules. Bluesky has its own Terms of Service and API documentation; Mastodon is federated, so instance-level terms and privacy policies can differ; each RSS publisher can set its own conditions; and the Hacker News API has its own documentation. Check the current terms for each source before further collection, external sharing, or publication. Do not publish the collected post text or dataset as a general-purpose archive without checking those terms and any applicable rights.

Useful starting points:

- [Bluesky Terms of Service](https://bsky.social/about/support/tos)
- [Bluesky developer documentation](https://docs.bsky.app/)
- [Mastodon API documentation](https://docs.joinmastodon.org/)
- [Hacker News API documentation](https://github.com/HackerNews/API)
- For RSS, check the terms and content-use policy of each publisher in `listen.py` individually.

## How it works

1. **Collection:** `listen.py` queries the sources above and applies keyword and relevance checks. The results depend on search terms, filtering, source availability, and public posting behavior.
2. **Sentiment analysis:** The collector runs the Hugging Face model `nlptown/bert-base-multilingual-uncased-sentiment` locally.
3. **Storage:** `storage.py` stores post text, publication time, collection time, predicted sentiment, topic, and a hash used for duplicate detection in `rail_pulse_clean.db`.
4. **Dashboard:** `dashboard.py` uses Streamlit to show sentiment percentages, daily post counts, an average sentiment score over time, topic counts, filters, and the items behind a change.
5. **Evaluation:** `evaluate_rail_pulse.py` compares the transformer and a simple word-list baseline with 50 human-labeled posts.

## Model card summary

- **Model:** [`nlptown/bert-base-multilingual-uncased-sentiment`](https://huggingface.co/nlptown/bert-base-multilingual-uncased-sentiment)
- **Architecture / base model:** multilingual uncased BERT fine-tuned for sentiment classification.
- **Intended use in the model card:** sentiment analysis of product reviews, rather than railway announcements or passenger-service posts.
- **Languages covered by the model card:** English, Dutch, German, French, Spanish, and Italian.
- **Training data described in the model card:** product reviews (150,000 English; 80,000 Dutch; 137,000 German; 140,000 French; 72,000 Italian; and 50,000 Spanish reviews).
- **Original outputs:** five star classes. Rail Pulse maps 1–2 stars to negative, 3 stars to neutral, and 4–5 stars to positive.
- **License listed on Hugging Face:** MIT.
- **Important limitation:** the training domain is product reviews, not railway service feedback. The model may confuse a negative event with a negative opinion, and its performance on product-review tests should not be assumed to transfer to railway posts.

The model card reports 57% exact-star accuracy on its held-out Dutch product-review test set (93% within one star). These figures are from the model's own product-review evaluation; they are **not** a performance estimate for Rail Pulse. On this project's 50 human-labeled posts, the transformer agreed with the human labels on 7/50 items (14%).

## Collection run and stored data

The recorded 48-hour collection run saved **302 new records**, meeting the assignment target of at least 300 new items. The database contained **534 records in total** after that run. These figures describe that recorded run and database snapshot; a later run may produce different results.

## Requirements

Python 3.11 or newer is recommended. Internet access is required to collect current public items and to download the Hugging Face model the first time. Tested in the project environment with Python 3.14.7.

Dependencies used by the project include `websockets`, `transformers`, `torch`, `streamlit`, `pandas`, and `plotly`. They are listed in `requirements.txt`.

## Setup

Open PowerShell in the `rail-pulse-learning` project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If activation is blocked by local PowerShell policy, use the activation method allowed by your environment or call `.venv\Scripts\python.exe` directly.

## Run the collector

Check whether the configured public sources respond. This check does not start the 48-hour collection run:

```powershell
python listen.py --check-source
```

For a short five-minute test without historical backfill:

```powershell
python listen.py --test-minutes 5 --backfill-hours 0
```

For the configured collection run:

```powershell
python listen.py
```

The default run imports up to 72 hours of recent history and then runs the live collection window for 48 hours. Keep the computer and terminal running. Pressing Ctrl+C stops the run early. The script reports the number of records saved; it does not treat reaching 300 records as a reason to end the 48-hour timer.

## Run the dashboard

Ensure `rail_pulse_clean.db` is in the same folder as `dashboard.py`, then run:

```powershell
streamlit run dashboard.py
```

Open the local URL printed by Streamlit (usually `http://localhost:8501`). The dashboard reads the existing database; running the dashboard does not start data collection.

## Run the evaluation

`evaluate_rail_pulse.py` expects `human_label_sheet.csv` in the project directory. Labels should be `positive`, `neutral`, or `negative`.

```powershell
python evaluate_rail_pulse.py
```

The script creates:

- `evaluation_summary.txt` — overall agreement, per-class metrics, and confusion matrices.
- `evaluation_comparison.csv` — the 50 human labels and both systems' predictions.
- `evaluation_disagreements.csv` — posts where a system disagreed with the human label.

### Results on the 50-post sample

The sample contains 41 neutral, 7 negative, and 2 positive labels.

- **Transformer:** 7/50 agreement (14%). It predicted 44 posts as negative, including 40 that were labeled neutral by the human reviewer.
- **Word-list baseline:** 44/50 agreement (88%). It correctly labeled all 41 neutral items and both positive items, but identified only 1 of the 7 negative items.

The sample is small and imbalanced. The baseline's high agreement is mainly driven by its neutral predictions and does not mean it reliably detects complaints. The transformer frequently treated factual disruption announcements as negative sentiment. These results are preliminary and should not be generalized to all passengers or used as proof that either system is ready for operational use.

## Ethical reflection

The stream represents people and publishers who post publicly and whose content is found by these queries; it excludes passengers who do not post online, whose posts are private, who use other languages or platforms, or whose wording does not match the filters. One very active account, a news burst, duplicated reporting, or irrelevant keyword matches could shift the chart. The evaluation also found that the transformer often labels factual disruption notices as negative, so a dashboard peak might reflect the number of incident reports rather than how passengers feel. I addressed some of this risk by displaying the number of items and the original text alongside sentiment, adding a dashboard warning that labels can be wrong, and manually evaluating 50 posts against a word-list baseline. The database does not have separate username or profile columns, but post text and timestamps can still contain identifying information. I will keep the dataset local for the project, avoid publishing unnecessary raw text, review the applicable source terms, and treat the dashboard as a prompt for human investigation—not a representative survey or an automatic basis for operational decisions.

## Project files

Core files for running and evaluating the project:

- `listen.py` — collects public items, filters them, runs the sentiment model, and reports collection statistics.
- `storage.py` — SQLite database setup and storage helpers.
- `dashboard.py` — Streamlit dashboard.
- `rail_pulse_clean.db` — the cleaned dataset used by the collector and dashboard.
- `rail_pulse.log` — collection log evidence.
- `human_label_sheet.csv` — the 50 manually labeled posts used for evaluation.
- `human_label_sheet.xlsx` — a spreadsheet copy for reviewing the labels.
- `evaluate_rail_pulse.py` — runs the transformer and word-list baseline comparison.
- `evaluation_summary.txt` — evaluation metrics and confusion matrices.
- `evaluation_comparison.csv` — the 50 human labels and both systems' predictions.
- `evaluation_disagreements.csv` — posts where a system disagreed with the human label.
- `rail_pulse_evaluation_results.xlsx` — formatted evaluation workbook.
- `rail_pulse_evaluation_section.md` — report section with methodology, results, failure examples, and limitations.
- `prepare_evaluation.py` — optional helper for preparing a new blind sample; do not run it over your final labels because it recreates the label sheet.
- `requirements.txt` — Python dependencies.
- `.gitignore` — excludes local environments and Python cache files from Git.
- `README.md` — this documentation.

`model_predictions.csv` and `model_predictions_for_sample.csv` are not required for the final submission because the authoritative predictions are already included in `evaluation_comparison.csv`. Keep them only if you need them for your own records.

## Reproducibility note

For stronger reproducibility, record the exact Python and package versions used in your environment. Include the code, the required collected data, the evaluation test table, this README, and the ethical reflection in your portfolio repository. Model weights, public-source content, access policies, and returned live search results can change, so a later run may not reproduce the same collection or scores.
