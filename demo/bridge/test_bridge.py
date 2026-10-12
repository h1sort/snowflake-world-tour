"""Offline tests for the D1 -> Snowflake bridge.

    uv run --with pytest --with python-dotenv --with rich pytest demo/bridge/test_bridge.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bridge as b  # noqa: E402

SALT = "sal-de-prueba"


def make_bridge(sink=None, mock: b.MockD1 | None = None):
    d1 = mock or b.MockD1()
    sink = sink or b.SqliteSink(":memory:")
    return b.Bridge(b.D1Source(d1, d1.group_code, SALT), sink), d1, sink


# ---------------------------------------------------------------- ORDINAL

def test_ordinal_by_created_at_then_id_regardless_of_input_order():
    polls = [
        {"id": "zzz", "created_at": "2026-10-13 16:41:07"},
        {"id": "aaa", "created_at": "2026-10-13 16:41:07"},   # same second as zzz: id breaks the tie
        {"id": "mmm", "created_at": "2026-10-13 16:41:08"},
        {"id": "000", "created_at": "2026-10-13 16:41:06"},   # earliest wins even with the smallest... id
    ]
    expected = {"000": 1, "aaa": 2, "zzz": 3, "mmm": 4}
    for order in (polls, list(reversed(polls)), sorted(polls, key=lambda p: p["id"])):
        got = {p["id"]: p["ORDINAL"] for p in b.assign_ordinals(order)}
        assert got == expected


def test_ordinal_matches_contract_content_for_fixtures():
    d1 = b.MockD1()
    src = b.D1Source(d1, d1.group_code, SALT)
    src.group()
    polls = b.assign_ordinals(src.polls())
    by_ord = {p["ORDINAL"]: p["question"] for p in polls}
    assert by_ord == {
        1: "¿Cuál describe mejor tu rol?",
        2: "En los últimos 7 días, ¿usaste IA para trabajar con datos?",
        3: "¿Le darías a un agente permiso de actuar en producción?",
    }
    # the fixture deliberately creates P1 and P2 in the same second: the tie is broken by id
    assert polls[0]["created_at"] == polls[1]["created_at"] and polls[0]["id"] < polls[1]["id"]


# ---------------------------------------------------------------- VOTER_KEY

def test_voter_key_is_sha256_hex_of_salt_plus_hash():
    vh = "A" * 43
    assert b.voter_key("s", vh) == hashlib.sha256(("s" + vh).encode()).hexdigest()
    assert len(b.voter_key("s", vh)) == 64
    assert b.voter_key("s", vh) != b.voter_key("t", vh)  # salt matters


def test_votes_leave_the_source_hashed_and_without_voter_hash():
    br, d1, _ = make_bridge()
    d1.reveal_all()
    br.source.group()
    raw = {r["voter_hash"] for r in d1("SELECT voter_hash FROM poll_votes")}
    rows, total = br.source.votes(None)
    assert total == len(rows) == 107
    keys = {r["VOTER_KEY"] for r in rows}
    assert len(keys) == 40 and not (keys & raw)
    assert all("voter_hash" not in r and "VOTER_HASH" not in r for r in rows)
    assert all(re.fullmatch(r"[0-9a-f]{64}", k) for k in keys)


# ---------------------------------------------------------------- watermark / MERGE semantics

def test_since_for_applies_five_second_overlap_and_none():
    assert b.since_for(None) is None
    assert b.since_for("2026-10-13 17:00:03") == "2026-10-13 16:59:58"
    assert b.since_for("2026-10-13 17:00:03", overlap=0) == "2026-10-13 17:00:03"


def test_merge_is_idempotent_in_the_sqlite_mock():
    sink = b.SqliteSink(":memory:")
    rows = [{"ID": "v1", "POLL_ID": "p", "OPTION_ID": "o", "VOTER_KEY": "k1", "CREATED_AT": "2026-10-13 17:00:00"},
            {"ID": "v2", "POLL_ID": "p", "OPTION_ID": "o", "VOTER_KEY": "k2", "CREATED_AT": "2026-10-13 17:00:01"}]
    sink.merge("POLL_VOTES", rows, update=False)
    sink.merge("POLL_VOTES", rows + [{**rows[0], "ID": "v3", "VOTER_KEY": "k3"}], update=False)
    assert sink.con.execute("SELECT COUNT(*) FROM POLL_VOTES").fetchone()[0] == 3
    # dimension tables update on match (e.g. a poll that gets closed)
    poll = {"id": "p", "group_id": "g", "code": "C", "question": "q", "status": "open",
            "created_at": "2026-10-13 16:00:00", "opened_at": "2026-10-13 16:01:00", "closed_at": None, "ORDINAL": 1}
    sink.merge("POLLS", [poll])
    sink.merge("POLLS", [{**poll, "status": "closed", "closed_at": "2026-10-13 17:30:00"}])
    assert sink.con.execute("SELECT COUNT(*), MAX(STATUS) FROM POLLS").fetchone() == (1, "closed")


def test_overlap_rereads_rows_but_never_duplicates_and_counts_match():
    br, d1, sink = make_bridge()
    br.sync_dims()
    d1.tick()                                   # 12 votes land in D1
    first = br.sync_votes()
    assert first.initial and first.new == 12 and first.d1_total == first.sf_total == 12
    again = br.sync_votes()                     # same watermark - 5 s: rows come back, none is new
    assert again.new == 0 and again.sf_total == 12
    d1.tick()
    nxt = br.sync_votes()
    assert nxt.new > 0 and nxt.d1_total == nxt.sf_total == 12 + nxt.new
    assert nxt.latency is not None and 0 <= nxt.latency < 10
    # even a bridge restart (empty `seen`, no watermark) leaves Snowflake without duplicates
    br2 = b.Bridge(b.D1Source(d1, d1.group_code, SALT), sink)
    br2.sync_dims()
    br2.sync_votes()
    assert sink.count_votes(br.source.group_id) == br2.d1_total


def test_failed_merge_does_not_advance_the_watermark():
    class Flaky(b.SqliteSink):
        fail = True

        def merge(self, table, rows, update=True):
            if table == "POLL_VOTES" and self.fail:
                raise b.BridgeError("Snowflake caido")
            super().merge(table, rows, update)

    sink = Flaky(":memory:")
    br, d1, _ = make_bridge(sink)
    br.sync_dims()
    d1.tick()
    with pytest.raises(b.BridgeError):
        br.sync_votes()
    assert br.watermark is None and not br.seen
    sink.fail = False
    assert br.sync_votes().new == 12            # nothing was lost


def test_full_drip_ends_with_all_107_votes_and_40_browsers():
    br, d1, sink = make_bridge()
    br.sync_dims()
    for _ in range(60):
        d1.tick()
        br.sync_votes()
    assert br.d1_total == br.sf_total == 107
    assert sink.con.execute("SELECT COUNT(DISTINCT VOTER_KEY) FROM POLL_VOTES").fetchone()[0] == 40
    assert sink.con.execute("SELECT MIN(ORDINAL), MAX(ORDINAL) FROM POLLS").fetchone() == (1, 3)
    assert sink.con.execute("SELECT COUNT(*) FROM POLL_OPTIONS").fetchone()[0] == 10


# ---------------------------------------------------------------- only the four poll tables

def test_d1_sql_only_touches_the_four_poll_tables_and_only_votes_select_voter_hash():
    br, d1, _ = make_bridge()
    d1.reveal_all()
    br.sync_dims()
    br.sync_votes()
    br.sync_votes()
    br.source.count()
    assert len(d1.queries) >= 6
    for sql in d1.queries:
        low = sql.lower()
        tables = set(re.findall(r"\b(?:from|join)\s+([a-z_]+)", low))
        assert tables and tables <= b.ALLOWED_D1_TABLES, sql
        for forbidden in ("messages", "conversations", "poll_auth_attempts", "sqlite_master", "insert ", "update ",
                          "delete ", "drop ", ";"):
            assert forbidden not in low, (forbidden, sql)
        assert ("voter_hash" in low) == ("from poll_votes where" in low and "select id, poll_id, option_id" in low), sql
        if "group_id" in low or "poll_groups" in low:
            assert br.source.group_code.lower() in low or br.source.group_id.lower() in low  # scoped to the group
    assert b.sql_str("o'brien") == "'o''brien'"
    with pytest.raises(b.BridgeError):
        b.D1Source(d1, "X'; DROP TABLE polls;--", SALT).group()


def test_group_not_found_is_a_readable_error():
    d1 = b.MockD1()
    with pytest.raises(b.BridgeError, match="no existe el grupo"):
        b.D1Source(d1, "ZZZZZZZZZZ", SALT).group()


# ---------------------------------------------------------------- parsing, scrubbing, Snowflake SQL

def test_fixtures_are_wrangler_shaped_and_realistic():
    root = Path(__file__).resolve().parents[1] / "fixtures"
    for name in ("d1_group", "d1_polls", "d1_options", "d1_votes"):
        payload = json.loads((root / f"{name}.json").read_text(encoding="utf-8"))
        assert isinstance(payload, list) and payload[0]["success"] is True and isinstance(payload[0]["results"], list)
    votes = b.load_fixture("d1_votes.json")
    assert all(len(v["voter_hash"]) == 43 for v in votes)
    per_browser: dict[str, set[str]] = {}
    for v in votes:
        per_browser.setdefault(v["voter_hash"], set()).add(v["poll_id"])
    polls = {p["id"]: p for p in b.assign_ordinals(b.load_fixture("d1_polls.json"))}
    p_by_ord = {p["ORDINAL"]: pid for pid, p in polls.items()}
    assert len(per_browser) == 40
    assert sum(1 for s in per_browser.values() if p_by_ord[1] not in s) >= 2   # skipped P1
    assert sum(1 for s in per_browser.values() if p_by_ord[3] not in s) >= 4   # skipped P3
    assert [r for r in b.load_fixture("d1_options.json") if r["label"] == "Sí, con aprobación humana"]


def test_parse_wrangler_json_variants():
    ok = json.dumps([{"results": [{"a": 1}], "success": True}])
    assert b.parse_wrangler_json(ok) == [{"a": 1}]
    assert b.parse_wrangler_json("banner\n" + ok) == [{"a": 1}]
    with pytest.raises(b.BridgeError):
        b.parse_wrangler_json(json.dumps({"error": {"text": "no such table"}}))
    with pytest.raises(b.BridgeError):
        b.parse_wrangler_json("not json")


def test_scrub_removes_voter_tokens_and_secrets():
    vh = "u26AVjFi221QozoVRFsKYm36yOc8pL995UbBTpyQGgA"
    key = hashlib.sha256(b"x").hexdigest()
    msg = b.scrub(f"bad row {vh} key {key} pat=SECRETPAT123", ["SECRETPAT123"])
    assert vh not in msg and key not in msg and "SECRETPAT123" not in msg


def test_snowflake_merge_sql_shape():
    sql = b.build_merge_sql("POLL_VOTES", 2, update=False)
    assert sql.startswith("MERGE INTO SWT_DEMO.RAW.POLL_VOTES t USING")
    assert "ON t.ID = s.ID" in sql and "WHEN MATCHED" not in sql and "WHEN NOT MATCHED THEN INSERT" in sql
    assert sql.count("%s") == 2 * 5 and "_LOADED_AT" in sql and "TRY_TO_TIMESTAMP_NTZ" in sql
    assert "VOTER_KEY" in sql and "voter_hash" not in sql.lower()
    polls = b.build_merge_sql("POLLS", 1, update=True)
    assert "WHEN MATCHED THEN UPDATE SET" in polls and "ORDINAL" in polls and "column9::NUMBER AS ORDINAL" in polls


def test_batch_line_format():
    line = b.format_batch(b.Batch(3, 107, 107, 2.14))
    assert "+3 votos" in line and "total D1 [bold]107[/]" in line and "total Snowflake [bold]107[/]" in line
    assert "latencia ~2.1 s" in line
    assert "≠" in b.format_batch(b.Batch(3, 107, 104, 2.0))
    assert "MODO ENSAYO" in b.format_batch(b.Batch(1, 1, 1, 0.5), mock=True)
