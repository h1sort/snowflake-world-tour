# Status: Snowflake World Tour CDMX talk (Tue 13 Oct 2026, 11:00 CST, 15 min)

_Last updated: Mon 12 Oct 2026, 12:20 ET. Read this first when resuming._

## Done
- **Deck (PowerPoint, official SWT26 template):** 13 slides + Spanish speaker notes, reviewed by an independent agent, all fixes applied. Source: `deck/src/` (unpacked pptx). Build: `deck/tools/pack.sh [OUT_DIR]` (pack + validate + render). Spec: `deck/BRIEF.md`.
  - Every Snowflake feature named on slide 5 is GA (verified on docs.snowflake.com 12 Oct 2026): Semantic Views, Cortex Agents, Cortex Analyst, AI_COMPLETE.
- **Anatomy figure** (`assets/anatomy/`): interactive `machine.html` (published privately as the artifact "Contexto Juicio Acción"), slide renders `machine-slide.png` (pass) and `machine-slide-reject.png`.
  - **On slide 7** (approved): figure + five labels; the native diagram stays in the slide as a hidden backup group `machine-fallback`.
- **Demo contract:** `demo/CONTRACT.md` (object names, definitions, Act rules). Authoritative.
- **Bridge D1 → Snowflake** (`demo/bridge/bridge.py`): done, 16 offline tests pass, `--mock` / `--once` / `--counts`. Reads D1 through Carlos's existing `npx wrangler` login. Hashes browser ids with a salt before upload.

## In progress (agents were running at 12:10 ET)
- Nothing running. All three demo pieces are written and committed; none has run against real Snowflake or h1sort.com yet.
- **Snowflake objects** (`demo/snowflake/00_setup.sql` … `05_reset.sql`, README, rest_examples.md): written from current docs, not executed. Unverified bits + plan B are in its README.
- **Harness** (`demo/harness/stage.py`): 49 tests pass; mock flow verified (refusal prints "RECHAZADA · sin efecto", no network call).
- **Bridge** (`demo/bridge/bridge.py`): 16 tests pass; uses `SNOWFLAKE_PAT_LOADER`.
- Contract amendments (two PATs, numerator requires ROL, model claude-sonnet-5) are at the bottom of `demo/CONTRACT.md`.

## Carlos's to-dos (only he can do these)
1. **Create the poll group** at h1sort.com/polls with the 3 questions EXACTLY as in `demo/CONTRACT.md` → send the group code.
2. **Snowflake:** `SELECT CURRENT_REGION()`; run `demo/snowflake/00_setup.sql` → `03_agent.sql` (ACCOUNTADMIN for 00); create TWO PATs (agent + loader, see README); **check the network policy allows the venue IP** (top risk); run `04_checks.sql`.
3. **Laptop:** `cp demo/.env.example demo/.env`, fill it; `npx wrangler login`; `uv run demo/bridge/bridge.py --mock`, then `--once` for real.
4. **Decided:** `h1sort.com/snowflake` serves the slides from the start. Page built and committed LOCALLY on h1sort-website branch `feat/snowflake-world-tour` (commit 7d357ea: `src/pages/snowflake.astro`, `public/snowflake/{diapositivas.pdf,maquina/,maquina.webp}`, llms.txt). Build passes; desktop + 390 px checked. NOT pushed: any push deploys production. Push when Carlos says, then open PR and merge.

## Still to build after the to-dos
- h1sort-website PR: `/swt` → `/p/<GROUP_CODE>` redirect, `/snowflake` → slides PDF (needs decisions 1 and 4).
- End-to-end rehearsal against real Snowflake; record the full demo as the labeled fallback video and embed it in the deck (notes already reference "(grabación)").
- Final deck export (pptx + PDF) and a phone test of both QR codes.
- After the talk: HTML version of the deck with animations + the interactive Anatomy figure on h1sort.com.

## Slide 7 swap recipe (if approved)
Replace the `machine-fallback` group in `deck/src/ppt/slides/slide11.xml` with a picture of `assets/anatomy/machine-slide.png` at x=2.0 in, y=3.3 in, w=16 in (keep aspect), plus five pill labels (Ask · definición aprobada / Judge · evidencia 4/4 / Act · app + humano / Recibo / ✕ rechazada · sin efecto). A working version was built at `/tmp/swt-v7/` (not persistent); the generator logic is simple to redo.

## Key decisions (do not relitigate without Carlos)
- PowerPoint from the Snowflake template first; HTML with animations later.
- One continuous demo: Ask → Judge → Act; Act closes the poll and results appear on phones.
- Judge verdict values `pasa | revisar | rechazar`; "permiso" = P3 "Sí" or "Sí, con aprobación humana"; missing ≠ "No".
- Santander facts on stage: only "Sr. AI Engineer en Banco Santander" and "casi 10 años lidiando con datos". Banking examples labeled "Ilustrativo".
- No Snowpipe Streaming claim; the loader is "loader incremental, micro-lotes cada ~3 s".
- Conversation in English; deliverables in Spanish.
