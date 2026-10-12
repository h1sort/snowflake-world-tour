# Plan: Snowflake World Tour CDMX 2026

15-minute talk, Tue 13 Oct 2026 11:00 CST. Content brief: `deck/BRIEF.md`.

## Phase 1: deck (PowerPoint from the official SWT26 template)
- `deck/template/`: Snowflake's speaker template (source, never edited).
- `deck/src/`: the unpacked deck we edit (13 slides, see the ownership table in BRIEF.md).
- `deck/tools/pack.sh [OUT]`: pack, validate against the template, render PNGs.
- `assets/anatomy/`: isometric "machine" figure (Ask → Judge → Act) built with the Anatomy skill; its PNG may replace the native-shape fallback on slide 7.

## Phase 2: live demo (after the deck)
- `demo/bridge/`: D1 → Snowflake loader, micro-batches every ~3 s into RAW tables.
- `demo/snowflake/`: DDL, Semantic View, Cortex Agent definition, read-only role.
- `demo/harness/`: Ask (Cortex Agent) → Judge (code invariants + AI_COMPLETE typed verdict) → Act (validated close of the poll group via h1sort.com API, human approval).
- Fallback: a labeled recording of the full rehearsal, embedded in the deck.

## Phase 3: publish
- h1sort.com/swt → poll group redirect; h1sort.com/snowflake → slides (PDF first, HTML with animations after the talk).
