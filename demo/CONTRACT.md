# Demo contract (authoritative; all three demo workstreams build against this)

Runs on Carlos's laptop (macOS, Python 3.11+ via `uv`, `npx wrangler` already logged in to Cloudflare). Nothing here may require secrets in the repo. All config comes from env vars, documented in `demo/.env.example`.

## Flow
```
phones → h1sort.com/p/<GROUP_CODE> → D1 (h1sort-chat)
  → bridge (every ~3 s) → Snowflake SWT_DEMO.RAW.*
  → SWT_DEMO.SEM.RESPUESTAS (view, one row per browser) → semantic view SWT_DEMO.SEM.ENCUESTA_SWT
  → ASK:   Cortex Agent SWT_DEMO.SEM.AGENTE_ENCUESTA (Cortex Analyst tool on the semantic view)
  → JUDGE: deterministic invariants (Python) + AI_COMPLETE typed verdict  pasa | revisar | rechazar
  → ACT:   AI_COMPLETE proposes {accion, objetivo, motivo}; the app validates; human y/N; PATCH h1sort.com closes the group
```

## Source: D1 (`h1sort-chat`, read via `npx wrangler d1 execute h1sort-chat --remote --json --command "<sql>"` run with cwd = `$H1SORT_SITE`)
Tables (SQLite): `poll_groups(id TEXT pk uuid, code TEXT unique 10 chars, title, created_at)`, `polls(id, group_id, code, question, status draft|open|closed, created_at, updated_at, opened_at, closed_at)`, `poll_options(id, poll_id, label, position 0-7)`, `poll_votes(id TEXT pk, poll_id, option_id, voter_hash TEXT 43 chars, created_at 'YYYY-MM-DD HH:MM:SS' UTC)`. Unique (poll_id, voter_hash): one vote per browser per question.
The bridge reads ONLY these four tables, ONLY rows of the group `GROUP_CODE`. Never `messages`, `conversations`, `poll_auth_attempts`.
Question order inside a group = `polls.created_at ASC, polls.id ASC` → P1, P2, P3.

## Snowflake objects (names are fixed)
- Database `SWT_DEMO`; schemas `RAW`, `SEM`; warehouse `SWT_WH` (XSMALL, auto-suspend 60).
- Roles: `SWT_LOADER` (USAGE + INSERT/UPDATE/MERGE on RAW tables), `SWT_AGENT_RO` (USAGE on SWT_WH, SELECT on SEM objects only, USAGE on the agent, CORTEX_USER database role). The harness runs as `SWT_AGENT_RO`. "Rol de solo lectura" on the slide is literally this role.
- `RAW.POLL_GROUPS(ID, CODE, TITLE, CREATED_AT TIMESTAMP_NTZ, _LOADED_AT)`
- `RAW.POLLS(ID, GROUP_ID, CODE, QUESTION, STATUS, CREATED_AT, OPENED_AT, CLOSED_AT, ORDINAL NUMBER, _LOADED_AT)`: ORDINAL 1..n computed by the bridge from the order rule above.
- `RAW.POLL_OPTIONS(ID, POLL_ID, LABEL, POSITION, _LOADED_AT)`
- `RAW.POLL_VOTES(ID, POLL_ID, OPTION_ID, VOTER_KEY, CREATED_AT TIMESTAMP_NTZ, _LOADED_AT)`: `VOTER_KEY = sha256(VOTER_SALT + voter_hash)` hex, computed in the bridge. The raw `voter_hash` never leaves the laptop.
- All loads are idempotent `MERGE ... ON ID`.
- `SEM.RESPUESTAS` (view): one row per VOTER_KEY in the configured group, columns `VOTER_KEY, ROL, USO_IA_7D, PERMISO_PRODUCCION, PRIMERA_RESPUESTA_AT`, each answer NULL when that browser didn't answer that question (P1→ROL, P2→USO_IA_7D, P3→PERMISO_PRODUCCION, by ORDINAL; values are the option labels verbatim).
- `SEM.ENCUESTA_SWT` (semantic view over SEM.RESPUESTAS). Must encode:
  - dimension `rol`; facts/dimensions for the three answers;
  - metric `navegadores_con_rol_y_p3` = count where ROL and PERMISO_PRODUCCION are not null (the denominator);
  - metric `con_permiso` = count where PERMISO_PRODUCCION in ('Sí', 'Sí, con aprobación humana');
  - metric `pct_permiso` = con_permiso / navegadores_con_rol_y_p3;
  - descriptions/synonyms in Spanish stating: a missing answer is NOT a "No"; a row is a browser, not a person; never expose VOTER_KEY.
