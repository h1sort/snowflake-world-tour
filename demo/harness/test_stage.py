#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "snowflake-connector-python", "httpx", "python-dotenv", "rich"]
# ///
"""Pruebas del harness. Sin red: uv run demo/harness/test_stage.py  (o: uv run --with pytest pytest)."""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import socket
import sys
from pathlib import Path

import httpx
import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("stage", HERE / "stage.py")
stage = importlib.util.module_from_spec(spec)
sys.modules["stage"] = stage
spec.loader.exec_module(stage)

CODE = "7F3A9C1E5B"
GID = "7f3a9c1e-5b24-4d86-9a0e-c1d2e3f4a5b6"
CUT = "2026-10-13 17:05:07"
SECRET_PAT = "pat-SECRETSECRET-123456"
SECRET_PW = "hunter2-hunter2"

RECALC = {"grupos": {"Datos y analítica": {"den": 18, "num": 12}, "Ingeniería": {"den": 22, "num": 11},
                     "Liderazgo": {"den": 7, "num": 4}, "Negocio": {"den": 14, "num": 5},
                     "Otro": {"den": 3, "num": 1}},
          "total_navegadores": 73, "rol_sin_p3": 9}

GOOD_ASK = {
    "mock": False, "grupo": CODE, "pregunta": stage.DEFAULT_QUESTION, "corte_utc": CUT,
    "sql": f"SELECT rol, ... WHERE primera_respuesta_at <= '{CUT}'",
    "columnas": ["ROL", "NAVEGADORES_CON_ROL_Y_P3", "CON_PERMISO", "PCT_PERMISO"],
    "filas": [["Datos y analítica", "18", "12", "66.7"], ["Ingeniería", "22", "11", "50.0"],
              ["Liderazgo", "7", "4", "57.1"], ["Negocio", "14", "5", "35.7"], ["Otro", "3", "1", "33.3"]],
    "respuesta": f"Corte: {CUT} UTC.\n- Negocio: 35.7 % (5 de 14)\n- Otro: muestra insuficiente (n = 3)\n",
}


def ask_with(**changes):
    a = copy.deepcopy(GOOD_ASK)
    a.update(changes)
    return a


def plain(text: str) -> str:
    import re
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def by_id(invs):
    return {i["id"]: i for i in invs}


@pytest.fixture(autouse=True)
def sandbox(tmp_path, monkeypatch):
    """Archivos de trabajo en tmp, sin pausas, sin secretos reales, MOCK apagado."""
    for name, value in {"LAST_ASK": "a.json", "LAST_JUDGE": "j.json", "LOG_FILE": "stage.log",
                        "RECEIPTS": "receipts.jsonl", "RECEIPTS_MOCK": "receipts.mock.jsonl"}.items():
        monkeypatch.setattr(stage, name, tmp_path / value)
    monkeypatch.setattr(stage, "MOCK", False)
    monkeypatch.setattr(stage, "TRANSPORT", None)
    monkeypatch.setattr(stage, "load_dotenv", lambda *a, **k: None)  # un demo/.env real no debe colarse
    for name in ("CORTEX_MODEL", "CORTEX_MODEL_FALLBACK", "SNOWFLAKE_ROLE_AGENT", "SNOWFLAKE_WAREHOUSE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("STAGE_FAST", "1")
    monkeypatch.setenv("GROUP_CODE", CODE)
    monkeypatch.setenv("H1SORT_BASE", "https://h1sort.com")
    monkeypatch.setenv("POLLS_ADMIN_USERNAME", "carlos")
    monkeypatch.setenv("POLLS_ADMIN_PASSWORD", SECRET_PW)
    monkeypatch.setenv("SNOWFLAKE_PAT", SECRET_PAT)
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "myorg_myacct")
    monkeypatch.setenv("SNOWFLAKE_USER", "swt_user")
    stage.setup_logging()


# ---------------------------------------------------------------- invariantes

def test_invariants_all_pass():
    invs = stage.check_invariants(GOOD_ASK, RECALC)
    assert all(i["ok"] for i in invs), invs


def test_denominator_mismatch_downgrades_pasa_to_revisar():
    bad = ask_with(filas=[r[:] for r in GOOD_ASK["filas"]])
    bad["filas"][1][1] = "23"  # Ingeniería: 23 en vez de 22
    invs = stage.check_invariants(bad, RECALC)
    assert not by_id(invs)["denominador"]["ok"]
    assert "Ingeniería" in by_id(invs)["denominador"]["detalle"]
    model = {"veredicto": "pasa", "evidencia": ["todo bien"], "motivo": "ok"}
    final, reasons = stage.combine(model, invs)
    assert final["veredicto"] == "revisar" and reasons


