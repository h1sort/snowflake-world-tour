#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["snowflake-connector-python", "python-dotenv", "rich"]
# ///
"""Puente D1 -> Snowflake para la demo en vivo (SWT_DEMO.RAW.*).

    uv run demo/bridge/bridge.py              # loop cada BRIDGE_INTERVAL s (3 por defecto)
    uv run demo/bridge/bridge.py --once       # una sincronizacion y conteos
    uv run demo/bridge/bridge.py --counts     # solo compara conteos D1 vs Snowflake
    uv run demo/bridge/bridge.py --mock       # ensayo sin red (fixtures + SQLite local)

Lee SOLO las cuatro tablas de encuestas (poll_groups, polls, poll_options, poll_votes) y SOLO
las filas del grupo GROUP_CODE. El voter_hash crudo se convierte en VOTER_KEY = sha256(SALT +
voter_hash) en cuanto llega y nunca se imprime ni se envia a Snowflake.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import signal
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable

from dotenv import load_dotenv
from rich.console import Console
from rich.markup import escape

BRIDGE_DIR = Path(__file__).resolve().parent
DEMO_DIR = BRIDGE_DIR.parent
FIXTURES_DIR = DEMO_DIR / "fixtures"
MOCK_SQLITE = BRIDGE_DIR / "mock_snowflake.sqlite"

D1_DATABASE = "h1sort-chat"
SF_DATABASE = "SWT_DEMO"
SF_SCHEMA = "RAW"
ALLOWED_D1_TABLES = {"poll_groups", "polls", "poll_options", "poll_votes"}
WRANGLER_TIMEOUT = 20  # seconds, per wrangler call
OVERLAP_SECONDS = 5  # votes are re-read from (watermark - 5 s); MERGE makes it idempotent
DIMS_EVERY = 30.0  # seconds between group/polls/options resyncs
CHUNK = 200  # rows per MERGE

console = Console(highlight=False)


class BridgeError(RuntimeError):
    """An expected, already-readable failure (shown as one red line)."""


# ---------------------------------------------------------------------------
# Small pure helpers (unit-tested)
# ---------------------------------------------------------------------------

_TOKEN43 = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])")
_HEX64 = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def scrub(text: str, secrets: Iterable[str] = ()) -> str:
    """Remove anything that looks like a voter_hash / VOTER_KEY / configured secret from a message."""
    for s in secrets:
        if s and len(s) >= 6:
            text = text.replace(s, "***")
    text = _TOKEN43.sub("***", text)
    return _HEX64.sub("***", text)


def sql_str(value: str) -> str:
    """Quote a value for a SQL literal. Only ever used on ids/codes that passed safe_id()."""
    return "'" + value.replace("'", "''") + "'"


def safe_id(value: str, what: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.match(value):
        raise BridgeError(f"{what} con formato inesperado")
    return value


def voter_key(salt: str, voter_hash: str) -> str:
    return hashlib.sha256((salt + voter_hash).encode("utf-8")).hexdigest()


def assign_ordinals(polls: list[dict]) -> list[dict]:
    """ORDINAL 1..n by (created_at, id): P1, P2, P3. Independent of the input order."""
    ordered = sorted(polls, key=lambda p: (p["created_at"], p["id"]))
    return [{**p, "ORDINAL": i} for i, p in enumerate(ordered, start=1)]


def parse_d1_ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def fmt_d1_ts(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def since_for(watermark: str | None, overlap: int = OVERLAP_SECONDS) -> str | None:
    """Lower bound for the next votes query ('YYYY-MM-DD HH:MM:SS' compares as a string)."""
    if not watermark:
        return None
    return fmt_d1_ts(parse_d1_ts(watermark) - timedelta(seconds=overlap))


def parse_wrangler_json(text: str) -> list[dict]:
    """`wrangler d1 execute --json` -> rows of the (single) statement: payload[0]["results"]."""
    text = text.strip()
    try:
        payload = json.loads(text)
    except ValueError:
        # wrangler can print banners before the JSON; retry from the first line that starts it
        start = next((m.start() for m in re.finditer(r"^[\[{]", text, re.M)), None)
        if start is None:
            raise BridgeError("wrangler no devolvio JSON") from None
        try:
            payload = json.loads(text[start:])
        except ValueError:
            raise BridgeError("wrangler devolvio JSON incompleto") from None
    if isinstance(payload, dict) and "error" in payload:
        err = payload["error"]
        raise BridgeError("D1: " + str(err.get("text", err) if isinstance(err, dict) else err)[:200])
    try:
        return list(payload[0]["results"])
    except (KeyError, IndexError, TypeError):
        raise BridgeError("respuesta de wrangler con forma inesperada") from None


# ---------------------------------------------------------------------------
# Source: D1 (SQL is built here; a "runner" executes it)
# ---------------------------------------------------------------------------

Runner = Callable[[str], list[dict]]


def wrangler_runner(site: str, database: str = D1_DATABASE, timeout: int = WRANGLER_TIMEOUT) -> Runner:
    site_path = Path(site).expanduser()

    def run(sql: str) -> list[dict]:
        if not site_path.is_dir():
            raise BridgeError(f"H1SORT_SITE no existe: {site_path}")
        env = {**os.environ, "NO_COLOR": "1", "WRANGLER_SEND_METRICS": "false"}
        proc = subprocess.Popen(
            ["npx", "wrangler", "d1", "execute", database, "--remote", "--json", "--command", sql],
            cwd=site_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
            text=True, env=env, start_new_session=True,
        )
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_group(proc)
            raise BridgeError(f"wrangler no respondio en {timeout} s") from None
        except BaseException:  # Ctrl-C included: never leave node running
            _kill_group(proc)
            raise
        try:
            return parse_wrangler_json(out)
        except BridgeError:
            tail = (err or "").strip()[-200:]
            if tail:  # stderr of wrangler never contains result rows
                raise BridgeError("wrangler: " + tail.replace("\n", " ")) from None
            raise

    return run


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        proc.kill()
    try:
        proc.communicate(timeout=2)
    except Exception:  # noqa: BLE001
        pass


class D1Source:
    """Read-only view of ONE group in D1. The only tables touched are the four poll tables."""

    def __init__(self, run: Runner, group_code: str, salt: str):
        self.run = run
        self.group_code = group_code
        self.salt = salt
        self.group_id: str | None = None

    def _in_group(self) -> str:
        return f"(SELECT id FROM polls WHERE group_id = {sql_str(safe_id(self.group_id or '', 'group_id'))})"

    def group(self) -> dict:
        code = safe_id(self.group_code, "GROUP_CODE")
        rows = self.run(f"SELECT id, code, title, created_at FROM poll_groups WHERE code = {sql_str(code)}")
        if not rows:
            raise BridgeError(f"no existe el grupo {code} en D1")
        self.group_id = rows[0]["id"]
        return rows[0]

    def polls(self) -> list[dict]:
        return self.run(
            "SELECT id, group_id, code, question, status, created_at, opened_at, closed_at "
            f"FROM polls WHERE group_id = {sql_str(safe_id(self.group_id or '', 'group_id'))} "
            "ORDER BY created_at ASC, id ASC")

    def options(self) -> list[dict]:
        return self.run(
            "SELECT id, poll_id, label, position FROM poll_options "
            f"WHERE poll_id IN {self._in_group()} ORDER BY poll_id ASC, position ASC")

    def votes(self, since: str | None) -> tuple[list[dict], int | None]:
        """New votes (created_at >= since) with VOTER_KEY already computed + D1 total for the group.

        voter_hash is read here and hashed on the spot; callers never see it.
        """
        cond = f" AND created_at >= {sql_str(since)}" if since else ""
        rows = self.run(
            "SELECT id, poll_id, option_id, voter_hash, created_at, "
            f"(SELECT COUNT(*) FROM poll_votes WHERE poll_id IN {self._in_group()}) AS d1_total "
            f"FROM poll_votes WHERE poll_id IN {self._in_group()}{cond} "
            "ORDER BY created_at ASC, id ASC")
        total = int(rows[0]["d1_total"]) if rows else None
        out = [{
            "ID": r["id"], "POLL_ID": r["poll_id"], "OPTION_ID": r["option_id"],
            "VOTER_KEY": voter_key(self.salt, r["voter_hash"]), "CREATED_AT": r["created_at"],
        } for r in rows]
        return out, total

    def count(self) -> int:
        rows = self.run(f"SELECT COUNT(*) AS n FROM poll_votes WHERE poll_id IN {self._in_group()}")
        return int(rows[0]["n"]) if rows else 0


# ---------------------------------------------------------------------------
# Mock D1: the real SQL runs against an in-memory SQLite loaded from fixtures
# ---------------------------------------------------------------------------

D1_SCHEMA = """
CREATE TABLE poll_groups (id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL, code TEXT);
CREATE UNIQUE INDEX idx_poll_groups_code ON poll_groups (code);
CREATE TABLE polls (id TEXT PRIMARY KEY, group_id TEXT NOT NULL, code TEXT NOT NULL UNIQUE, question TEXT NOT NULL,
  status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT, opened_at TEXT, closed_at TEXT);
