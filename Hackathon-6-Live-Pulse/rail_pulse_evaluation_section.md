# Human Evaluation and Model Comparison

## Method

I manually labeled 50 railway-related public posts as positive, neutral, or negative. I then ran the local Hugging Face model `nlptown/bert-base-multilingual-uncased-sentiment` on the exact text in the human-label CSV and compared its predictions with my labels. I also evaluated a simple word-list baseline on the same 50 posts. This is a small, manually labeled sample rather than a representative survey of all railway passengers.

## Results

The sample contained 41 neutral posts, 7 negative posts, and 2 positive posts. The transformer agreed with 7 of the 50 human labels (14%). The word-list baseline agreed with 44 of 50 labels (88%).

The transformer predicted 44 posts as negative, including 40 posts that I had labeled neutral. Its negative-class precision was 9.1% and recall was 57.1%. This shows that it frequently interpreted the negative event described in a railway disruption notice as negative sentiment expressed by the author.

The word-list baseline correctly classified all 41 human-labeled neutral posts and both positive posts, but correctly identified only 1 of the 7 negative posts (14.3% negative recall). It predicted 45 posts as neutral, so its high overall agreement should not be interpreted as evidence that it reliably detects passenger complaints. The small class counts—especially only two positive examples—also make per-class results uncertain.

## Examples of model failures

1. **Factual disruption incorrectly labeled negative.** Post ID 65 says, “STORING: defecte trein Breda - Tilburg.” I labeled this neutral because it is a factual service alert without an expressed opinion. The transformer predicted negative (one star, confidence 0.7466). It appears to react to the disruption wording rather than distinguish an incident report from the author's sentiment.

2. **A resolved disruption still labeled negative.** Post ID 451 begins “Storing voorbij” (the disruption has ended). I labeled it neutral because it reports a resolved issue without expressing an emotion. The transformer predicted negative (one star, confidence 0.7329). This is another example of the model treating negative subject matter as negative sentiment.

3. **Clear frustration labeled positive.** Post ID 251 describes the author's “ergernis” (annoyance) at people making phone calls on speakerphone in a quiet carriage. I labeled it negative, but the transformer predicted positive (five stars, confidence 0.4286). This is a more serious valence error because the text explicitly conveys frustration.

4. **Mild disappointment treated as neutral.** Post ID 164 says “Beetje jammer” (“a bit of a shame”) about a train not running a longer desired route. I labeled it negative, but the transformer predicted neutral. This suggests it can miss understated or colloquial negative sentiment in Dutch.

## Choice and limitations

For this 50-post evaluation, the word-list baseline is the better of the two by overall agreement (88% versus 14%) and is much better at recognizing neutral factual notices. I would use it as the provisional comparison baseline for the hackathon demonstration, while clearly documenting its limitation: it identified only 1 of the 7 negative posts. If the main goal is to alert railway communications staff to passenger complaints, neither system should be treated as reliable without improvement.

A practical next improvement is to separate **service-incident detection** from **expressed passenger sentiment**. A factual alert such as “Storing voorbij” could be tagged as a railway incident while remaining neutral for sentiment. Explicit complaints or emotional language could then be assessed separately. This is a proposed improvement, not a result validated by this 50-post test.

## Conclusion

The evaluation demonstrates why overall agreement alone is not enough. The transformer over-classifies factual disruption announcements as negative, while the word-list baseline often misses negative complaints. The sample is small and imbalanced, so these figures should be reported as preliminary rather than generalized to all railway passengers. The dashboard should make clear that labels are model predictions, not verified public opinion.