def test_code_never_upgrades():
    invs = stage.check_invariants(GOOD_ASK, RECALC)
    for v in ("revisar", "rechazar"):
        final, _ = stage.combine({"veredicto": v, "evidencia": ["x"], "motivo": "m"}, invs)
        assert final["veredicto"] == v
    bad = stage.check_invariants(ask_with(respuesta="sin corte"), RECALC)
    final, _ = stage.combine({"veredicto": "rechazar", "evidencia": ["x"], "motivo": "m"}, bad)
    assert final["veredicto"] == "rechazar"  # no sube a revisar


def test_pasa_without_evidence_is_downgraded():
    invs = stage.check_invariants(GOOD_ASK, RECALC)
    final, reasons = stage.combine({"veredicto": "pasa", "evidencia": [], "motivo": "m"}, invs)
    assert final["veredicto"] == "revisar" and any("evidencia" in r for r in reasons)


def test_missing_denominator_column_fails():
    ask = ask_with(columnas=["ROL", "PCT_PERMISO"], filas=[[r[0], r[3]] for r in GOOD_ASK["filas"]])
    assert not by_id(stage.check_invariants(ask, RECALC))["denominador"]["ok"]


def test_percentage_inconsistent_with_counts_fails():
    bad = ask_with(filas=[r[:] for r in GOOD_ASK["filas"]])
    bad["filas"][3][3] = "80.0"  # Negocio 5/14 no es 80 %
    assert not by_id(stage.check_invariants(bad, RECALC))["denominador"]["ok"]


def test_fraction_scale_percentage_is_accepted():
    ok = ask_with(filas=[[r[0], r[1], r[2], str(round(int(r[2]) / int(r[1]), 3))] for r in GOOD_ASK["filas"]])
    assert by_id(stage.check_invariants(ok, RECALC))["denominador"]["ok"]


def test_small_group_requires_muestra_insuficiente_wording():
    no_marker = ask_with(respuesta=f"Corte: {CUT} UTC.\n- Otro: 33.3 % (1 de 3)\n- Negocio: 35.7 % (5 de 14)")
    inv = by_id(stage.check_invariants(no_marker, RECALC))["muestra"]
    assert not inv["ok"] and "Otro" in inv["detalle"]
    marked = ask_with(respuesta=f"Corte: {CUT} UTC.\n- Otro: Muestra Insuficiente (n=3)")
    assert by_id(stage.check_invariants(marked, RECALC))["muestra"]["ok"]


def test_muestra_marker_in_table_row_counts():
    ask = ask_with(columnas=GOOD_ASK["columnas"] + ["NOTA"],
                   filas=[r + (["muestra insuficiente"] if r[0] == "Otro" else [""]) for r in GOOD_ASK["filas"]],
                   respuesta=f"Corte {CUT}")
    assert by_id(stage.check_invariants(ask, RECALC))["muestra"]["ok"]


def test_marker_for_a_different_group_does_not_count():
    ask = ask_with(respuesta=f"Corte: {CUT} UTC.\n- Negocio: muestra insuficiente\n- Otro: 33.3 %")
    assert not by_id(stage.check_invariants(ask, RECALC))["muestra"]["ok"]


def test_no_small_groups_needs_no_marker():
    recalc = copy.deepcopy(RECALC)
    recalc["grupos"]["Otro"] = {"den": 9, "num": 3}
    ask = ask_with(filas=[r[:] if r[0] != "Otro" else ["Otro", "9", "3", "33.3"] for r in GOOD_ASK["filas"]],
                   respuesta=f"Corte: {CUT} UTC.")
    assert by_id(stage.check_invariants(ask, recalc))["muestra"]["ok"]


@pytest.mark.parametrize("token", [
    "a" * 32 + "0" * 32,                                   # 64 hex
    "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789-_AbCdE"[:43],    # 43 base64url
])
def test_identifier_tokens_are_detected(token):
    assert len(token) in (43, 64)
    ask = ask_with(respuesta=f"Corte: {CUT} UTC. navegador {token} votó que sí.")
    assert not by_id(stage.check_invariants(ask, RECALC))["identificadores"]["ok"]
    sql_only = ask_with(sql=f"SELECT '{token}'")
    assert not by_id(stage.check_invariants(sql_only, RECALC))["identificadores"]["ok"]


