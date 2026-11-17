# Save:On Pilot Annotation Guidelines v1

## Goal

The pilot measures whether Save:On communicates the useful content of a short
video without adding unsupported or irrelevant information. It is not a
captioning benchmark and the reference summary is not the only acceptable
wording.

## Evidence priority

Annotators inspect the video and the temporary evidence bundle in this order:

1. spoken content with timestamps;
2. meaningful on-screen text with frame timestamps;
3. visible actions, objects, and places;
4. source title and description only as supporting metadata.

Metadata must be labelled as irrelevant when it conflicts with the actual
video. OCR fragments, watermarks, channel UI, and recognition mistakes are not
gold facts.

## Required and optional facts

- `requiredFacts`: omitting the fact makes the result misleading or removes the
  video's main utility.
- `optionalFacts`: correct and potentially useful, but not required for a good
  short summary.
- A fact must point to at least one timestamped evidence unit.
- Preserve uncertainty. A video making a claim is different from the claim
  being true.

## Irrelevant information

Add an `irrelevantInputs` item when a title, description, OCR fragment, STT
error, or coarse visual label could plausibly contaminate the result. The
evaluation counts a model output as noisy when it repeats such information as
part of the final summary.

## Entities

Record only named or uniquely identifiable places, products, brands, people,
services, events, and dates. Generic words such as `water`, `phone`, `cafe`, or
`exercise` are not entities.

## Claims and verification

Record at most three externally verifiable claims per item. `expectedVerdict`
is a gold verification label only when a reviewer checked authoritative
evidence. Otherwise use `NOT_ASSESSED`; do not guess.

## Targets, steps, and external evidence

- `targets` groups facts under the correct product, place, recipe, exercise,
  tool, or skill. Use a stable ID within each video; do not move attributes
  between targets. Existing top-level facts remain valid for whole-video facts.
- Use `globalSteps` for one video-wide sequence and `targets[].steps` for a
  sequence belonging to one target. Order starts at 1 and is consecutive within
  each sequence. Mark optional steps `required: false` and record conditions.
- Each fact and step links to video evidence and a timestamp or an explanatory
  metadata note. A sampled frame is not proof that all intervening steps were
  observed; review the full video.
- `externalExpectations` states what should be checked or added. Keep
  `NOT_REVIEWED` and an empty `sources` list until verification. `REVIEWED`
  requires an actual source, title, access date, and an explanation of what it
  supports. Record a validity date for changing facts such as price or hours.
  Absence of an external source must not be interpreted as a negative verdict.
- The existing ten items have not been migrated to target structures; add them
  during human review. Missing new optional fields mean not annotated, not that
  the video has no targets or steps.

## Summary rubric

Each model summary receives 0, 1, or 2 points on five dimensions:

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Faithfulness | Unsupported central information | Minor unsupported detail | Every material statement is supported |
| Completeness | Most required facts missing | Some required facts included | All required facts included |
| Relevance | Mostly noise | Some unnecessary detail | Only decision-useful information |
| Non-redundancy | Repetitive | Minor repetition | No meaningful repetition |
| Actionability | Wrong or unsafe action | Vague but usable | Correct next action or correctly no action |

`referenceSummary` represents one acceptable answer. Scoring is based on facts
and evidence, not exact sentence overlap.

## Dataset maturity

- `DRAFT`: evidence collected but labels not fully reviewed.
- `SINGLE_REVIEWED`: one reviewer checked the video and labels.
- `ADJUDICATED`: two reviewers resolved disagreements. Only adjudicated items
  should be used for final reported model scores.

The current pilot was drafted from machine-extracted transcripts and sampled
frames; full-video human review has not been completed. All items remain
`DRAFT` until a person watches the complete source and checks each label.
Two independent reviewers must resolve disagreements before final scoring.
