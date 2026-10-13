# Status: Snowflake World Tour CDMX talk (Tue 13 Oct 2026, 11:00 CST, 15 min)

_Last updated: Tue 13 Oct 2026, 05:50 CST. Read this first when resuming._

## The pivot (13 Oct, 03:36 CST, decided by Carlos)
- **Live demo CUT** (not enough time to test). **Poll dropped.**
- Talk rebuilt with the onion method around ONE core and ONE package:
  **Confianza = Contexto × Evidencia × Control** (if one factor is zero, trust is zero). One question per factor: ¿con qué definición respondió? · ¿qué evidencia lo respalda? · ¿quién puede detenerlo?
- Opens with the **tapping game** (*Las Mañanitas*; Newton, Stanford 1990: 50% predicted vs 2.5% actual).
- Santander framing: **"así pensamos estas decisiones"** only; never claim what Santander runs in production.
- Spec: `deck/BRIEF-v2.md` (overrides the slide-by-slide part of `deck/BRIEF.md`; hard rules in BRIEF.md still apply).

## Deck state: FINAL (05:50 CST)
- 14 slides, Spanish notes on every slide (except Safe Harbor), independent review done and all fixes applied, package validates.
- Exports (gitignored, regenerate with pack.sh): `deck/out/SWT26 CDMX - Carlos Haro - Confianza.pptx` and `.pdf` (PDF has no notes).
- h1sort.com/snowflake updated with the final PDF and new page copy (branch push d9357cd).
- Build: `deck/tools/pack.sh [OUT_DIR]`.

## Website
- `h1sort.com/snowflake` is LIVE (branch `feat/snowflake-world-tour` on h1sort-website; every branch push deploys production). Carlos still needs to open + merge the PR: https://github.com/h1sort/h1sort-website/pull/new/feat/snowflake-world-tour
- After the deck is final: replace `public/snowflake/diapositivas.pdf` on that branch, build, push.
- No `/swt` redirect needed anymore (poll dropped).

## Parked (not used in the talk)
- `demo/` (bridge, Snowflake SQL, harness, contract): built and unit-tested, never run live. Keep for a future talk or the HTML version.
- `assets/anatomy/`: the machine figure; used on slide 10 and at h1sort.com/snowflake/maquina/.

## Key decisions (do not relitigate without Carlos)
- PowerPoint from the Snowflake template first; HTML with animations after the talk.
- No live demo, no poll. Optional, never required: show h1sort.com/snowflake/maquina and remove a pin.
- Santander facts on stage: only "Sr. AI Engineer en Banco Santander" and "casi 10 años lidiando con datos". Banking examples labeled "Ilustrativo".
- All Snowflake features named on slides are GA (verified 12 Oct 2026).
- Conversation in English; deliverables in Spanish.