- `SEM.AGENTE_ENCUESTA` (Cortex Agent): one tool, Cortex Analyst over `SEM.ENCUESTA_SWT`; orchestration model: a Claude model available in the account's region (fallback documented); instructions in Spanish: answer with numerators, denominators, cutoff, the SQL used; say "muestra insuficiente" for groups with n < 5; never invent.

## Exact poll content (the group Carlos creates)
1. `¿Cuál describe mejor tu rol?` · `Negocio` / `Ingeniería` / `Datos y analítica` / `Liderazgo` / `Otro`
2. `En los últimos 7 días, ¿usaste IA para trabajar con datos?` · `Sí` / `No`
3. `¿Le darías a un agente permiso de actuar en producción?` · `Sí` / `Sí, con aprobación humana` / `No`

## Harness contract
- Ask question (default, overridable): `Por rol, ¿qué porcentaje le daría a un agente permiso de actuar en producción? Solo cuenta a quien respondió rol y P3.`
- Judge output JSON (validated in code): `{"veredicto": "pasa"|"revisar"|"rechazar", "evidencia": [str], "motivo": str}`. Deterministic invariants run first and can only downgrade: denominators present and equal to valid pairs (recomputed by the harness with its own SQL on SEM.RESPUESTAS); every group with n < 5 marked "muestra insuficiente"; no VOTER_KEY or 43-char/64-hex tokens in the answer; cutoff timestamp present.
- Act allowlist: exactly one tool, `cerrar_encuesta(codigo_grupo)`. Validation: tool in allowlist · `codigo_grupo == GROUP_CODE` · last Judge verdict == `pasa` · group currently open. Then a human `y/N` prompt, then `PATCH https://h1sort.com/api/polls/admin/groups/<group_id>` `{"status":"closed"}` with an admin session from `POST /api/polls/auth/login` `{"username","password"}` (send `Origin: https://h1sort.com`; keep the cookie). Receipt = HTTP status + `updated` count + timestamp, printed and appended to `demo/receipts.jsonl`.
- Anything else the model proposes (e.g. `borrar_votos`) → `RECHAZADA · sin efecto`, with the reason, and no network call.
- Stage output style: like GBM `demo/agent.py`: colored stage labels `SOLICITUD › VALIDACIÓN › EJECUCIÓN › OBSERVACIÓN`, `RECHAZADA` in orange/red, large readable text, Spanish.
- Every component has `--mock` (no network: canned fixtures in `demo/fixtures/`) used for rehearsal and as the last-resort fallback, and is clearly labeled `[MODO ENSAYO]` on screen when mocked.

## Amendments (from the Snowflake build, 12 Oct; these win over the text above)
- `con_permiso` also requires `ROL IS NOT NULL` (else the % can exceed 100). Harness recompute already uses `ROL IS NOT NULL AND PERMISO_PRODUCCION IS NOT NULL`.
- Two PATs on service user `SWT_DEMO_USER`, one role each: `SNOWFLAKE_PAT` (SWT_AGENT_RO, harness) and `SNOWFLAKE_PAT_LOADER` (SWT_LOADER, bridge).
- `SEM.RESPUESTAS` has a sixth column `ULTIMA_RESPUESTA_AT` (data cutoff). The view reads the most recently created group in RAW: run `05_reset.sql` after rehearsing with another group.
- Extra role `SWT_OWNER` owns the objects. `SWT_LOADER` cannot create temp tables: MERGE uses `USING (SELECT … FROM VALUES …)` (bridge already does).
- Cortex model: `claude-sonnet-5` (GA), fallback `claude-sonnet-4-5`; Claude runs via cross-region inference; check `CORTEX_ENABLED_CROSS_REGION` and `SELECT CURRENT_REGION()`.

## Env vars (`demo/.env.example`)
`GROUP_CODE`, `H1SORT_SITE` (path to the h1sort-website checkout), `VOTER_SALT`, `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PAT` (programmatic access token; key-pair optional), `SNOWFLAKE_ROLE_LOADER=SWT_LOADER`, `SNOWFLAKE_ROLE_AGENT=SWT_AGENT_RO`, `SNOWFLAKE_WAREHOUSE=SWT_WH`, `CORTEX_MODEL` (default a Claude model id), `POLLS_ADMIN_USERNAME`, `POLLS_ADMIN_PASSWORD`, `H1SORT_BASE=https://h1sort.com`.
