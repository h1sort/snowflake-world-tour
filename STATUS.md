# Status: Snowflake World Tour CDMX talk (Tue 13 Oct 2026, 11:00 CST, 15 min)

_Last updated: Mon 12 Oct 2026, 12:10 ET. Read this first when resuming._

## Done
- **Deck (PowerPoint, official SWT26 template):** 13 slides + Spanish speaker notes, reviewed by an independent agent, all fixes applied. Source: `deck/src/` (unpacked pptx). Build: `deck/tools/pack.sh [OUT_DIR]` (pack + validate + render). Spec: `deck/BRIEF.md`.
  - Every Snowflake feature named on slide 5 is GA (verified on docs.snowflake.com 12 Oct 2026): Semantic Views, Cortex Agents, Cortex Analyst, AI_COMPLETE.
- **Anatomy figure** (`assets/anatomy/`): interactive `machine.html` (published privately as the artifact "Contexto Juicio Acción"), slide renders `machine-slide.png` (pass) and `machine-slide-reject.png`.
  - **Pending decision (Carlos):** swap it into slide 7 with labels (preview at `deck/out/slide7-anatomy-option.png`, recipe below). Current slide 7 = native-shape diagram.
- **Demo contract:** `demo/CONTRACT.md` (object names, definitions, Act rules). Authoritative.
- **Bridge D1 → Snowflake** (`demo/bridge/bridge.py`): done, 16 offline tests pass, `--mock` / `--once` / `--counts`. Reads D1 through Carlos's existing `npx wrangler` login. Hashes browser ids with a salt before upload.

## In progress (agents were running at 12:10 ET)
- **Snowflake objects** (`demo/snowflake/00_setup.sql` … `05_reset.sql`, README, rest_examples): files written, agent finishing README/verification.
- **Ask/Judge/Act harness** (`demo/harness/stage.py` + tests): main file written, agent finishing tests/README.
- If a session resumes and these agents are gone: check `git log`, run the tests (`uv run --with pytest ... pytest demo/`), read the READMEs; finish whatever is missing against `demo/CONTRACT.md`.

## Carlos's to-dos (only he can do these)
1. **Create the poll group** at h1sort.com/polls with the 3 questions EXACTLY as in `demo/CONTRACT.md` → send the group code.
2. **Snowflake:** run `demo/snowflake/00_setup.sql` → `03_agent.sql` in a worksheet (ACCOUNTADMIN for 00); create a PAT; **check the network policy allows the venue IP** (top risk); run `04_checks.sql`.
3. **Laptop:** `cp demo/.env.example demo/.env`, fill it; `npx wrangler login`; `uv run demo/bridge/bridge.py --mock`, then `--once` for real.
4. **Decide:** does `h1sort.com/snowflake` (QR on last slide) serve the slides PDF from the start of the talk, or only after? Any push to h1sort-website deploys production immediately, so that PR waits for his go.
5. **Decide:** Anatomy figure on slide 7, yes/no.

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
