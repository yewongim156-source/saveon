# Save:On Evaluation Pilot v1

This directory contains the first evidence-aware evaluation set for the
short-form analysis pipeline.

## Files

- `pilot_sources.json`: reproducible source selection and reasons
- `pilot_v1.json`: ten provisional annotations requiring full-video review
- `evaluation_item.schema.json`: machine-readable dataset contract
- `annotation_guidelines.md`: annotation and summary scoring rules
- `metrics.md`: automatic and human metrics plus initial gates
- `collect_evidence.py`: local STT/OCR/frame evidence collector
- `validate_dataset.py`: dependency-free structural and timestamp validator
- `examples/`: five fictional examples of target facts, ordering and evidence

The repository stores URLs and annotations, not copied videos. Temporary frame
and transcript evidence is written to `.runtime/evaluation-evidence`, which is
excluded from Git.

## Validate

From the repository root:

```powershell
.\ai\.venv\Scripts\python.exe evaluation\validate_dataset.py
```

The validator checks core fields and selected cross-field constraints; it is not
a full JSON Schema validator. New target and sequence fields are optional for
backward compatibility and are not yet populated in the ten pilot items.

`evaluationStatus: EXCLUDED` marks an item excluded from scoring, while retaining
its history. Missing `evaluationStatus` means active. Any future scoring runner
must filter excluded items. The validator checks the file, including excluded
items; it does not itself run an evaluation.

## Rebuild temporary evidence

```powershell
.\ai\.venv\Scripts\python.exe evaluation\collect_evidence.py --frames 8
```

Use `--id pilot-003` to collect one item. The command downloads a public video
into a temporary directory, extracts timestamped evidence, and deletes the
media when that item finishes.

## Important limitation

All ten items are `DRAFT`: they were prepared using machine transcripts, OCR,
and sampled frames, not a complete human viewing. A team member must watch
each full source and resolve the notes, and a second reviewer must adjudicate
disagreements before final model scores are reported. In particular, recipe quantities, exercise advice,
historical claims, and time-sensitive product promotions need domain-aware
second review.
