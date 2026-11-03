# Term 1 - Week 5: Machine Learning Basics

---

## 1. Homework & workshop assignments -> [`homework/`](homework/)

**What was the assignment?**

**What did I hand in?**

**What did I find difficult, and how did I solve it?**


### Checklist
- [ ] My workshop / homework files are in `homework/`
- [ ] Everything runs without errors, or I explained what does not and why

---

## 2. Hackathon prototype -> [`hackathon/`](hackathon/)

**Project title:** The Big Short: When Mortgages Go Wrong

**My pair partner:** Slyman

**Tool we had to use:** Python with scikit-learn, in a Jupyter notebook / Google Colab.

**Youtube link:** https://youtu.be/DscNu96ViJA


**SDG we had to address:** SDG 8 — Decent Work and Economic Growth, particularly Target 8.10 (stronger financial institutions and access to financial services).

**What problem does it solve, and for whom?**
We looked at the mortgage crisis because we wanted to work on a real financial problem, not just predict a random label. Our question is: **Can information recorded when a mortgage starts predict whether it will become 90+ days late on payments during its first 24 months?** We focus on loans originated in 2006 in the United States. Our intended user is a mortgage credit-risk analyst working for an institutional investor who studies mortgage portfolios. They could use the results to flag patterns for further review, not to automatically reject a person's loan. Freddie Mac publishes the data for credit-performance research and risk modelling. We have not spoken to Freddie Mac or proved that an analyst would adopt our exact notebook.

