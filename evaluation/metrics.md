# Save:On Evaluation Metrics v1

## Automatic metrics

- Primary category: accuracy and Macro F1
- Content type: accuracy and Macro F1
- Entities: micro/macro precision, recall, and F1 after whitespace/case
  normalization
- Claim selection: precision and recall for verifiable claims
- Verification: verdict accuracy and false-supported rate
- Actions: exact-set precision, recall, and F1
- Target recall and precision: matched expected vs extracted targets
- Target-to-fact assignment precision/recall: facts attached to the correct target
- Step coverage and ordering: recall of required steps and pairwise order
  accuracy among matched steps; evaluate optional steps separately
- Runtime: end-to-end p50/p95 latency and per-step latency
- Cost: Gemini request count and estimated cost per item

## Human or calibrated judge metrics

- Required-fact precision and recall
- Unsupported claim rate
- Irrelevant-input inclusion rate
- Five-part summary rubric from `annotation_guidelines.md`
- Citation precision: whether each cited page supports the associated claim

## Pilot acceptance targets

These are initial engineering gates, not claims about production quality.

- Primary-category Macro F1 >= 0.80
- Required-fact recall >= 0.80
- Unsupported claim rate <= 0.05
- Irrelevant-input inclusion rate <= 0.10
- Entity F1 >= 0.80
- False-supported rate for fact checking = 0 on the pilot
- p95 end-to-end latency <= 60 seconds on the reference local environment

Scores must always include the model name, prompt version, configuration,
dataset commit, and number of adjudicated items.

These target/step metrics are planned definitions, not implemented automated
scorers. Do not score a missing optional target/step field as an empty label.