def test_voter_key_word_in_answer_but_not_in_sql():
    assert not by_id(stage.check_invariants(ask_with(respuesta=f"{CUT} VOTER_KEY=abc"), RECALC))["identificadores"]["ok"]
    sql_ok = ask_with(sql=f"SELECT COUNT(DISTINCT voter_key) FROM x WHERE t <= '{CUT}'")
    assert by_id(stage.check_invariants(sql_ok, RECALC))["identificadores"]["ok"]


def test_ordinary_long_identifiers_are_not_tokens():
    assert stage.find_identifiers("NAVEGADORES_CON_ROL_Y_P3_SIN_CORTE_X_YYYYY") == []
    assert stage.find_identifiers("navegadores_con_rol_y_p3_sin_corte_x_yyyyy_123") == []


def test_cutoff_must_be_present():
    assert not by_id(stage.check_invariants(ask_with(respuesta="hola", sql="select 1"), RECALC))["corte"]["ok"]
    iso = ask_with(respuesta="hola", sql=f"... <= '{CUT.replace(' ', 'T')}Z'")
    assert by_id(stage.check_invariants(iso, RECALC))["corte"]["ok"]


def test_validate_verdict_is_strict():
    assert stage.validate_verdict({"veredicto": " Pasa ", "evidencia": ["a"], "motivo": "m"})["veredicto"] == "pasa"
    for bad in ({"veredicto": "aprobar", "evidencia": [], "motivo": ""},
                {"veredicto": "pasa", "evidencia": "x", "motivo": "m"},
                {"veredicto": "pasa", "evidencia": [1], "motivo": "m"}, "pasa"):
        with pytest.raises(ValueError):
            stage.validate_verdict(bad)


def test_sf_literal_builds_snowflake_object():
    lit = stage.sf_literal({"type": "json", "schema": {"required": ["a"], "additionalProperties": False, "d": "it's"}})
    assert lit == "{'type': 'json', 'schema': {'required': ['a'], 'additionalProperties': FALSE, 'd': 'it''s'}}"


# ---------------------------------------------------------------- Ask (SSE)

SSE = "\n".join([
    "event: response.status", 'data: {"message":"Planning the next steps","status":"planning"}', "",
    "event: response.thinking.delta", 'data: {"content_index":0,"text":"hmm"}', "",
    "event: response.text.delta", 'data: {"content_index":1,"text":"Voy a consultar."}', "",
    "event: response.tool_use", 'data: {"content_index":2,"type":"cortex_analyst_text_to_sql","name":"analyst","input":{}}', "",
    "event: response.tool_result.analyst.delta",
    'data: {"content_index":3,"tool_type":"cortex_analyst_text_to_sql","delta":{"sql":"SELECT rol, COUNT(*) FROM r"}}', "",
    "event: response.tool_result.analyst.delta",
    'data: {"content_index":3,"delta":{"result_set":{"resultSetMetaData":{"rowType":[{"name":"ROL"},{"name":"N"}]},"data":[["Negocio","14"]]},"query_id":"q-1"}}', "",
    "event: response.tool_result", 'data: {"content_index":3,"name":"analyst","status":"success","content":[{"type":"json","json":{"answer":1}}]}', "",
    "event: response.text.delta", 'data: {"content_index":4,"text":"Negocio: "}', "",
    "event: response.text.delta", 'data: {"content_index":4,"text":"14 navegadores."}', "",
    "event: response", 'data: {"role":"assistant","status":"completed","content":[{"type":"text","text":"Voy a consultar."},{"type":"tool_use","name":"analyst"},{"type":"tool_result","content":[{"type":"json","json":{"answer":1}}]},{"type":"text","text":"Negocio: 14 navegadores."}]}', "",
    "",
])