CREATE TABLE poll_options (id TEXT PRIMARY KEY, poll_id TEXT NOT NULL, label TEXT NOT NULL, position INTEGER NOT NULL);
CREATE TABLE poll_votes (id TEXT PRIMARY KEY, poll_id TEXT NOT NULL, option_id TEXT NOT NULL,
  voter_hash TEXT NOT NULL CHECK (length(voter_hash) = 43), created_at TEXT NOT NULL,
  UNIQUE (poll_id, voter_hash));
"""


def load_fixture(name: str) -> list[dict]:
    return parse_wrangler_json((FIXTURES_DIR / name).read_text(encoding="utf-8"))


class MockD1:
    """Runner with the same contract as wrangler_runner, plus tick() to drip votes in over time."""

    INITIAL = 12

    def __init__(self, fixtures: Path | None = None, seed: int = 7):
        self.con = sqlite3.connect(":memory:", check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(D1_SCHEMA)
        self.rng = random.Random(seed)
        self.queries: list[str] = []
        g = load_fixture("d1_group.json")[0]
        self.con.execute("INSERT INTO poll_groups (id, title, created_at, code) VALUES (?,?,?,?)",
                         (g["id"], g["title"], g["created_at"], g["code"]))
        self.group_code = g["code"]
        for p in load_fixture("d1_polls.json"):
            self.con.execute(
                "INSERT INTO polls (id, group_id, code, question, status, created_at, opened_at, closed_at) "
                "VALUES (?,?,?,?,?,?,?,?)", (p["id"], p["group_id"], p["code"], p["question"], p["status"],
                                             p["created_at"], p["opened_at"], p["closed_at"]))
        for o in load_fixture("d1_options.json"):
            self.con.execute("INSERT INTO poll_options (id, poll_id, label, position) VALUES (?,?,?,?)",
                             (o["id"], o["poll_id"], o["label"], o["position"]))
        self.pending = sorted(load_fixture("d1_votes.json"), key=lambda v: (v["created_at"], v["id"]))
        self.started = False

    def __call__(self, sql: str) -> list[dict]:
        self.queries.append(sql)
        if not sql.lstrip().upper().startswith("SELECT"):
            raise BridgeError("mock D1: solo lectura")
        return [dict(r) for r in self.con.execute(sql).fetchall()]

    def _insert(self, v: dict, created_at: str) -> None:
        self.con.execute(
            "INSERT OR IGNORE INTO poll_votes (id, poll_id, option_id, voter_hash, created_at) VALUES (?,?,?,?,?)",
            (v["id"], v["poll_id"], v["option_id"], v["voter_hash"], created_at))

    def reveal_all(self) -> None:
        """--once / --counts: everything, original fixture timestamps."""
        for v in self.pending:
            self._insert(v, v["created_at"])
        self.pending = []

    def tick(self) -> None:
        """Loop mode: first call shows a burst already 'in D1', later calls drip a few votes at 'now'."""
        now = datetime.now(timezone.utc)
        if not self.started:
            self.started = True
            batch = [self.pending.pop(0) for _ in range(min(self.INITIAL, len(self.pending)))]
            for i, v in enumerate(batch):  # spread over the last ~minute, order preserved
                self._insert(v, fmt_d1_ts(now - timedelta(seconds=60 - i * (50 / max(1, len(batch))))))
            return
        for _ in range(min(self.rng.randint(2, 6), len(self.pending))):
            v = self.pending.pop(0)
            self._insert(v, fmt_d1_ts(now - timedelta(seconds=self.rng.uniform(0.3, 1.5))))


# ---------------------------------------------------------------------------
# Sinks: Snowflake and its local SQLite stand-in. Same tables, same MERGE-ON-ID semantics.
# ---------------------------------------------------------------------------

TABLES: dict[str, list[tuple[str, str]]] = {
    "POLL_GROUPS": [("ID", "VARCHAR"), ("CODE", "VARCHAR"), ("TITLE", "VARCHAR"), ("CREATED_AT", "TIMESTAMP_NTZ")],
    "POLLS": [("ID", "VARCHAR"), ("GROUP_ID", "VARCHAR"), ("CODE", "VARCHAR"), ("QUESTION", "VARCHAR"),
              ("STATUS", "VARCHAR"), ("CREATED_AT", "TIMESTAMP_NTZ"), ("OPENED_AT", "TIMESTAMP_NTZ"),
              ("CLOSED_AT", "TIMESTAMP_NTZ"), ("ORDINAL", "NUMBER")],
    "POLL_OPTIONS": [("ID", "VARCHAR"), ("POLL_ID", "VARCHAR"), ("LABEL", "VARCHAR"), ("POSITION", "NUMBER")],
    "POLL_VOTES": [("ID", "VARCHAR"), ("POLL_ID", "VARCHAR"), ("OPTION_ID", "VARCHAR"), ("VOTER_KEY", "VARCHAR"),
                   ("CREATED_AT", "TIMESTAMP_NTZ")],
}
# D1 column name -> RAW column name is just upper-case; ORDINAL is computed by the bridge.


def to_raw(table: str, row: dict) -> dict:
    return {c: row.get(c, row.get(c.lower())) for c, _ in TABLES[table]}


def build_merge_sql(table: str, n_rows: int, update: bool) -> str:
    """MERGE ... ON ID using a VALUES list. Values are bound as parameters (%s)."""
    cols = TABLES[table]
    marks = "(" + ",".join(["%s"] * len(cols)) + ")"
    select = ", ".join(
        f"TRY_TO_TIMESTAMP_NTZ(column{i}::VARCHAR, 'YYYY-MM-DD HH24:MI:SS') AS {c}" if t == "TIMESTAMP_NTZ"
        else f"column{i}::{t} AS {c}" for i, (c, t) in enumerate(cols, start=1))
    names = ", ".join(c for c, _ in cols)
    sql = (f"MERGE INTO {SF_DATABASE}.{SF_SCHEMA}.{table} t USING "
           f"(SELECT {select} FROM VALUES {','.join([marks] * n_rows)}) s ON t.ID = s.ID ")
    if update:
        sets = ", ".join(f"t.{c} = s.{c}" for c, _ in cols if c != "ID")
        sql += f"WHEN MATCHED THEN UPDATE SET {sets}, t._LOADED_AT = CURRENT_TIMESTAMP() "
    sql += (f"WHEN NOT MATCHED THEN INSERT ({names}, _LOADED_AT) "
            f"VALUES ({', '.join('s.' + c for c, _ in cols)}, CURRENT_TIMESTAMP())")
    return sql


def chunks(rows: list, size: int = CHUNK):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


class SnowflakeSink:
    label = "Snowflake"

    def __init__(self, account: str, user: str, pat: str, role: str, warehouse: str, pat_mode: str = "auto"):
        self.cfg = dict(account=account, user=user, role=role, warehouse=warehouse)
        self.pat = pat
        self.pat_mode = pat_mode
        self._con = None

    def secrets(self) -> list[str]:
        return [self.pat]

    def _connect(self):
        import snowflake.connector  # lazy: unit tests and --mock never need it

        base = dict(**self.cfg, database=SF_DATABASE, schema=SF_SCHEMA, login_timeout=15, network_timeout=30,
                    session_parameters={"QUERY_TAG": "swt-bridge"})
        # Documented way (docs.snowflake.com/en/user-guide/programmatic-access-tokens): PAT as `password`.
        # Newer connectors also have authenticator=PROGRAMMATIC_ACCESS_TOKEN + token=.
        attempts = {"password": [dict(password=self.pat)],
                    "token": [dict(authenticator="PROGRAMMATIC_ACCESS_TOKEN", token=self.pat)],
                    "auto": [dict(password=self.pat),
                             dict(authenticator="PROGRAMMATIC_ACCESS_TOKEN", token=self.pat)]}[self.pat_mode]
        last: Exception | None = None
        for extra in attempts:
            try:
                return snowflake.connector.connect(**base, **extra)
            except Exception as exc:  # noqa: BLE001 - try the other PAT method
                last = exc
        raise BridgeError("login Snowflake: " + str(last)[:200])

    @property
    def con(self):
        if self._con is None:
            self._con = self._connect()
        return self._con

    def reset(self) -> None:
        try:
            if self._con is not None:
                self._con.close()
        except Exception:  # noqa: BLE001
            pass
        self._con = None

    close = reset

    def merge(self, table: str, rows: list[dict], update: bool = True) -> None:
        cur = self.con.cursor()
        try:
            for part in chunks(rows):
                params = [v for r in part for v in (to_raw(table, r)[c] for c, _ in TABLES[table])]
                cur.execute(build_merge_sql(table, len(part), update), params)
        finally:
            cur.close()

    def count_votes(self, group_id: str) -> int:
        cur = self.con.cursor()
        try:
            cur.execute(f"SELECT COUNT(*) FROM {SF_DATABASE}.{SF_SCHEMA}.POLL_VOTES WHERE POLL_ID IN "
                        f"(SELECT ID FROM {SF_DATABASE}.{SF_SCHEMA}.POLLS WHERE GROUP_ID = %s)", (group_id,))
            return int(cur.fetchone()[0])
        finally:
            cur.close()


class SqliteSink:
    """Local stand-in for Snowflake (--mock and tests). INSERT .. ON CONFLICT(ID) == MERGE ON ID."""

    label = "Snowflake (SQLite local)"

    def __init__(self, path: str | Path = ":memory:", fresh: bool = False):
        if fresh and str(path) != ":memory:":
            for suffix in ("", "-wal", "-shm", "-journal"):
                Path(str(path) + suffix).unlink(missing_ok=True)
        self.con = sqlite3.connect(str(path), check_same_thread=False)
        for table, cols in TABLES.items():
            defs = ", ".join(f"{c} {'INTEGER' if t == 'NUMBER' else 'TEXT'}" + (" PRIMARY KEY" if c == "ID" else "")
                             for c, t in cols)
            self.con.execute(f"CREATE TABLE IF NOT EXISTS {table} ({defs}, _LOADED_AT TEXT)")
        self.con.commit()

    def secrets(self) -> list[str]:
        return []

    def reset(self) -> None:
        pass

    def close(self) -> None:
        self.con.close()

    def merge(self, table: str, rows: list[dict], update: bool = True) -> None:
        cols = [c for c, _ in TABLES[table]]
        conflict = ("DO UPDATE SET " + ", ".join(f"{c} = excluded.{c}" for c in cols if c != "ID")
                    + ", _LOADED_AT = excluded._LOADED_AT") if update else "DO NOTHING"
        sql = (f"INSERT INTO {table} ({', '.join(cols)}, _LOADED_AT) VALUES ({','.join('?' * (len(cols) + 1))}) "
               f"ON CONFLICT(ID) {conflict}")
        loaded = fmt_d1_ts(datetime.now(timezone.utc))
        self.con.executemany(sql, [[to_raw(table, r)[c] for c in cols] + [loaded] for r in rows])
        self.con.commit()

    def count_votes(self, group_id: str) -> int:
        return self.con.execute(
            "SELECT COUNT(*) FROM POLL_VOTES WHERE POLL_ID IN (SELECT ID FROM POLLS WHERE GROUP_ID = ?)",
            (group_id,)).fetchone()[0]


# ---------------------------------------------------------------------------
# The bridge
# ---------------------------------------------------------------------------

@dataclass
class Batch:
    new: int
    d1_total: int
    sf_total: int | None
    latency: float | None  # seconds; None for the initial load or an empty batch
    initial: bool = False


@dataclass
class Bridge:
    source: D1Source
    sink: object
    group: dict | None = None
    polls: list[dict] = field(default_factory=list)
    n_options: int = 0
    watermark: str | None = None
    seen: set[str] = field(default_factory=set)
    d1_total: int = 0
    sf_total: int | None = None
    first_batch_done: bool = False

    def sync_dims(self) -> None:
        group = self.source.group()
        polls = assign_ordinals(self.source.polls())
        options = self.source.options()
        self.sink.merge("POLL_GROUPS", [group])
        self.sink.merge("POLLS", polls)
        self.sink.merge("POLL_OPTIONS", options)
        self.group, self.polls, self.n_options = group, polls, len(options)
        self.sf_total = self.sink.count_votes(group["id"])

    def sync_votes(self, now: datetime | None = None) -> Batch:
        rows, total = self.source.votes(since_for(self.watermark))
        if total is not None:
            self.d1_total = total
        new = [r for r in rows if r["ID"] not in self.seen]
        if new:
            self.sink.merge("POLL_VOTES", new, update=False)  # votes are immutable: insert-if-missing
            self.sf_total = self.sink.count_votes(self.group["id"])
        # Only reached when the MERGE succeeded: advance the watermark and remember the ids.
        if rows:
            self.watermark = max(r["CREATED_AT"] for r in rows)
        self.seen.update(r["ID"] for r in new)
        initial = not self.first_batch_done
        self.first_batch_done = True
        latency = None
        if new and not initial:
            now = now or datetime.now(timezone.utc)
            latency = max(0.0, (now - parse_d1_ts(max(r["CREATED_AT"] for r in new))).total_seconds())
        return Batch(len(new), self.d1_total, self.sf_total, latency, initial)


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def counts_line(d1: int, sf: int | None) -> str:
    if sf is None:
        return f"D1 [bold]{d1}[/] · Snowflake [bold]?[/]"
    ok = d1 == sf
    mark = "[bold green]✓ coinciden[/]" if ok else f"[bold yellow]≠ diferencia {d1 - sf:+d}[/]"
    return f"D1 [bold]{d1}[/] · Snowflake [bold]{sf}[/]  {mark}"


def format_batch(b: Batch, mock: bool = False) -> str:
    tag = "[bold yellow]\\[MODO ENSAYO][/] " if mock else ""
    lat = "carga inicial" if b.initial else (f"latencia ~{b.latency:.1f} s" if b.latency is not None else "")
    sf = "?" if b.sf_total is None else str(b.sf_total)
    ok = b.sf_total is not None and b.sf_total == b.d1_total
    color = "green" if ok else "yellow"
    line = (f"{tag}[dim]{time.strftime('%H:%M:%S')}[/] [bold {color}]+{b.new} votos[/] · "
            f"total D1 [bold]{b.d1_total}[/] · total Snowflake [bold]{sf}[/]")
    if lat:
        line += f" · {lat}"
    return line + (" [bold green]✓[/]" if ok else " [bold yellow]≠[/]")


class ErrorReporter:
    """One red line per error; identical consecutive errors are throttled so the stage stays readable."""

    def __init__(self, secrets: list[str], mock: bool = False, repeat_after: float = 15.0):
        self.secrets, self.mock, self.repeat_after = secrets, mock, repeat_after
        self.last: tuple[str, float] | None = None

    def report(self, exc: BaseException) -> None:
        msg = scrub(str(exc) or exc.__class__.__name__, self.secrets).replace("\n", " ")[:220]
        if not isinstance(exc, BridgeError):
            msg = f"{exc.__class__.__name__}: {msg}"
        now = time.monotonic()
        if self.last and self.last[0] == msg and now - self.last[1] < self.repeat_after:
            return
        self.last = (msg, now)
        console.print(f"[bold red]✗ {escape(msg)}  (reintentando)[/]")


# ---------------------------------------------------------------------------
# Config + wiring
# ---------------------------------------------------------------------------

def need(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        console.print(f"[bold red]✗ falta {name} en demo/.env (ver demo/.env.example)[/]")
        sys.exit(2)
    return value


def build(args: argparse.Namespace) -> tuple[Bridge, ErrorReporter, float]:
    interval = float(args.interval or os.environ.get("BRIDGE_INTERVAL") or 3)
    if args.mock:
        d1 = MockD1()
        sink = SqliteSink(MOCK_SQLITE, fresh=not args.counts)
        salt = os.environ.get("VOTER_SALT") or "sal-de-ensayo"
        source = D1Source(d1, d1.group_code, salt)
        if args.once or args.counts:
            d1.reveal_all()
        return Bridge(source, sink), ErrorReporter([salt], mock=True), interval
    group_code = need("GROUP_CODE")
    salt = need("VOTER_SALT")
    site = need("H1SORT_SITE")
    sink = SnowflakeSink(
        account=need("SNOWFLAKE_ACCOUNT"), user=need("SNOWFLAKE_USER"), pat=need("SNOWFLAKE_PAT"),
        role=os.environ.get("SNOWFLAKE_ROLE_LOADER", "SWT_LOADER"),
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "SWT_WH"),
        pat_mode=os.environ.get("SNOWFLAKE_PAT_AUTH", "auto").strip().lower() or "auto")
    source = D1Source(wrangler_runner(site), group_code, salt)
    return Bridge(source, sink), ErrorReporter(sink.secrets() + [salt]), interval


def print_counts(bridge: Bridge, mock: bool) -> int:
    d1 = bridge.source.count()
    sf = bridge.sink.count_votes(bridge.source.group_id)
    tag = "[bold yellow]\\[MODO ENSAYO][/] " if mock else ""
    console.print(f"{tag}{counts_line(d1, sf)}")
    return 0 if d1 == sf else 1


def run_once(bridge: Bridge, mock: bool) -> int:
    bridge.sync_dims()
    batch = bridge.sync_votes()
    console.print(format_batch(batch, mock))
    return print_counts(bridge, mock)


def run_counts(bridge: Bridge, mock: bool) -> int:
    bridge.source.group()
    return print_counts(bridge, mock)


def run_loop(bridge: Bridge, reporter: ErrorReporter, interval: float, mock: bool) -> None:
    last_dims = float("-inf")
    announced: tuple | None = None
    with console.status("conectando…", spinner="dots") as status:
        while True:
            started = time.monotonic()
            try:
                tick = getattr(bridge.source.run, "tick", None)
                if tick:
                    tick()
                if started - last_dims >= DIMS_EVERY:
                    bridge.sync_dims()
                    last_dims = time.monotonic()
                    sig = (bridge.group["code"], len(bridge.polls), bridge.n_options)
                    if sig != announced:
                        announced = sig
                        tag = "[bold yellow]\\[MODO ENSAYO][/] " if mock else ""
                        console.print(f"{tag}[dim]grupo {bridge.group['code']} · {len(bridge.polls)} preguntas · "
                                      f"{bridge.n_options} opciones sincronizadas[/]")
                batch = bridge.sync_votes()
                if batch.new:
                    console.print(format_batch(batch, mock))
                status.update(f"esperando votos…  {counts_line(bridge.d1_total, bridge.sf_total)}")
            except Exception as exc:  # noqa: BLE001 - fail-open: report and keep looping
                reporter.report(exc)
                bridge.sink.reset()  # reconnect next time if the Snowflake session died
            time.sleep(max(0.0, interval - (time.monotonic() - started)))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Puente D1 -> Snowflake (demo)")
    ap.add_argument("--once", action="store_true", help="una sincronizacion y conteos")
    ap.add_argument("--counts", action="store_true", help="solo imprime conteos D1 vs Snowflake")
    ap.add_argument("--mock", action="store_true", help="ensayo sin red: fixtures + SQLite local")
    ap.add_argument("--interval", type=float, help="segundos entre ciclos (default BRIDGE_INTERVAL o 3)")
    ap.add_argument("--env", type=Path, default=DEMO_DIR / ".env", help="ruta del .env")
    args = ap.parse_args(argv)

    load_dotenv(args.env)  # real environment variables win over the file
    bridge, reporter, interval = build(args)
    if args.mock:
        console.print("[bold yellow]\\[MODO ENSAYO][/] sin red: fixtures de demo/fixtures → SQLite local "
                      f"({MOCK_SQLITE.relative_to(DEMO_DIR.parent)})")
    try:
        if args.counts:
            return run_counts(bridge, args.mock)
        if args.once:
            return run_once(bridge, args.mock)
        console.print(f"[dim]puente D1 → Snowflake · cada {interval:g} s · Ctrl-C para salir[/]")
        run_loop(bridge, reporter, interval, args.mock)
        return 0
    except KeyboardInterrupt:
        console.print("\n[dim]puente detenido[/]")
        return 0
    except Exception as exc:  # noqa: BLE001 - --once/--counts: one red line, non-zero exit
        reporter.report(exc)
        return 1
    finally:
        try:
            bridge.sink.close()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    sys.exit(main())
