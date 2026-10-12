# Puente D1 → Snowflake

Copies the live votes of ONE poll group from Cloudflare D1 (`h1sort-chat`) into `SWT_DEMO.RAW.*` every ~3 s, so the audience votes on their phones and the agent queries Snowflake seconds later.

```
phones → h1sort.com/p/<GROUP_CODE> → D1 → bridge.py → SWT_DEMO.RAW.{POLL_GROUPS,POLLS,POLL_OPTIONS,POLL_VOTES}
```

## Run

```bash
cp demo/.env.example demo/.env      # fill GROUP_CODE, H1SORT_SITE, VOTER_SALT, SNOWFLAKE_*
uv run demo/bridge/bridge.py        # the live loop (Ctrl-C to stop)
```

| Flag | What it does |
|---|---|
| (none) | Loop every `BRIDGE_INTERVAL` s (default 3). Dimensions (group, polls, options) re-sync every 30 s. |
| `--once` | One full sync, prints the batch line and the counts, exits (exit code 1 if counts differ). |
| `--counts` | Only prints `D1 X · Snowflake Y` and whether they match. No writes. |
| `--mock` | No network at all. Fixtures in `demo/fixtures/d1_*.json` stand in for D1 (the real SQL runs on an in-memory SQLite) and `demo/bridge/mock_snowflake.sqlite` stands in for Snowflake. Everything is labeled `[MODO ENSAYO]`. Votes drip in at a few per second so you can rehearse the screen. Combine with `--once` / `--counts`. |
| `--interval N` | Override the loop period in seconds. |
| `--env PATH` | Use another env file (default `demo/.env`). |

Tests (offline): `uv run --with pytest --with python-dotenv --with rich pytest demo/bridge/test_bridge.py`

## What it does and does not do

- Reads ONLY `poll_groups`, `polls`, `poll_options`, `poll_votes`, ONLY rows of `GROUP_CODE`. Read-only SQL; never `messages`, `conversations` or `poll_auth_attempts`.
- `ORDINAL` (1..n) is computed from `(created_at, id)`: P1 role, P2 AI use, P3 production permission.
- `VOTER_KEY = sha256(VOTER_SALT + voter_hash)` (hex) is computed the moment the row arrives. The raw `voter_hash` is never printed, logged or sent to Snowflake. Error messages are scrubbed of 43-char / 64-hex tokens and of the PAT.
- Votes are fetched with `created_at >= watermark - 5 s` and loaded with `MERGE ... ON ID`, so the overlap and restarts never duplicate. The watermark only advances after the MERGE succeeded, so a failed batch is retried automatically.
- Starting it twice, or restarting mid-talk, is safe (idempotent).

## What to show on stage

One line per batch:

```
12:02:15 +4 votos · total D1 16 · total Snowflake 16 · latencia ~1.3 s ✓
```

- `+N votos`: new votes loaded in this cycle.
- `total D1` vs `total Snowflake`: the two counts must match. The green `✓` means they do; a yellow `≠` means Snowflake is behind (normally for one cycle).
- `latencia`: now minus the newest vote's `created_at` in that batch (about 1 to 4 s with real wrangler).
- Between batches the spinner line keeps showing the current counts.
- Optional proof in a second terminal: `uv run demo/bridge/bridge.py --counts`.

## Snowflake login (PAT)

`SNOWFLAKE_PAT_AUTH=auto` (default) first sends the token as `password=` (the documented way,
<https://docs.snowflake.com/en/user-guide/programmatic-access-tokens>), and if that login fails it retries with `authenticator="PROGRAMMATIC_ACCESS_TOKEN", token=<PAT>` (supported by recent `snowflake-connector-python`). Force one with `password` or `token`. The PAT's user needs the `SWT_LOADER` role (role restriction on the token if it is a service user) and, by default, a network policy that allows the laptop's IP.

## Failure modes (it never exits on its own after start)

| Symptom on screen | Cause | What happens / what to do |
|---|---|---|
| `✗ wrangler no respondio en 20 s` | Slow venue wifi or Cloudflare | Call is killed, retried next cycle. The watermark did not move, nothing is lost. |
| `✗ wrangler: ... not logged in / Authentication error` | `npx wrangler login` expired | Run `npx wrangler login` in `H1SORT_SITE`; the loop recovers by itself. |
| `✗ H1SORT_SITE no existe` | Wrong path in `.env` | Fix `.env`, restart. |
| `✗ no existe el grupo XXXX en D1` | Wrong `GROUP_CODE` (or group not created yet) | Fix/create; it retries every cycle. |
| `✗ login Snowflake: ...` (IP not allowed, token expired, role) | PAT expired, network policy doesn't include the venue IP, wrong role | Reconnect hotspot or renew the PAT; it reconnects by itself. |
| Counts show `≠` for more than a few cycles | Snowflake errors above, or votes were deleted in D1 | Read the red line; if D1 votes were deleted the old rows remain in Snowflake (truncate `RAW.POLL_VOTES` and restart). |
| Same red line repeats | Identical consecutive errors are throttled to once per 15 s | n/a |

Last-resort fallback on stage: `uv run demo/bridge/bridge.py --mock` (clearly labeled `[MODO ENSAYO]`).