def test_run_agent_parses_stream_and_sends_pat_headers():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["auth"] = str(request.url), request.headers["authorization"]
        seen["ttype"], seen["body"] = request.headers["x-snowflake-authorization-token-type"], json.loads(request.content)
        return httpx.Response(200, content=SSE.encode(), headers={"content-type": "text/event-stream"})

    statuses = []
    client = httpx.Client(transport=httpx.MockTransport(handler))
    out = stage.run_agent("¿Pregunta?", client=client, on_status=statuses.append)
    assert seen["url"] == "https://myorg-myacct.snowflakecomputing.com/api/v2/databases/SWT_DEMO/schemas/SEM/agents/AGENTE_ENCUESTA:run"
    assert seen["auth"] == f"Bearer {SECRET_PAT}" and seen["ttype"] == "PROGRAMMATIC_ACCESS_TOKEN"
    assert seen["body"] == {"messages": [{"role": "user", "content": [{"type": "text", "text": "¿Pregunta?"}]}]}
    assert out["sql"] == "SELECT rol, COUNT(*) FROM r"
    assert out["columnas"] == ["ROL", "N"] and out["filas"] == [["Negocio", "14"]]
    assert out["respuesta"] == "Negocio: 14 navegadores." and out["query_id"] == "q-1"
    assert statuses == ["Planning the next steps"]


def test_run_agent_error_event_and_http_error_do_not_leak_token():
    err = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(
        200, content=b'event: error\ndata: {"code":"399504","message":"boom"}\n\n')))
    with pytest.raises(stage.StageError, match="boom"):
        stage.run_agent("q", client=err)
    denied = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401, text=f"bad token {SECRET_PAT}")))
    with pytest.raises(stage.StageError) as exc:
        stage.run_agent("q", client=denied)
    assert "401" in str(exc.value) and SECRET_PAT not in str(exc.value)


def test_markdown_table_fallback_feeds_the_invariants():
    text = ("Corte: " + CUT + " UTC\n\n| Rol | Navegadores (denominador) | Con permiso (numerador) | % |\n|---|---|---|---|\n"
            "| Datos y analítica | 18 | 12 | 66.7 % |\n| Ingeniería | 22 | 11 | 50.0 % |\n| Liderazgo | 7 | 4 | 57.1 % |\n"
            "| Negocio | 14 | 5 | 35.7 % |\n| Otro | 3 | 1 | muestra insuficiente |\n\nFin.")
    cols, rows = stage.parse_markdown_table(text)
    assert cols[0] == "Rol" and len(rows) == 5
    ask = ask_with(columnas=cols, filas=rows, respuesta=text)
    invs = by_id(stage.check_invariants(ask, RECALC))
    assert invs["denominador"]["ok"], invs["denominador"]
    assert invs["muestra"]["ok"]


# ---------------------------------------------------------------- Act

class Site:
    """h1sort.com simulado con httpx.MockTransport; registra cada llamada."""

    def __init__(self, statuses=("open", "open", "open")):
        self.calls: list[tuple[str, str]] = []
        self.requests: list[httpx.Request] = []
        self.statuses = list(statuses)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, request.url.path))
        self.requests.append(request)
        path = request.url.path
        if request.method == "GET" and path == f"/api/polls/public/groups/{CODE}":
            polls = [{"question": f"P{i + 1}", "status": s, "total": 10 if s == "closed" else None}
                     for i, s in enumerate(self.statuses)]
            return httpx.Response(200, json={"group": {"id": GID, "code": CODE, "title": "t", "polls": polls}})
        if request.method == "POST" and path == "/api/polls/auth/login":
            return httpx.Response(200, json={"authenticated": True}, headers={
                "set-cookie": "__Host-polls_admin=tok123; Path=/; HttpOnly; SameSite=Strict; Max-Age=3600; Secure"})
        if request.method == "PATCH" and path == f"/api/polls/admin/groups/{GID}":
            self.statuses = ["closed"] * len(self.statuses)
            return httpx.Response(200, json={"updated": 3})
        return httpx.Response(404, json={"error": "not found"})

    def writes(self):
        return [c for c in self.calls if c[0] != "GET"]


def setup_act(monkeypatch, tmp_path, proposal, *, verdict="pasa", site=None, judge_mock=False, judge_overrides=None,
              answers="s"):
    site = site or Site()
    monkeypatch.setattr(stage, "TRANSPORT", httpx.MockTransport(site.handler))
    monkeypatch.setattr(stage, "propose_action", lambda pedido, code: (proposal, "modelo-falso"))
    stage.write_json(stage.LAST_ASK, GOOD_ASK)
    judge = {"mock": judge_mock, "grupo": CODE, "corte_utc": CUT, "veredicto": verdict}
    judge.update(judge_overrides or {})
    stage.write_json(stage.LAST_JUDGE, judge)
    monkeypatch.setattr("builtins.input", lambda *_: answers)
    return site


