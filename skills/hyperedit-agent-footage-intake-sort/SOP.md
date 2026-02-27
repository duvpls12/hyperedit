# SOP - Footage Intake and Sorting

## Objective

Convert raw media into a ranked, sequence ready shot pool with minimal assembly friction.

## Inputs

- Raw clips and metadata.
- Project format target (`mls`, `reel`, `highlight`, `ai_lot`).
- Property profile (style, price bracket, key selling points).

## Procedure

1. Ingest all clips and normalize metadata.
2. Tag each clip by shot class:
- `wide_push`, `wide_orbit`, `detail_slider`, `drone_establishing`, `transition_shot`, `talking_head`.
3. Tag room/zone and sequence block (exterior, kitchen, living, bed, bath, amenities).
4. Tag directional movement (`left`, `right`, `forward`, `backward`, `straight_reset`, `orbit`).
5. Score each clip:
- Technical quality (stability, exposure, focus).
- Narrative value (hook, reveal, connector, payoff).
- Continuity utility (movement match, room handoff fit).
6. Create shortlist bins for each sequence block.
7. Detect gaps per required sequence plan.
8. Apply fallback ladder for gaps:
- Borrow from adjacent sequence block.
- Reuse alternative take.
- Speed adjust existing clip if plausible.
- Generate synthetic detail only if still blocked.
9. Write outputs and include assumptions/open questions.

## Quality gates

- No sequence block lacks both wide and detail options unless explicitly documented.
- Direction tags exist for all shortlisted clips.
- At least one viable hook candidate and one payoff candidate are identified.
- Gaps are labeled as `blocking` or `non_blocking`.

## Outputs

- `10_footage_catalog.json` full tagged inventory.
- `11_selects_shortlist.json` ranked per sequence.
- `12_gap_report.json` with fallback recommendations.
