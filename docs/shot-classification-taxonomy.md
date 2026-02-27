# HyperEdit Shot Classification Taxonomy

## Overview

This document defines the canonical shot classification labels used across the HyperEdit pipeline. All `classify_shot` MCP tool calls, `bins/` symlink paths, and `10_footage_catalog.json` artifacts must use these exact strings.

---

## Primary Tags

Primary tags determine the `bins/{type}/` sort destination.

```
PRIMARY TAGS:
├── wide
│   ├── establishing
│   ├── low-angle
│   ├── high-angle
│   └── eye-level
├── tight
│   ├── close-up
│   └── medium-close-up
├── detail
│   ├── hardware
│   ├── fixture
│   ├── texture
│   ├── architectural
│   └── landscape
├── drone
│   ├── aerial-wide
│   ├── aerial-orbit
│   ├── aerial-reveal
│   └── aerial-tracking
└── agent-on-camera
    ├── talking-head
    ├── walk-through
    └── stand-up
```

---

## Secondary Tags

Secondary tags are stored in the catalog but do **not** affect bin sorting.

```
SECONDARY TAGS:
├── perspective
│   ├── interior
│   └── exterior
├── room
│   ├── kitchen
│   ├── bathroom
│   ├── bedroom
│   ├── living
│   ├── dining
│   ├── office
│   ├── garage
│   ├── pool
│   └── yard
└── lighting
    ├── natural
    ├── artificial
    ├── mixed
    └── golden-hour
```

---

## Full Tag Reference Table

| Primary | Sub-classification | Bin Path | Notes |
|---------|--------------------|----------|-------|
| `wide` | `establishing` | `bins/wide/` | Opening or closing property reveal |
| `wide` | `low-angle` | `bins/wide/` | Camera below waist height |
| `wide` | `high-angle` | `bins/wide/` | Camera above head height, not drone |
| `wide` | `eye-level` | `bins/wide/` | Standard horizontal perspective |
| `tight` | `close-up` | `bins/tight/` | Subject fills most of frame |
| `tight` | `medium-close-up` | `bins/tight/` | Subject from chest/shoulders up |
| `detail` | `hardware` | `bins/detail/` | Door handles, faucets, fixtures |
| `detail` | `fixture` | `bins/detail/` | Light fixtures, appliances |
| `detail` | `texture` | `bins/detail/` | Materials: stone, wood, fabric |
| `detail` | `architectural` | `bins/detail/` | Arches, columns, structural features |
| `detail` | `landscape` | `bins/detail/` | Plants, water features, hardscape |
| `drone` | `aerial-wide` | `bins/drone/` | High altitude, full property visible |
| `drone` | `aerial-orbit` | `bins/drone/` | Circular/orbital path around subject |
| `drone` | `aerial-reveal` | `bins/drone/` | Fly-in or pull-back reveal |
| `drone` | `aerial-tracking` | `bins/drone/` | Forward dolly/push along axis |
| `agent-on-camera` | `talking-head` | `bins/agent-on-camera/` | Agent speaking directly to camera |
| `agent-on-camera` | `walk-through` | `bins/agent-on-camera/` | Agent walking through property |
| `agent-on-camera` | `stand-up` | `bins/agent-on-camera/` | Agent stationary, framed mid-shot |

---

## Classification Rules for the Cowork Auto-Sort Task

### Visual Analysis Guidelines

1. **Drone vs. wide**: If metadata shows DJI/Autel/Skydio maker tag OR altitude > 5m → `drone`. Otherwise use perspective/composition.
2. **Detail detection**: If subject occupies > 60% of frame width and is a non-human object → `detail`.
3. **Agent-on-camera**: Any frame containing a clearly visible human face in focus → `agent-on-camera`. Sub-type determined by camera motion and framing.
4. **Ambiguous clips**: Default to the broader primary category (e.g., prefer `wide/establishing` over `tight/medium-close-up` when uncertain).

### Stills (Photos)

Still images receive the same primary + sub-classification as video clips AND are always added to `bins/photos/` in addition to their primary bin.

### Confidence Threshold

If visual analysis confidence is below 0.65, tag the clip as `wide/establishing` (safe fallback) and add a note to `open_questions` in the run-ledger.

---

## JSON Representation

In `10_footage_catalog.json`, each clip entry uses this structure:

```json
{
  "filename": "DJI_0042.MP4",
  "primary_tag": "drone",
  "sub_tag": "aerial-orbit",
  "secondary_tags": {
    "perspective": "exterior",
    "lighting": "golden-hour"
  },
  "confidence": 0.91,
  "bin_path": "bins/drone/DJI_0042.MP4",
  "graded_path": "graded/DJI_0042_graded.MP4",
  "camera_model": "DJI Mavic 3 Pro",
  "color_profile": "D-Log M",
  "lut_applied": "DJI_Mavic3Pro_DLogM_to_Rec709.cube"
}
```

---

## Bin Directory Mapping

```
bins/
├── wide/
├── tight/
├── detail/
├── drone/
├── agent-on-camera/
└── photos/              ← stills only (in addition to primary bin)
```

All entries in `bins/` are **symlinks** pointing back to the original file in `footage/`. The originals are never moved or copied.