def run_act(dry_run=False, pedido="x"):
    return stage.cmd_act(argparse.Namespace(pedido=pedido, dry_run=dry_run))


GOOD_PROPOSAL = {"accion": "cerrar_encuesta", "objetivo": CODE, "motivo": "pedido del orador"}


def test_act_rejects_borrar_votos_without_any_http_call(monkeypatch, tmp_path, capsys):
    site = setup_act(monkeypatch, tmp_path, {"accion": "borrar_votos", "objetivo": CODE, "motivo": "m"})
    assert run_act() == 0
    out = capsys.readouterr().out
    assert "RECHAZADA · sin efecto" in out and "borrar_votos" in out
    assert site.calls == []
    assert not stage.RECEIPTS.exists()


def test_act_rejects_wrong_group_without_any_http_call(monkeypatch, tmp_path, capsys):
    site = setup_act(monkeypatch, tmp_path, {"accion": "cerrar_encuesta", "objetivo": "AAAAAAAAAA", "motivo": "m"})
    run_act()
    assert "RECHAZADA · sin efecto" in capsys.readouterr().out
    assert site.calls == []


@pytest.mark.parametrize("verdict", ["revisar", "rechazar"])
def test_act_rejects_when_verdict_is_not_pasa(monkeypatch, tmp_path, capsys, verdict):
    site = setup_act(monkeypatch, tmp_path, GOOD_PROPOSAL, verdict=verdict)
    run_act()
    out = capsys.readouterr().out
    assert "RECHAZADA · sin efecto" in out and verdict in out
    assert site.calls == []


def test_act_rejects_when_no_verdict_exists(monkeypatch, tmp_path, capsys):
    site = setup_act(monkeypatch, tmp_path, GOOD_PROPOSAL)
    stage.LAST_JUDGE.unlink()
    run_act()
    assert "RECHAZADA · sin efecto" in capsys.readouterr().out and site.calls == []


def test_act_rejects_stale_or_mock_verdicts(monkeypatch, tmp_path, capsys):
    site = setup_act(monkeypatch, tmp_path, GOOD_PROPOSAL, judge_overrides={"corte_utc": "2000-01-01 00:00:00"})
    run_act()
    assert "no corresponde a la última consulta" in capsys.readouterr().out and site.calls == []
    site = setup_act(monkeypatch, tmp_path, GOOD_PROPOSAL, judge_mock=True)
    run_act()
    assert "ensayo" in capsys.readouterr().out and site.calls == []


def test_act_rejects_already_closed_group_and_never_patches(monkeypatch, tmp_path, capsys):
    site = setup_act(monkeypatch, tmp_path, GOOD_PROPOSAL, site=Site(("closed", "closed", "closed")))
    run_act()
    assert "RECHAZADA · sin efecto" in capsys.readouterr().out
    assert site.writes() == []


def test_act_human_says_no_means_no_write(monkeypatch, tmp_path, capsys):
    site = setup_act(monkeypatch, tmp_path, GOOD_PROPOSAL, answers="")
    run_act()
    assert "RECHAZADA · sin efecto" in capsys.readouterr().out
    assert site.writes() == [] and not stage.RECEIPTS.exists()


def test_act_dry_run_stops_before_login_and_patch(monkeypatch, tmp_path, capsys):
    site = setup_act(monkeypatch, tmp_path, GOOD_PROPOSAL)
    assert run_act(dry_run=True) == 0
    assert "DRY-RUN" in capsys.readouterr().out
    assert site.writes() == []


def test_act_pass_path_patches_once_with_correct_request(monkeypatch, tmp_path, capsys):
    site = setup_act(monkeypatch, tmp_path, GOOD_PROPOSAL)
    assert run_act(pedido="Cierra la encuesta y publica los resultados") == 0
    out = capsys.readouterr().out
    patches = [r for r in site.requests if r.method == "PATCH"]
    assert len(patches) == 1
    p = patches[0]
    assert str(p.url) == f"https://h1sort.com/api/polls/admin/groups/{GID}"
    assert json.loads(p.content) == {"status": "closed"}
    assert p.headers["origin"] == "https://h1sort.com"
    assert "__Host-polls_admin=tok123" in p.headers["cookie"]
    login = next(r for r in site.requests if r.url.path == "/api/polls/auth/login")
    assert json.loads(login.content) == {"username": "carlos", "password": SECRET_PW}
    assert login.headers["origin"] == "https://h1sort.com"
    assert site.calls.index(("POST", "/api/polls/auth/login")) < site.calls.index(("PATCH", f"/api/polls/admin/groups/{GID}"))
    receipt = json.loads(stage.RECEIPTS.read_text().splitlines()[-1])
    assert receipt["http_status"] == 200 and receipt["updated"] == 3 and receipt["ok"] and receipt["ts"].endswith("Z")
    assert receipt["verificacion"] == ["closed"] * 3
    assert SECRET_PW not in stage.RECEIPTS.read_text() and SECRET_PW not in out
    assert "HTTP 200" in plain(out) and "updated 3" in plain(out)