The wider issue matters because mortgage losses contributed to the 2007–2010 financial crisis. Our notebook does **not** predict another financial crisis or explain all of its causes. It studies one narrower repayment outcome. See the [Federal Reserve's overview](https://www.federalreservehistory.org/essays/subprime-mortgage-crisis) and [Freddie Mac's dataset explanation](https://www.freddiemac.com/research/datasets/sf-loanlevel-dataset).

**What did you build?**
A notebook that reads the 2006 ZIP and joins historical mortgage information to monthly repayment records, creates one yes/no outcome per eligible loan, and compares a simple baseline with three scikit-learn classifiers. It displays a comparison table, confusion matrices, a check of mistakes by occupancy group and a prediction for a fictional new mortgage. It is a research prototype, not a mortgage approval tool.

**Link to the live thing (if any):** No deployed website. The runnable notebook is the demo: [`Big_Short_Model_Showdown.ipynb`](hackathon/Big_Short_Model_Showdown.ipynb) 

### Dataset card — where the data came from
Freddie Mac's **Single-Family Loan-Level Dataset**, specifically the **2006 Standard Sample**. Freddie Mac collects and publishes information on selected single-family loans it purchased or guaranteed, with origination details and later monthly loan performance. The standard sample is documented as containing approximately 50,000 loans per complete origination year, and our executed notebook shows **37,674 labelled loans after exclusions**. The official `sample_2006.zip` was downloaded and used in Google Colab. 

- Source: https://www.freddiemac.com/research/datasets/sf-loanlevel-dataset
- Field definitions and sample documentation: https://www.freddiemac.com/fmac-resources/research/pdf/user_guide.pdf
- Geography / year: United States, loans originated in 2006.
- Population: Freddie Mac loans meeting its selection rules; **not** all US borrowers or all subprime loans.
- Raw structure: origination file (one record per loan) and monthly performance file (multiple records per loan).
- Planned outcome: `target=1` if recorded ordinary delinquency status reaches 3–9 (90+ days) within loan ages 1–24; `target=0` if there is sufficient observed follow-up without that event. Ambiguous early exits are excluded, rather than automatically labelled safe.
- Inputs: original credit score, original LTV/CLTV, DTI, loan amount, interest rate, occupancy, loan purpose, state, and other origination fields. At least five will be used, subject to validating the data dictionary.
- Dataset licence / access: registration and Freddie Mac's terms apply. **We still need to confirm the exact accepted terms and whether redistribution is allowed before putting raw files on public GitHub.**
- Actual labelled rows: **37,674** (from 50,000 raw origination records; 12,326 excluded from the final labelled data).
- Actual number of model features: **15**. Labelled class balance: **36,687 negative (97.38%)** and **987 positive (2.62%)**. Modelling subset: 12,000 loans (11,686 negative and 314 positive).
- Limitations: selected fixed-rate loans; missing or coded values; early payoffs; older economic conditions; no complete demographic representation. The sample is not a complete picture of the 2008 crisis.

### How the notebook works, step by step
1. **Load raw data:** read the two pipe-separated Freddie Mac files. The monthly file is linked to the origination file by loan ID.
2. **Make the target:** check each loan's first 24 months. Mark a positive if it reaches the defined serious delinquency status; exclude cases without enough evidence for a reliable negative.
3. **Explore:** print raw and final sizes, duplicate IDs, missing-value percentages, numeric summaries, suspect values and class balance. Duplicate feature values can be valid even when loan IDs must be unique.
4. **Split before fitting preprocessing:** first select a reproducible stratified subset of at most 12,000 labelled loans to keep KNN tuning practical, then use a fixed random seed (`42`) and a stratified 80/20 training/test split. We leave the test set alone until final evaluation.
5. **Preprocess inside scikit-learn:** a `ColumnTransformer` imputes missing numerical values with the training median, scales them, and fills/one-hot-encodes categorical fields. KNN depends on distances, so scaling is especially important. Logistic regression also benefits from comparable numerical scales.
6. **Baseline:** `DummyClassifier(strategy='most_frequent')` predicts the majority class. This is the minimum comparison, not a useful risk model by itself.
7. **Tune three models:** KNN (`n_neighbors` and weights), logistic regression (`C`) and decision tree (depth and minimum leaf size). `GridSearchCV` uses the same stratified three-fold training CV and **recall for class 1**. A table shows each tried setting and its CV score.
8. **Evaluate once:** report training recall, CV recall mean and spread, test precision/recall/F1 and confusion matrices for the baseline and all three models. We compare training and test results to look for overfitting or underfitting.
9. **Review errors:** look at false negatives (missed serious delinquencies) and false positives (loans wrongly flagged). Compare results across occupancy groups when there are enough cases. Occupancy is **not** a substitute for checking protected demographic groups.
10. **Use the model:** show a prediction and probability for a fictional mortgage. The notebook picks a CV-leading model for demonstration, but that does not mean it is safe to deploy or recommend.

**Why recall?** A false negative means a loan that becomes seriously delinquent was missed, so an analyst might underestimate a risk pattern. Recall tells us how many actual delinquent loans we find. But a false positive also matters: flagging a loan that stays current could waste time and, if misused, unfairly affect borrowers. That is why we also look at precision, F1 and the confusion matrix. A model with recall of 1.0 that flags everyone is not automatically good.

**What did the comparison show?**

We trained and tuned all three models in scikit-learn, alongside a majority-class DummyClassifier. We used the same 80/20 stratified split (9,600 training and 2,400 test rows), three-fold stratified cross-validation, random seed 42, and **recall** as our main tuning metric. The test set was only used for the final evaluation. These are the actual saved notebook results:

| Model | Best settings | Training recall | CV recall (mean ± SD) | Test precision | Test recall | Test F1 |
|---|---|---:|---:|---:|---:|---:|
| Dummy baseline | Most frequent | 0.000 | 0.000 ± 0.000 | 0.000 | 0.000 | 0.000 |
| KNN | 5 neighbours; uniform weights | 0.032 | 0.000 ± 0.000 | 0.000 | 0.000 | 0.000 |
| Logistic regression | C = 0.1 | 0.821 | 0.729 ± 0.039 | 0.076 | 0.730 | 0.138 |
| Decision tree | Max depth = 3; minimum 100 samples per leaf | 0.817 | 0.828 ± 0.051 | 0.060 | 0.698 | 0.110 |

The decision tree had the highest cross-validation recall (0.828), but on the untouched test set logistic regression did better on recall, precision and F1. We should not pick the winner just because of the test set: that would mean using test data to make a new modelling decision. The cross-validation scores also have variation, and the tree's drop from CV recall to test recall shows why we needed a held-out test set. KNN and the dummy baseline both missed every positive test case.

**The confusion matrices and what went wrong:** The notebook shows one for each model. The decision tree correctly identified 44 of the 63 seriously delinquent mortgages in the test set, missed 19, and incorrectly flagged **690** mortgages that did not reach serious delinquency. Its precision was only about **6%**. Logistic regression also produced many false alerts: precision was about **7.6%**. Since the positive class is rare, catching more risky mortgages also means flagging many that do not become seriously delinquent. These are not small mistakes if someone were to use the results for actual lending decisions.

**Which model would we recommend?** We would **not recommend any of these models for actual loan approval or automatic credit-risk decisions**. The low precision means too many false alarms. Logistic regression looks more promising for another research experiment because of its stronger test precision and F1, while the decision tree is easier to explain and had the best training-only CV recall. For a real analyst, the next step would be to test other thresholds and models on fresh data, compare the cost of false alerts with missed cases, and check fairness properly. We did **not** tune a threshold using the test set.

**The fictional prediction:** The notebook's CV-leading decision tree predicted **class 1 (serious delinquency)** for the made-up mortgage, with an estimated probability of **0.670**. This is an uncalibrated model score, not a trustworthy estimate of someone's actual chance of default. We would not use it to reject an application.

**Group check and limitations:** The notebook compares the tree's errors by occupancy type. For primary residences there were 59 actual positives and recall was 0.695; for investor properties there was only one positive (recall 1.0), and for second homes there were three positives (recall 0.667). With so few positive cases in two groups, we cannot draw strong conclusions. Occupancy is not race, gender or nationality, so this is **not proof of fairness**. Another limitation is that loans paid off early without a serious delinquency were excluded rather than automatically treated as negative, which affects the population we can model.

**How do I run it?**
1. Download the **2006 Standard Sample** origination and monthly performance files from Freddie Mac. Read the access terms first.
2. Open `hackathon/Big_Short_Model_Showdown.ipynb` in Google Colab. The code uses Colab's standard Python scientific packages: pandas, numpy, matplotlib and **scikit-learn**. No additional pip installs are intended.
3. Upload `sample_2006.zip` into the Colab Files panel (or put it beside the notebook locally). The notebook reads the ZIP directly; no manual extraction or filename edits are needed.
4. Click **Runtime → Run all**. The notebook creates the comparison table, four confusion matrices, a group check, the fictional prediction and `model_comparison.csv`. Save the executed notebook with outputs visible.
5. Versions recorded in our successful Colab run: **Python 3.13.16, pandas 2.2.3, numpy 2.1.3, scikit-learn 1.6.1**. Matplotlib is used for the figures; its version was not printed in the saved output. Colab versions can change over time. If rerunning, compare your environment and keep the raw ZIP unchanged.

**Who did what?**
- Me: technical notebook, dataset preparation, model testing, documenting the code and explaining the comparison.
- Slyman: proposed the movie-inspired idea, researched the mortgage problem, prepared the desk research and will make the slides.
- We both need to understand the model choice and results. AI was used to help draft and review code and writing; we need to test it and be able to explain it ourselves.

**Ethical reflection — what are the risks of your tool? Who could it harm?**
The people most affected would be borrowers, even though our intended user is a portfolio analyst. If a prediction were used to reject someone for a mortgage, a false positive could unfairly limit their access to credit. A false negative could make risk look lower than it is. Credit scores and location can also reflect older inequalities, and our dataset does not include everyone who applied for a mortgage, especially rejected applicants. We cannot honestly say our model is fair across race, gender or immigration background when we do not have reliable information to test that. Our concrete safeguards are to use only information known at origination, avoid automatic loan decisions, show both types of error, and compare error rates by occupancy group. The comparison was completed, but two groups had too few positive cases for reliable conclusions. We will also check the dataset's use terms and avoid publishing restricted loan records. Before any real use, we would need a proper fairness review, updated data, external validation and human oversight.

**How does this connect to AI for Good and SDG 8?**
[UN SDG 8 Target 8.10](https://sdgs.un.org/goals/goal8) is about strengthening financial institutions and access to financial services. Our project connects indirectly by testing whether mortgage risk can be understood more reliably. Better information could support responsible financial risk management, but an unfair model could also make access worse. We are **not** claiming our notebook increases access to mortgages, prevents crises or achieves the SDG on its own.

### Checklist
- [x] Prototype notebook drafted with three scikit-learn classifiers and a baseline
- [x] Raw 2006 dataset downloaded and notebook executed; public redistribution rights still need checking
- [x] Notebook run end-to-end in Colab with outputs saved
- [x] Actual comparison and cautious recommendation filled in
- [x] Presentation slides added to `hackathon/`
- [x] Project-specific ethical risks and safeguards documented

---

## 3. Presentation -> [`presentation/`](presentation/)

*Only fill this in for the week your group was selected to present. You need at least **one** of these across the whole term.*

- [ ] My group presented in this week
- [ ] Slides are in `presentation/`
- [ ] Proof of the live demo is in `presentation/` (recording, screenshots, or link)

**How did it go? What would I do differently next time?**

---

## 4. Reflection

**What is the most important thing I learned this week?**
The biggest thing I learned is that getting a model to run is not the same as making it useful. The decision tree looked good on recall during cross-validation, but its test precision was only around 6%. That made me realise why we have to look at the actual mistakes and not just the highest score.

**Where does this connect to "AI for Good"?**
It is not enough to say a model helps with financial decisions. We have to check what happens when it makes a mistake, and whether its results might make things harder for borrowers.