def test_act_patch_failure_is_reported_not_assumed(monkeypatch, tmp_path, capsys):
    site = Site()
    base = site.handler
    site.handler = lambda r: httpx.Response(403, json={"error": "forbidden origin"}) if r.method == "PATCH" else base(r)
    setup_act(monkeypatch, tmp_path, GOOD_PROPOSAL, site=site)
    monkeypatch.setattr(stage, "TRANSPORT", httpx.MockTransport(site.handler))
    assert run_act() == 1
    receipt = json.loads(stage.RECEIPTS.read_text().splitlines()[-1])
    assert receipt["ok"] is False and receipt["http_status"] == 403
    assert "no confirmó" in capsys.readouterr().out


def test_login_failure_never_patches(monkeypatch, tmp_path, capsys):
    site = Site()
    base = site.handler
    site.handler = lambda r: httpx.Response(401, json={"error": "invalid credentials"}) if r.url.path.endswith("/login") else base(r)
    setup_act(monkeypatch, tmp_path, GOOD_PROPOSAL, site=site)
    monkeypatch.setattr(stage, "TRANSPORT", httpx.MockTransport(site.handler))
    with pytest.raises(stage.StageError, match="401"):
        run_act()
    assert not [c for c in site.calls if c[0] == "PATCH"]


# ---------------------------------------------------------------- Snowflake (conector simulado)

class FakeCursor:
    def __init__(self, conn):
        self.conn, self.last = conn, None

    def execute(self, sql, params=None):
        self.conn.executed.append((sql, params))
        self.last = (sql, params)
        return self

    def fetchone(self):
        return self.fetchall()[0]

    def fetchall(self):
        sql, params = self.last
        if "CURRENT_ROLE" in sql:
            return [(self.conn.role,)]
        if "GROUP BY ROL" in sql:
            return [(k, v["den"], v["num"]) for k, v in RECALC["grupos"].items()]
        if "COUNT_IF(ROL IS NOT NULL AND PERMISO_PRODUCCION IS NULL)" in sql:
            return [(73, 9)]
        if "AI_COMPLETE" in sql:
            return [(self.conn.ai(sql, params),)]
        raise AssertionError(sql)


class FakeConn:
    def __init__(self, role="SWT_AGENT_RO", ai=None):
        self.role, self.executed, self.closed = role, [], False
        self.ai = ai or (lambda sql, params: json.dumps({"veredicto": "pasa", "evidencia": ["18, 22, 7, 14 y 3 coinciden."], "motivo": "ok"}))

    def cursor(self):
        return FakeCursor(self)

    def close(self):
        self.closed = True


def install_fake_connector(monkeypatch, conn):
    import types
    seen = {}
    connector = types.ModuleType("snowflake.connector")

    def connect(**kw):
        seen.update(kw)
        return conn

    connector.connect = connect
    pkg = types.ModuleType("snowflake")
    pkg.connector = connector
    monkeypatch.setitem(sys.modules, "snowflake", pkg)
    monkeypatch.setitem(sys.modules, "snowflake.connector", connector)
    return seen


def test_real_judge_recomputes_with_readonly_role_and_calls_ai_complete(monkeypatch, capsys):
    conn = FakeConn()
    seen = install_fake_connector(monkeypatch, conn)
    stage.write_json(stage.LAST_ASK, GOOD_ASK)
    assert stage.main(["judge"]) == 0
    assert seen["role"] == "SWT_AGENT_RO" and seen["password"] == SECRET_PAT and seen["account"] == "myorg_myacct"
    assert seen["database"] == "SWT_DEMO" and seen["warehouse"] == "SWT_WH"
    recalcs = [e for e in conn.executed if "GROUP BY ROL" in e[0]]
    assert recalcs and recalcs[0][1] == (CUT,) and "SWT_DEMO.SEM.RESPUESTAS" in recalcs[0][0]
    assert "VOTER_KEY" not in recalcs[0][0]
    ai = [e for e in conn.executed if "AI_COMPLETE" in e[0]]
    assert len(ai) == 1
    sql, params = ai[0]
    assert "response_format => {'type': 'json', 'schema': {" in sql and "'required': ['veredicto', 'evidencia', 'motivo']" in sql
    assert params[0] == "claude-sonnet-4-6" and "Corte (UTC)" in params[1]
    judge = json.loads(stage.LAST_JUDGE.read_text())
    assert judge["veredicto"] == "pasa" and not judge["mock"] and conn.closed
    out = capsys.readouterr().out
    assert SECRET_PAT not in out and "PASA" in plain(out)


def test_real_judge_downgrades_model_pasa_when_agent_denominator_is_wrong(monkeypatch, capsys):
    install_fake_connector(monkeypatch, FakeConn())
    bad = ask_with(filas=[r[:] for r in GOOD_ASK["filas"]])
    bad["filas"][0][1] = "17"
    stage.write_json(stage.LAST_ASK, bad)
    assert stage.main(["judge"]) == 0
    judge = json.loads(stage.LAST_JUDGE.read_text())
    assert judge["veredicto_modelo"] == "pasa" and judge["veredicto"] == "revisar"
    assert "denominador" in " ".join(judge["degradado_por"])


def test_real_judge_invalid_model_output_fails_safe(monkeypatch, capsys):
    install_fake_connector(monkeypatch, FakeConn(ai=lambda s, p: json.dumps({"veredicto": "aprobar", "evidencia": [], "motivo": "x"})))
    stage.write_json(stage.LAST_ASK, GOOD_ASK)
    assert stage.main(["judge"]) == 0
    assert json.loads(stage.LAST_JUDGE.read_text())["veredicto"] == "revisar"


def test_real_judge_falls_back_to_second_model(monkeypatch, capsys):
    calls = []

    def ai(sql, params):
        calls.append(params[0])
        if params[0] == "claude-sonnet-4-6":
            raise RuntimeError("model not available in region")
        return {"veredicto": "pasa", "evidencia": ["ok"], "motivo": "m"}  # VARIANT ya parseado

    install_fake_connector(monkeypatch, FakeConn(ai=ai))
    stage.write_json(stage.LAST_ASK, GOOD_ASK)
    assert stage.main(["judge"]) == 0
    assert calls == ["claude-sonnet-4-6", "llama3.3-70b"]
    assert json.loads(stage.LAST_JUDGE.read_text())["veredicto"] == "pasa"


def test_session_refuses_to_run_as_the_wrong_role(monkeypatch, capsys):
    install_fake_connector(monkeypatch, FakeConn(role="ACCOUNTADMIN"))
    stage.write_json(stage.LAST_ASK, GOOD_ASK)
    assert stage.main(["judge"]) == 1
    assert "ACCOUNTADMIN" in capsys.readouterr().out and not stage.LAST_JUDGE.exists()


def test_real_act_asks_model_for_proposal_then_closes(monkeypatch, tmp_path, capsys):
    site = Site()
    monkeypatch.setattr(stage, "TRANSPORT", httpx.MockTransport(site.handler))
    conn = FakeConn(ai=lambda s, p: json.dumps({"accion": "cerrar_encuesta", "objetivo": CODE, "motivo": "pedido del orador"}))
    install_fake_connector(monkeypatch, conn)
    stage.write_json(stage.LAST_ASK, GOOD_ASK)
    stage.write_json(stage.LAST_JUDGE, {"mock": False, "grupo": CODE, "corte_utc": CUT, "veredicto": "pasa"})
    monkeypatch.setattr("builtins.input", lambda *_: "s")
    assert stage.main(["act", "--pedido", "Cierra la encuesta y publica los resultados"]) == 0
    prompt = next(e for e in conn.executed if "AI_COMPLETE" in e[0])[1][1]
    assert "cerrar_encuesta" in prompt and CODE in prompt and "Cierra la encuesta" in prompt
    assert len([c for c in site.calls if c[0] == "PATCH"]) == 1


def test_real_act_model_proposing_delete_is_refused_with_no_h1sort_call(monkeypatch, capsys):
    site = Site()
    monkeypatch.setattr(stage, "TRANSPORT", httpx.MockTransport(site.handler))
    install_fake_connector(monkeypatch, FakeConn(ai=lambda s, p: json.dumps(
        {"accion": "borrar_votos", "objetivo": "votos incompletos", "motivo": "limpiar"})))
    stage.write_json(stage.LAST_ASK, GOOD_ASK)
    stage.write_json(stage.LAST_JUDGE, {"mock": False, "grupo": CODE, "corte_utc": CUT, "veredicto": "pasa"})
    assert stage.main(["act", "--pedido", "Borra los votos incompletos"]) == 0
    assert "RECHAZADA · sin efecto" in capsys.readouterr().out and site.calls == []


# ---------------------------------------------------------------- mock end to end

def test_mock_end_to_end_without_network(monkeypatch, capsys):
    def no_network(*a, **k):
        raise AssertionError("el modo ensayo no debe abrir sockets")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr("builtins.input", lambda *_: "s")
    assert stage.main(["--mock", "ask"]) == 0
    ask = json.loads(stage.LAST_ASK.read_text())
    assert ask["mock"] is True and ask["corte_utc"] in ask["respuesta"]
    assert stage.main(["--mock", "judge"]) == 0
    judge = json.loads(stage.LAST_JUDGE.read_text())
    assert judge["mock"] and judge["veredicto"] == "pasa" and all(i["ok"] for i in judge["invariantes"])
    assert stage.main(["--mock", "act", "--pedido", "Cierra la encuesta y publica los resultados"]) == 0
    receipt = json.loads(stage.RECEIPTS_MOCK.read_text().splitlines()[-1])
    assert receipt["mock"] and receipt["http_status"] == 200 and receipt["updated"] == 3
    assert not stage.RECEIPTS.exists()
    out = capsys.readouterr().out
    assert out.count("[MODO ENSAYO]") >= 3
    for label in ("SOLICITUD", "VALIDACIÓN", "EJECUCIÓN", "OBSERVACIÓN", "PASA"):
        assert label in out
    assert stage.main(["act", "--mock", "--pedido", "Borra los votos incompletos"]) == 0
    assert "RECHAZADA · sin efecto" in capsys.readouterr().out
    assert len(stage.RECEIPTS_MOCK.read_text().splitlines()) == 1  # el rechazo no genera recibo


def test_mock_judge_downgrades_when_invariants_fail(monkeypatch, capsys):
    stage.main(["--mock", "ask"])
    ask = json.loads(stage.LAST_ASK.read_text())
    ask["filas"][1][1] = "99"
    stage.write_json(stage.LAST_ASK, ask)
    stage.main(["--mock", "judge"])
    out = capsys.readouterr().out
    judge = json.loads(stage.LAST_JUDGE.read_text())
    assert judge["veredicto"] == "revisar" and judge["veredicto_modelo"] == "pasa"
    assert "degradó" in out
    monkeypatch.setattr("builtins.input", lambda *_: "s")
    stage.main(["--mock", "act", "--pedido", "Cierra la encuesta"])
    assert "RECHAZADA · sin efecto" in capsys.readouterr().out
    assert not stage.RECEIPTS_MOCK.exists()


def test_real_judge_refuses_mock_ask(capsys):
    stage.main(["--mock", "ask"])
    assert stage.main(["judge"]) == 1
    assert "ensayo" in capsys.readouterr().out


def test_unexpected_error_prints_one_line_and_logs_traceback(monkeypatch, capsys):
    def boom(args):
        raise RuntimeError("kaboom " + SECRET_PAT)

    monkeypatch.setattr(stage, "cmd_ask", boom)
    assert stage.main(["--mock", "ask"]) == 1
    out = capsys.readouterr().out
    assert "Traceback" not in out and "kaboom" not in out and SECRET_PAT not in out
    assert "stage.log" in out
    assert "Traceback" in stage.LOG_FILE.read_text()


def test_missing_env_is_a_clean_spanish_error(monkeypatch, capsys):
    monkeypatch.delenv("SNOWFLAKE_PAT")
    stage.write_json(stage.LAST_ASK, GOOD_ASK)
    assert stage.main(["ask"]) == 1
    out = capsys.readouterr().out
    assert "SNOWFLAKE_PAT" in out and "Traceback" not in out


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
