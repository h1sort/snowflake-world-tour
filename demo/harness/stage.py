#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["snowflake-connector-python", "httpx", "python-dotenv", "rich"]
# ///
"""Harness en escena: Ask -> Judge -> Act (Snowflake World Tour CDMX).

    uv run demo/harness/stage.py ask                      # diapositiva 8
    uv run demo/harness/stage.py judge                    # diapositiva 9
    uv run demo/harness/stage.py act --pedido "..."       # diapositiva 10
    uv run demo/harness/stage.py --mock <comando>         # ensayo sin red [MODO ENSAYO]

ask    Cortex Agent SWT_DEMO.SEM.AGENTE_ENCUESTA (API REST, PAT). Muestra SQL, tabla y respuesta.
judge  Invariantes en codigo (recalculo propio sobre SEM.RESPUESTAS) y luego AI_COMPLETE con
       salida tipada. El codigo solo puede degradar el veredicto del modelo.
act    El modelo propone {accion, objetivo, motivo}; la aplicacion valida, un humano aprueba y
       solo entonces se ejecuta el PATCH que cierra la encuesta en h1sort.com.

La configuracion sale de variables de entorno (ver demo/.env.example). Nada de esto imprime
secretos ni VOTER_KEY. Los tracebacks van a demo/harness/stage.log, nunca a la pantalla.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import textwrap
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit

import httpx
from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

HARNESS_DIR = Path(__file__).resolve().parent
DEMO_DIR = HARNESS_DIR.parent
FIXTURES_DIR = DEMO_DIR / "fixtures"
LAST_ASK = HARNESS_DIR / ".last_ask.json"
LAST_JUDGE = HARNESS_DIR / ".last_judge.json"
LOG_FILE = HARNESS_DIR / "stage.log"
RECEIPTS = DEMO_DIR / "receipts.jsonl"
RECEIPTS_MOCK = DEMO_DIR / "receipts.mock.jsonl"

SF_DATABASE = "SWT_DEMO"
SF_SCHEMA = "SEM"
AGENT_NAME = "AGENTE_ENCUESTA"
DEFAULT_QUESTION = (
    "Por rol, ¿qué porcentaje le daría a un agente permiso de actuar en producción? "
    "Solo cuenta a quien respondió rol y P3."
)
DEFAULT_MODEL = "claude-sonnet-5"      # igual que el agente (03_agent.sql)
FALLBACK_MODEL = "claude-sonnet-4-5"   # el Claude con más cobertura regional
MIN_N = 5
MOCK_GROUP = "7F3A9C1E5B"  # mismo grupo que los fixtures d1_* del puente
PERMISO_SI = ("Sí", "Sí, con aprobación humana")

# La unica herramienta que la aplicacion ejecuta. Todo lo demas se rechaza.
ALLOWLIST = {
    "cerrar_encuesta": "Cierra todas las preguntas del grupo de encuesta y publica los resultados "
                       "en h1sort.com. El objetivo es el código del grupo.",
}

MOCK = False
TRANSPORT: httpx.BaseTransport | None = None  # solo para pruebas (httpx.MockTransport)
SECRET_ENV = ("SNOWFLAKE_PAT", "POLLS_ADMIN_PASSWORD", "VOTER_SALT")

console = Console(highlight=False)
log = logging.getLogger("stage")

# ---------------------------------------------------------------------------
# Pantalla
# ---------------------------------------------------------------------------
DIM, BOLD, RESET = "\033[2m", "\033[1m", "\033[0m"
ORANGE, PURPLE = "\033[38;5;208m", "\033[38;5;135m"
COLOR = {
    "ASK": "\033[34m", "JUDGE": "\033[34m", "ACT": "\033[34m",
    "CORTE": "\033[36m", "PREGUNTA": "\033[33m", "SQL": "\033[36m", "RESULTADO": "\033[32m",
    "RESPUESTA": "\033[32m", "PEDIDO": "\033[33m",
    "SOLICITUD": PURPLE, "MODELO": PURPLE, "JUICIO": PURPLE,
    "VALIDACIÓN": "\033[36m", "INVARIANTES": "\033[36m", "RECÁLCULO": "\033[36m",
    "APROBACIÓN": "\033[33m", "EJECUCIÓN": "\033[32m", "OBSERVACIÓN": "\033[32m", "RECIBO": "\033[32m",
    "VEREDICTO": "\033[1m", "RECHAZADA": ORANGE, "ERROR": ORANGE, "DRY-RUN": "\033[33m",
}
VERDICT_COLOR = {"pasa": "green", "revisar": "yellow", "rechazar": "red"}
VERDICT_ANSI = {"pasa": "\033[32m", "revisar": "\033[33m", "rechazar": "\033[31m"}


def stage(name: str, text: str = "") -> None:
    print(f"{COLOR.get(name, '')}{BOLD}{name} ›{RESET} {text}", flush=True)


def say(text: str = "", indent: int = 3, width: int = 66, style: str = "") -> None:
    """Texto con sangria y salto de linea a un ancho legible desde el fondo del salon."""
    if not text:
        print()
        return
    for raw in str(text).splitlines() or [""]:
        if not raw.strip():
            print()
            continue
        if raw.lstrip().startswith("|"):  # tabla markdown: no se parte
            print(f"{' ' * indent}{style}{raw.strip()}{RESET if style else ''}")
            continue
        for line in textwrap.wrap(raw, width=width, subsequent_indent="  " if raw.lstrip().startswith(("-", "·")) else "") or [""]:
            print(f"{' ' * indent}{style}{line}{RESET if style else ''}")


def pause(seconds: float) -> None:
    if not os.environ.get("STAGE_FAST"):
        time.sleep(seconds)


def banner(title: str, subtitle: str = "") -> None:
    bar = "━" * 46
    print(f"\n{BOLD}{bar}\n {title}{RESET}" + (f"  {DIM}{subtitle}{RESET}" if subtitle else ""))
    print(f"{BOLD}{bar}{RESET}")
    if MOCK:
        print(f"{BOLD}\033[30;43m [MODO ENSAYO] sin red · datos de ejemplo {RESET}")
    print()


class StageError(Exception):
    """Fallo esperado: ya viene redactado en espanol para mostrarse en una linea."""


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(DEMO_DIR.parent))
    except ValueError:
        return str(path)


def redact(text: str) -> str:
    for name in SECRET_ENV:
        value = os.environ.get(name, "")
        if len(value) >= 6:
            text = text.replace(value, "‹oculto›")
    return text


# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------

def env(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.environ.get(name) or default  # una variable vacía en .env cuenta como no definida
    if required and not value:
        raise StageError(f"falta {name} en demo/.env (ver demo/.env.example)")
    return value or ""


def group_code() -> str:
    code = os.environ.get("GROUP_CODE", "").strip()
    if code:
        return code
    if MOCK:
        return MOCK_GROUP
    raise StageError("falta GROUP_CODE en demo/.env (ver demo/.env.example)")


def account_id() -> str:
    a = env("SNOWFLAKE_ACCOUNT", required=True).strip().lower()
    a = re.sub(r"^https?://", "", a).rstrip("/")
    return a.removesuffix(".snowflakecomputing.com")


def account_url() -> str:
    # Los nombres de host no admiten guion bajo: org_cuenta -> org-cuenta.
    return f"https://{account_id().replace('_', '-')}.snowflakecomputing.com"


def h1sort_base() -> str:
    return env("H1SORT_BASE", "https://h1sort.com").rstrip("/")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_fixture(name: str) -> Any:
    path = FIXTURES_DIR / name
    if not path.is_file():
        raise StageError(f"falta el fixture {rel(path)}")
    return read_json(path)


# ---------------------------------------------------------------------------
# ASK: Cortex Agents REST (agent:run, SSE)
#   POST /api/v2/databases/{db}/schemas/{schema}/agents/{name}:run
#   https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-run
# ---------------------------------------------------------------------------

class AgentError(StageError):
    pass


def iter_sse(lines: Any) -> Iterator[tuple[str, str]]:
    event, data = None, []
    for line in lines:
        if line == "":
            if data:
                yield event or "message", "\n".join(data)
            event, data = None, []
        elif line.startswith(":"):
            continue
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:][1:] if line[5:6] == " " else line[5:])
    if data:
        yield event or "message", "\n".join(data)


def _walk(obj: Any, depth: int = 0) -> Iterator[dict]:
    if depth > 6:
        return
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v, depth + 1)


class AgentStream:
    """Acumula los eventos SSE del agente: texto final, SQL y result_set."""

    def __init__(self, on_status: Any = None) -> None:
        self.on_status = on_status
        self.text_by_idx: dict[int, str] = {}
        self.sql_delta = ""
        self.sql_result: str | None = None
        self.result_set: Any = None
        self.query_id: str | None = None
        self.last_tool_idx = -1
        self.final_content: list = []
        self.events_seen: list[str] = []

    def _harvest(self, obj: Any) -> None:
        for d in _walk(obj):
            if isinstance(d.get("sql"), str) and d["sql"].strip():
                self.sql_result = d["sql"]
            if d.get("result_set"):
                self.result_set = d["result_set"]
            if isinstance(d.get("query_id"), str):
                self.query_id = d["query_id"]

    def feed(self, event: str, data: dict) -> None:
        self.events_seen.append(event)
        idx = data.get("content_index")
        if event == "response.status" and self.on_status:
            self.on_status(data.get("message") or data.get("status") or "")
        elif event == "response.text.delta":
            i = idx if isinstance(idx, int) else 0
            self.text_by_idx[i] = self.text_by_idx.get(i, "") + (data.get("text") or "")
        elif event == "response.text":
            i = idx if isinstance(idx, int) else 0
            self.text_by_idx[i] = data.get("text") or self.text_by_idx.get(i, "")
        elif event in ("response.tool_use", "response.tool_result"):
            if isinstance(idx, int):
                self.last_tool_idx = max(self.last_tool_idx, idx)
            if event == "response.tool_result":
                self._harvest(data.get("content"))
        elif event == "response.tool_result.analyst.delta":
            delta = data.get("delta") or {}
            if isinstance(delta.get("sql"), str):
                self.sql_delta += delta["sql"]
            if delta.get("result_set"):
                self.result_set = delta["result_set"]
            if isinstance(delta.get("query_id"), str):
                self.query_id = delta["query_id"]
        elif event == "response.table":
            if data.get("result_set"):
                self.result_set = data["result_set"]
            if isinstance(data.get("query_id"), str):
                self.query_id = data["query_id"]
        elif event == "response":
            content = data.get("content")
            if isinstance(content, list):
                self.final_content = content
                self._harvest(content)
        elif event == "error":
            raise AgentError(f"el agente devolvió un error: {data.get('message') or data.get('code') or 'desconocido'}")

    @property
    def sql(self) -> str:
        sql = (self.sql_result or self.sql_delta or "").strip()
        half = len(sql) // 2
        if half and len(sql) % 2 == 0 and sql[:half] == sql[half:]:  # delta repetido
            sql = sql[:half]
        return sql

    @property
    def answer(self) -> str:
        if self.final_content:
            parts: list[str] = []
            for item in self.final_content:
                kind = item.get("type") if isinstance(item, dict) else None
                if kind == "tool_result":
                    parts = []
                elif kind == "text":
                    parts.append(str(item.get("text", "")))
            text = "\n".join(p.strip() for p in parts if p.strip()).strip()
            if text:
                return text
        idxs = sorted(self.text_by_idx)
        use = [i for i in idxs if i > self.last_tool_idx] or idxs
        return "\n".join(self.text_by_idx[i].strip() for i in use if self.text_by_idx[i].strip())


def result_set_table(result_set: Any) -> tuple[list[str], list[list]]:
    """result_set del API SQL de Snowflake -> (columnas, filas)."""
    if isinstance(result_set, str):
        try:
            result_set = json.loads(result_set)
        except ValueError:
            return [], []
    if not isinstance(result_set, dict):
        return [], []
    meta = result_set.get("resultSetMetaData") or {}
    cols = [str(c.get("name", "")) for c in meta.get("rowType") or []]
    rows = [list(r) for r in result_set.get("data") or []]
    if not cols and rows:
        cols = [f"COL{i + 1}" for i in range(len(rows[0]))]
    return cols, rows


def agent_url() -> str:
    return f"{account_url()}/api/v2/databases/{SF_DATABASE}/schemas/{SF_SCHEMA}/agents/{AGENT_NAME}:run"


def run_agent(question: str, client: httpx.Client | None = None, on_status: Any = None) -> dict:
    token = env("SNOWFLAKE_PAT", required=True)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Snowflake-Authorization-Token-Type": "PROGRAMMATIC_ACCESS_TOKEN",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    body = {"messages": [{"role": "user", "content": [{"type": "text", "text": question}]}]}
    own = client is None
    client = client or httpx.Client(transport=TRANSPORT, timeout=httpx.Timeout(150.0, connect=15.0))
    acc = AgentStream(on_status)
    try:
        with client.stream("POST", agent_url(), headers=headers, json=body) as resp:
            if resp.status_code != 200:
                resp.read()
                hint = {
                    401: "token rechazado: revisa SNOWFLAKE_PAT y la política de red",
                    403: "sin permiso: el rol necesita USAGE sobre el agente y CORTEX_USER",
                    404: f"no existe el agente {SF_DATABASE}.{SF_SCHEMA}.{AGENT_NAME} (o el rol no lo ve)",
                }.get(resp.status_code, "respuesta inesperada")
                log.error("agent HTTP %s: %s", resp.status_code, redact(resp.text[:500]))
                raise AgentError(f"Cortex Agents respondió HTTP {resp.status_code}: {hint}")
            for event, payload in iter_sse(resp.iter_lines()):
                try:
                    data = json.loads(payload)
                except ValueError:
                    continue  # [DONE] u otros marcadores
                if isinstance(data, dict):
                    acc.feed(event, data)
    except httpx.TimeoutException:
        raise AgentError("el agente no respondió a tiempo (150 s)") from None
    except httpx.HTTPError as exc:
        log.exception("ask network error")
        raise AgentError(f"no se pudo contactar a Snowflake ({type(exc).__name__})") from None
    finally:
        if own:
            client.close()
    cols, rows = result_set_table(acc.result_set)
    if not acc.sql and not acc.answer:
        log.error("stream sin contenido; eventos: %s", acc.events_seen[:40])
        raise AgentError("el agente no devolvió SQL ni respuesta")
    return {"sql": acc.sql, "columnas": cols, "filas": rows, "respuesta": acc.answer, "query_id": acc.query_id}


def build_agent_prompt(question: str, cutoff: str) -> str:
    return (
        f"{question}\n\n"
        f"Corte de datos (UTC): {cutoff}. Usa solo filas con PRIMERA_RESPUESTA_AT <= '{cutoff}'. "
        f"Escribe este corte literalmente en tu respuesta. "
        f"Para cada rol incluye numerador, denominador y porcentaje."
    )


def clean_markdown(text: str) -> str:
    """Solo para mostrar en pantalla (las invariantes usan el texto original)."""
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)  # el SQL ya se mostró arriba
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    return text.replace("`", "")


def parse_markdown_table(text: str) -> tuple[list[str], list[list]]:
    """Plan B si el stream no trae result_set: primera tabla markdown de la respuesta."""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip().replace("**", "") for c in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                continue
            rows.append(cells)
        elif rows:
            break
    if len(rows) < 2:
        return [], []
    width = len(rows[0])
    return rows[0], [r for r in rows[1:] if len(r) == width]


def fmt_cell(col: str, value: Any, pct_scale: float = 1.0) -> str:
    if value is None:
        return "·"
    num = _num(value)
    if num is None:
        return str(value)
    if re.search(r"PCT|PORC|PERCENT", col.upper()):
        return f"{num * pct_scale:.1f} %"
    return str(int(num)) if float(num).is_integer() else f"{num:.1f}"


def print_table(cols: list[str], rows: list[list], title: str = "") -> None:
    if not cols or not rows:
        say("(sin filas)", style=DIM)
        return
    scale = 1.0
    for i, c in enumerate(cols):
        if re.search(r"PCT|PORC|PERCENT", c.upper()):
            vals = [_num(r[i]) for r in rows if i < len(r)]
            vals = [v for v in vals if v is not None]
            if vals and max(vals) <= 1.0:
                scale = 100.0
    table = Table(box=box.SIMPLE_HEAD, pad_edge=False, title=title or None, title_justify="left")
    for c in cols:
        table.add_column(Text(c.lower().replace("_", " "), style="bold"), justify="left")
    for r in rows:
        table.add_row(*[Text(fmt_cell(c, r[i] if i < len(r) else None, scale)) for i, c in enumerate(cols)])
    console.print(table, soft_wrap=False)


def show_sql(sql: str, max_lines: int = 18) -> None:
    lines = textwrap.dedent(sql.strip("\n")).splitlines() if sql.strip() else ["(el agente no devolvió SQL)"]
    for line in lines[:max_lines]:
        print(f"    {COLOR['SQL']}{line.rstrip()}{RESET}")
    if len(lines) > max_lines:
        print(f"    {DIM}… {len(lines) - max_lines} líneas más (completo en .last_ask.json){RESET}")


def cmd_ask(args: argparse.Namespace) -> int:
    cutoff = utc_stamp()  # el corte se fija ANTES de preguntar
    question = args.pregunta or DEFAULT_QUESTION
    code = group_code()
    banner("ASK · consultar al agente", f"Cortex Agent {SF_DATABASE}.{SF_SCHEMA}.{AGENT_NAME}")
    stage("CORTE", f"{BOLD}{cutoff} UTC{RESET}  {DIM}fijado antes de preguntar{RESET}")
    stage("PREGUNTA")
    say(question)
    print()
    if MOCK:
        fx = load_fixture("harness_ask.json")
        pause(0.8)
        result = {
            "sql": fx["sql"].replace("{corte}", cutoff),
            "columnas": fx["columnas"],
            "filas": fx["filas"],
            "respuesta": fx["respuesta"].replace("{corte}", cutoff),
            "query_id": fx.get("query_id"),
        }
        if args.pregunta and args.pregunta != DEFAULT_QUESTION:
            say("(en ensayo la respuesta es siempre la del fixture)", style=DIM)
    else:
        seen: list[str] = []

        def on_status(msg: str) -> None:
            if msg and msg not in seen:
                seen.append(msg)
                say(f"· {msg}", style=DIM)

        result = run_agent(build_agent_prompt(question, cutoff), on_status=on_status)
        if not result["filas"]:
            result["columnas"], result["filas"] = parse_markdown_table(result["respuesta"])
            if result["filas"]:
                say("(el stream no trajo result_set: tabla tomada del texto de la respuesta)", style=DIM)
        print()
    stage("SQL", f"{DIM}lo que el agente ejecutó{RESET}")
    show_sql(result["sql"])
    print()
    stage("RESULTADO")
    print_table(result["columnas"], result["filas"])
    stage("RESPUESTA")
    say(clean_markdown(result["respuesta"]))
    print()
    record = {
        "mock": MOCK, "grupo": code, "pregunta": question, "corte_utc": cutoff,
        "sql": result["sql"], "columnas": result["columnas"], "filas": result["filas"],
        "respuesta": result["respuesta"], "query_id": result["query_id"], "ts": utc_iso(),
    }
    write_json(LAST_ASK, record)
    say(f"guardado en {rel(LAST_ASK)}", style=DIM)
    return 0


# ---------------------------------------------------------------------------
# JUDGE: invariantes deterministas + AI_COMPLETE tipado
# ---------------------------------------------------------------------------
RANK = {"rechazar": 0, "revisar": 1, "pasa": 2}
HEX64 = re.compile(r"(?<![0-9A-Za-z])[0-9a-fA-F]{64}(?![0-9A-Za-z])")
TOK43 = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])")
TOTAL_LABELS = {"total", "todos", "general", "global", "all", "gran total"}

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "veredicto": {"type": "string", "description": "exactamente uno de: pasa, revisar, rechazar"},
        "evidencia": {"type": "array", "items": {"type": "string"}},
        "motivo": {"type": "string"},
    },
    "required": ["veredicto", "evidencia", "motivo"],
    "additionalProperties": False,
}
ACT_SCHEMA = {
    "type": "object",
    "properties": {
        "accion": {"type": "string"},
        "objetivo": {"type": "string"},
        "motivo": {"type": "string"},
    },
    "required": ["accion", "objetivo", "motivo"],
    "additionalProperties": False,
}


def _norm(s: Any) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s).strip().casefold()


def _num(x: Any) -> float | None:
    if x is None or isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace("%", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def parse_agent_table(cols: list[str], rows: list[list]) -> dict | None:
    """Tabla del agente -> {grupos: {clave: {label, den, num, pct, celdas}}, total, tiene_*}."""
    if not cols or not rows:
        return None
    n = len(cols)
    gi = next((i for i in range(n) if sum(1 for r in rows if i < len(r) and r[i] is not None and _num(r[i]) is None) > len(rows) / 2), None)
    if gi is None:
        return None
    numeric = [i for i in range(n) if i != gi and all(i >= len(r) or r[i] is None or _num(r[i]) is not None for r in rows)]
    names = {i: cols[i].upper() for i in numeric}
    pct_i = next((i for i in numeric if re.search(r"PCT|PORC|PERCENT|%", names[i])), None)
    rest = [i for i in numeric if i != pct_i]
    num_i = next((i for i in rest if re.search(r"CON_PERMISO|NUMER|PERMISO|AFIRM|^SI", names[i])), None)
    den_i = next((i for i in rest if i != num_i and re.search(r"NAVEGADORES|DENOM|BASE|TOTAL|VALID|MUESTRA|^N$|_N$|^N_", names[i])), None)
    if den_i is None and num_i is None and len(rest) == 2:
        sums = {i: sum(_num(r[i]) or 0 for r in rows) for i in rest}
        den_i = max(rest, key=lambda i: sums[i])
        num_i = next(i for i in rest if i != den_i)
    elif den_i is None and len(rest) == 2 and num_i is not None:
        den_i = next(i for i in rest if i != num_i)
    grupos: dict[str, dict] = {}
    total = None
    for r in rows:
        if gi >= len(r) or r[gi] is None:
            continue
        label = str(r[gi])
        entry = {
            "label": label,
            "den": _num(r[den_i]) if den_i is not None and den_i < len(r) else None,
            "num": _num(r[num_i]) if num_i is not None and num_i < len(r) else None,
            "pct": _num(r[pct_i]) if pct_i is not None and pct_i < len(r) else None,
            "pct_dec": _decimals(r[pct_i]) if pct_i is not None and pct_i < len(r) else 0,
            "celdas": [str(c) for c in r if isinstance(c, str)],
        }
        if _norm(label) in TOTAL_LABELS:
            total = entry
        else:
            grupos[_norm(label)] = entry
    return {"grupos": grupos, "total": total, "tiene_den": den_i is not None,
            "tiene_num": num_i is not None, "tiene_pct": pct_i is not None}


def _decimals(raw: Any) -> int:
    m = re.search(r"\.(\d+)", str(raw))
    return len(m.group(1)) if m else 0


def _pct_ok(pct: float, num: float, den: float, dec: int = 1) -> bool:
    """El porcentaje debe cuadrar con num/den, como fracción (0-1) o como % (0-100), al redondeo que trae."""
    if den <= 0:
        return False
    exp = num / den
    tol = 0.5 * 10 ** -dec + 1e-9
    return abs(pct - 100 * exp) <= tol or abs(pct - exp) <= min(tol, 0.05)


def inv_denominador(ask: dict, recalc: dict) -> dict:
    title = "denominador = respuestas válidas"
    parsed = parse_agent_table(ask.get("columnas") or [], ask.get("filas") or [])
    if not parsed or not parsed["tiene_den"]:
        return {"id": "denominador", "titulo": title, "ok": False,
                "detalle": "la respuesta no trae una tabla con denominadores"}
    if not parsed["tiene_num"] and not parsed["tiene_pct"]:
        return {"id": "denominador", "titulo": title, "ok": False, "detalle": "falta numerador o porcentaje"}
    problems: list[str] = []
    expected = recalc["grupos"]
    for label, rc in expected.items():
        row = parsed["grupos"].get(_norm(label))
        if row is None:
            problems.append(f"{label}: no aparece en la tabla del agente")
            continue
        if row["den"] is None or int(row["den"]) != rc["den"]:
            problems.append(f"{label}: denominador agente {_fmt(row['den'])} vs recalculado {rc['den']}")
        if row["num"] is not None and int(row["num"]) != rc["num"]:
            problems.append(f"{label}: numerador agente {_fmt(row['num'])} vs recalculado {rc['num']}")
        if row["pct"] is not None and not _pct_ok(row["pct"], rc["num"], rc["den"], row["pct_dec"]):
            problems.append(f"{label}: el porcentaje no cuadra con {rc['num']}/{rc['den']}")
    known = {_norm(k) for k in expected}
    for key, row in parsed["grupos"].items():
        if key not in known:
            problems.append(f"{row['label']}: grupo que no existe en el recálculo")
    if parsed["total"] and parsed["total"]["den"] is not None:
        tot = sum(rc["den"] for rc in expected.values())
        if int(parsed["total"]["den"]) != tot:
            problems.append(f"total: agente {_fmt(parsed['total']['den'])} vs recalculado {tot}")
    if problems:
        return {"id": "denominador", "titulo": title, "ok": False, "detalle": "; ".join(problems[:4])}
    total = sum(rc["den"] for rc in expected.values())
    return {"id": "denominador", "titulo": title, "ok": True,
            "detalle": f"{len(expected)} grupos coinciden con el recálculo (n total = {total})"}


def _fmt(v: Any) -> str:
    return "·" if v is None else (str(int(v)) if float(v).is_integer() else f"{v:.1f}")


def inv_muestra(ask: dict, recalc: dict) -> dict:
    title = f"n ≥ {MIN_N} por grupo o «muestra insuficiente»"
    small = [(label, rc["den"]) for label, rc in recalc["grupos"].items() if rc["den"] < MIN_N]
    if not small:
        return {"id": "muestra", "titulo": title, "ok": True, "detalle": f"ningún grupo con n < {MIN_N}"}
    parsed = parse_agent_table(ask.get("columnas") or [], ask.get("filas") or []) or {"grupos": {}}
    lines = [_norm(ln) for ln in str(ask.get("respuesta", "")).splitlines()]
    missing: list[str] = []
    for label, n in small:
        key = _norm(label)
        row = parsed["grupos"].get(key)
        in_row = bool(row) and any("muestra insuficiente" in _norm(c) for c in row["celdas"])
        in_text = any(key in ln and "muestra insuficiente" in ln for ln in lines)
        if not (in_row or in_text):
            missing.append(f"{label} (n={n})")
    if missing:
        return {"id": "muestra", "titulo": title, "ok": False,
                "detalle": "sin «muestra insuficiente» en: " + ", ".join(missing)}
    return {"id": "muestra", "titulo": title, "ok": True,
            "detalle": "marcado: " + ", ".join(f"{l} (n={n})" for l, n in small)}


def find_identifiers(text: str) -> list[str]:
    found = [m.group() for m in HEX64.finditer(text)]
    for m in TOK43.finditer(text):
        tok = m.group()
        if re.search(r"\d", tok) and re.search(r"[A-Za-z]", tok) and not re.fullmatch(r"[A-Z0-9_]+|[a-z0-9_]+", tok):
            found.append(tok)
    return found


def scrub_identifiers(text: str) -> str:
    for tok in set(find_identifiers(text)):
        text = text.replace(tok, "‹id›")
    return text


def inv_identificadores(ask: dict) -> dict:
    title = "sin identificadores"
    shown = " ".join([str(ask.get("respuesta", ""))] + [str(c) for c in ask.get("columnas") or []]
                     + [str(v) for r in ask.get("filas") or [] for v in r if v is not None])
    everything = shown + " " + str(ask.get("sql", ""))
    bad = []
    if find_identifiers(everything):
        bad.append("token de 43 caracteres o 64 hex")
    if re.search(r"voter[_ ]?(key|hash)", shown, re.IGNORECASE):
        bad.append("mención de VOTER_KEY en lo que ve el público")
    if bad:
        return {"id": "identificadores", "titulo": title, "ok": False, "detalle": "; ".join(bad)}
    return {"id": "identificadores", "titulo": title, "ok": True, "detalle": "ningún token tipo VOTER_KEY"}


TS_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?")


def inv_corte(ask: dict) -> dict:
    """Corte visible: el de la aplicación, o el corte_datos propio del agente (último voto cargado)."""
    title = "corte visible"
    cutoff = str(ask.get("corte_utc", ""))
    text = str(ask.get("respuesta", ""))
    hay = f"{text}\n{ask.get('sql', '')}"
    forms = {cutoff[:16], cutoff[:16].replace(" ", "T")}
    if cutoff and any(f in hay for f in forms):
        return {"id": "corte", "titulo": title, "ok": True, "detalle": f"{cutoff} UTC aparece en la respuesta"}
    own = TS_RE.search(text)
    if own:
        return {"id": "corte", "titulo": title, "ok": True,
                "detalle": f"la respuesta declara su propio corte: {own.group()} UTC"}
    return {"id": "corte", "titulo": title, "ok": False, "detalle": "la respuesta no declara ningún corte (fecha y hora UTC)"}


def check_invariants(ask: dict, recalc: dict) -> list[dict]:
    return [inv_denominador(ask, recalc), inv_muestra(ask, recalc), inv_identificadores(ask), inv_corte(ask)]


def validate_verdict(obj: Any) -> dict:
    if not isinstance(obj, dict):
        raise ValueError("la salida no es un objeto")
    v = str(obj.get("veredicto", "")).strip().lower()
    ev, motivo = obj.get("evidencia"), obj.get("motivo")
    if v not in RANK:
        raise ValueError(f"veredicto fuera del esquema: {v!r}")
    if not isinstance(ev, list) or not all(isinstance(x, str) for x in ev):
        raise ValueError("evidencia debe ser una lista de textos")
    if not isinstance(motivo, str):
        raise ValueError("motivo debe ser texto")
    return {"veredicto": v, "evidencia": [x.strip() for x in ev if x.strip()], "motivo": motivo.strip()}


def combine(model: dict, invariants: list[dict]) -> tuple[dict, list[str]]:
    """El codigo solo puede degradar: cualquier invariante fallida => como maximo «revisar»."""
    final = dict(model)
    reasons = [f"invariante fallida: {i['titulo']}" for i in invariants if not i["ok"]]
    if model["veredicto"] == "pasa" and not model["evidencia"]:
        reasons.append("«pasa» sin evidencia")
    if reasons and RANK[final["veredicto"]] > RANK["revisar"]:
        final["veredicto"] = "revisar"
    return final, reasons


RECALC_SQL = f"""SELECT ROL,
       COUNT(*) AS DEN,
       COUNT_IF(PERMISO_PRODUCCION IN ('Sí', 'Sí, con aprobación humana')) AS NUM
FROM {SF_DATABASE}.{SF_SCHEMA}.RESPUESTAS
WHERE ROL IS NOT NULL
  AND PERMISO_PRODUCCION IS NOT NULL
  AND PRIMERA_RESPUESTA_AT <= TO_TIMESTAMP_NTZ(%s)
GROUP BY ROL
ORDER BY ROL"""
RECALC_EXTRA_SQL = f"""SELECT COUNT(*), COUNT_IF(ROL IS NOT NULL AND PERMISO_PRODUCCION IS NULL)
FROM {SF_DATABASE}.{SF_SCHEMA}.RESPUESTAS
WHERE PRIMERA_RESPUESTA_AT <= TO_TIMESTAMP_NTZ(%s)"""


def sf_literal(v: Any) -> str:
    """Python -> literal de objeto de Snowflake (para response_format)."""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return "'" + v.replace("\\", "\\\\").replace("'", "''") + "'"
    if isinstance(v, list):
        return "[" + ", ".join(sf_literal(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{sf_literal(str(k))}: {sf_literal(x)}" for k, x in v.items()) + "}"
    raise TypeError(type(v))


class SfSession:
    """Conexion de solo lectura como SWT_AGENT_RO (snowflake-connector-python, PAT)."""

    def __init__(self) -> None:
        import snowflake.connector  # import tardio: --mock y las pruebas no lo necesitan

        logging.getLogger("snowflake.connector").setLevel(logging.CRITICAL)
        self.role = env("SNOWFLAKE_ROLE_AGENT", "SWT_AGENT_RO")
        pat = env("SNOWFLAKE_PAT", required=True)
        base = dict(account=account_id(), user=env("SNOWFLAKE_USER", required=True), role=self.role,
                    warehouse=env("SNOWFLAKE_WAREHOUSE", "SWT_WH"), database=SF_DATABASE, schema=SF_SCHEMA,
                    login_timeout=20, network_timeout=90, session_parameters={"QUERY_TAG": "swt-harness"})
        # Igual que el puente: documentado = PAT como `password`; conectores nuevos: authenticator=PROGRAMMATIC_ACCESS_TOKEN.
        mode = env("SNOWFLAKE_PAT_AUTH", "auto").lower()
        attempts = {"password": [dict(password=pat)],
                    "token": [dict(authenticator="PROGRAMMATIC_ACCESS_TOKEN", token=pat)]}.get(
            mode, [dict(password=pat), dict(authenticator="PROGRAMMATIC_ACCESS_TOKEN", token=pat)])
        last: Exception | None = None
        self.conn = None
        for extra in attempts:
            try:
                self.conn = snowflake.connector.connect(**base, **extra)
                break
            except Exception as exc:  # noqa: BLE001 - probar el otro método de PAT
                last = exc
        if self.conn is None:
            log.error("snowflake connect failed: %s", redact(str(last)))
            raise StageError(f"no se pudo conectar a Snowflake: {redact(str(last))[:160]}")
        self.cur = self.conn.cursor()
        actual = self.cur.execute("SELECT CURRENT_ROLE()").fetchone()[0]
        if str(actual).upper() != self.role.upper():
            self.close()
            raise StageError(f"la sesión corre como {actual}, no como {self.role}: me detengo")

    def query(self, sql: str, params: tuple = ()) -> list[tuple]:
        try:
            return self.cur.execute(sql, params or None).fetchall()
        except Exception as exc:  # noqa: BLE001
            log.exception("snowflake query failed")
            raise StageError(f"Snowflake rechazó la consulta: {redact(str(exc))[:160]}") from None

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:  # noqa: BLE001
            pass


def recompute(sf: SfSession, cutoff: str) -> dict:
    rows = sf.query(RECALC_SQL, (cutoff,))
    total, sin_p3 = sf.query(RECALC_EXTRA_SQL, (cutoff,))[0]
    return {"grupos": {str(r[0]): {"den": int(r[1]), "num": int(r[2])} for r in rows},
            "total_navegadores": int(total), "rol_sin_p3": int(sin_p3)}


def recalc_from_fixture(fx: dict) -> dict:
    return {"grupos": {r[0]: {"den": int(r[1]), "num": int(r[2])} for r in fx["recalculo"]},
            "total_navegadores": int(fx["total_navegadores"]), "rol_sin_p3": int(fx["rol_sin_p3"])}


def ai_complete_json(sf: SfSession, prompt: str, schema: dict) -> tuple[dict, str]:
    """AI_COMPLETE con response_format. Prueba CORTEX_MODEL y luego CORTEX_MODEL_FALLBACK."""
    models = [env("CORTEX_MODEL", DEFAULT_MODEL)]
    fb = env("CORTEX_MODEL_FALLBACK", FALLBACK_MODEL)
    if fb and fb not in models:
        models.append(fb)
    fmt = sf_literal({"type": "json", "schema": schema})
    sql = ("SELECT AI_COMPLETE(model => %s, prompt => %s, "
           "model_parameters => {'temperature': 0, 'max_tokens': 900}, response_format => " + fmt + ")")
    last = ""
    for model in models:
        try:
            raw = sf.cur.execute(sql, (model, prompt)).fetchone()[0]
            obj = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(obj, dict) and "structured_output" in obj:  # show_details
                so = obj["structured_output"][0]
                obj = so.get("raw_message", so) if isinstance(so, dict) else so
                obj = json.loads(obj) if isinstance(obj, str) else obj
            if not isinstance(obj, dict):
                raise ValueError("AI_COMPLETE devolvió NULL o algo que no es un objeto")
            return obj, model
        except Exception as exc:  # noqa: BLE001
            log.exception("AI_COMPLETE failed with %s", model)
            last = redact(str(exc))[:140]
            if model != models[-1]:
                say(f"modelo {model} no respondió; probando {models[-1]}", style=DIM)
    raise StageError(f"AI_COMPLETE no respondió ({last})")


def judge_prompt(ask: dict, recalc: dict, invariants: list[dict]) -> str:
    tabla = "\n".join(" | ".join(str(c) for c in r) for r in ask.get("filas") or [])
    cols = " | ".join(ask.get("columnas") or [])
    rc = "\n".join(f"{k}: denominador {v['den']}, con permiso {v['num']}" for k, v in recalc["grupos"].items())
    inv = "\n".join(f"- [{'ok' if i['ok'] else 'FALLA'}] {i['titulo']}: {i['detalle']}" for i in invariants)
    return scrub_identifiers(textwrap.dedent(f"""\
        Eres el juez de una respuesta de un agente de datos sobre una encuesta en vivo.
        Definiciones aprobadas: «permiso» = P3 es «Sí» o «Sí, con aprobación humana». El denominador son
        los navegadores que respondieron rol y P3. Una respuesta faltante nunca es un «No». Una fila es un
        navegador, no una persona. Grupos con n < {MIN_N} deben decir «muestra insuficiente».

        Pregunta: {ask.get('pregunta')}
        Corte (UTC): {ask.get('corte_utc')}

        SQL del agente:
        {str(ask.get('sql', ''))[:1500]}

        Tabla del agente ({cols}):
        {tabla[:1500]}

        Respuesta del agente:
        {str(ask.get('respuesta', ''))[:1500]}

        Recálculo independiente de la aplicación (SEM.RESPUESTAS, mismo corte):
        {rc}
        Navegadores con rol pero sin P3 (no cuentan como «No»): {recalc['rol_sin_p3']}

        Invariantes de la aplicación:
        {inv}

        Emite un veredicto: «pasa» solo si la respuesta es fiel a los datos recalculados y respeta las
        definiciones; «revisar» si algo no se puede confirmar o falta evidencia; «rechazar» si es incorrecta.
        En «evidencia» da de 2 a 4 frases cortas con números concretos del recálculo. «motivo» es una frase.
        Responde solo con el objeto JSON del esquema."""))


def render_checks(items: list[dict], detail: bool = True) -> None:
    for i in items:
        mark = f"\033[32m✓{RESET}" if i["ok"] else f"{ORANGE}✕{RESET}"
        print(f"   {mark} {BOLD}{i['titulo']}{RESET}")
        if detail and i.get("detalle"):
            print(f"       {DIM}{i['detalle']}{RESET}")
        pause(0.35)


def verdict_card(verdict: dict) -> None:
    body = json.dumps(verdict, ensure_ascii=False, indent=2)
    color = VERDICT_COLOR[verdict["veredicto"]]
    console.print(Panel(Text(body), title="salida tipada", title_align="left", border_style=color,
                        padding=(1, 2), width=min(console.width, 78)))


def cmd_judge(args: argparse.Namespace) -> int:
    if not LAST_ASK.is_file():
        raise StageError("no hay consulta previa: corre primero «ask»")
    ask = read_json(LAST_ASK)
    if bool(ask.get("mock")) != MOCK:
        raise StageError("la última consulta es " + ("de ensayo" if ask.get("mock") else "real") +
                         ": corre «ask» " + ("sin" if ask.get("mock") else "con") + " --mock")
    banner("JUDGE · juzgar la respuesta", "invariantes en código, luego juicio del modelo")
    stage("CORTE", f"{ask['corte_utc']} UTC")
    sf = None
    if MOCK:
        fx = load_fixture("harness_judge.json")
        recalc, model_out, model_name = recalc_from_fixture(fx), fx["modelo"], fx.get("modelo_nombre", "ensayo")
        pause(0.6)
    else:
        sf = SfSession()
    try:
        who = f"como {BOLD}{sf.role}{RESET}" if sf else f"como {BOLD}SWT_AGENT_RO{RESET}"
        stage("RECÁLCULO", f"SQL propio {who} {DIM}(el Judge no confía en el agente){RESET}")
        show_sql(RECALC_SQL.replace("TO_TIMESTAMP_NTZ(%s)", f"'{ask['corte_utc']}'"))
        if sf:
            recalc = recompute(sf, ask["corte_utc"])
        print_table(["ROL", "DEN", "NUM"], [[k, v["den"], v["num"]] for k, v in recalc["grupos"].items()])
        say(f"{recalc['rol_sin_p3']} navegadores con rol y sin P3: no cuentan como «No»", style=DIM)
        print()
        stage("INVARIANTES", f"{DIM}código, sin modelo{RESET}")
        invariants = check_invariants(ask, recalc)
        render_checks(invariants)
        print()
        stage("JUICIO", f"{DIM}AI_COMPLETE con salida tipada{RESET}")
        try:
            if MOCK:
                pause(0.8)
                model_v = validate_verdict(model_out)
            else:
                raw, model_name = ai_complete_json(sf, judge_prompt(ask, recalc, invariants), JUDGE_SCHEMA)
                model_v = validate_verdict(raw)
            say(f"modelo: {model_name}", style=DIM)
        except (ValueError, StageError) as exc:
            log.error("judge model failed: %s", exc)
            model_v = {"veredicto": "revisar", "evidencia": [], "motivo": f"el juez de IA no produjo una salida válida ({str(exc)[:80]})"}
            say("el modelo no produjo una salida válida: veredicto «revisar»", style=ORANGE)
    finally:
        if sf:
            sf.close()
    final, reasons = combine(model_v, invariants)
    print()
    stage("VEREDICTO")
    verdict_card(final)
    if final["veredicto"] != model_v["veredicto"]:
        say(f"El modelo dijo «{model_v['veredicto']}». El código lo degradó a «{final['veredicto']}»:", style=ORANGE)
        for r in reasons:
            say(f"· {r}", indent=5, style=ORANGE)
    elif reasons:
        say("Con invariantes fallidas el veredicto no puede ser «pasa»:", style=ORANGE)
        for r in reasons:
            say(f"· {r}", indent=5, style=ORANGE)
    print()
    c = VERDICT_ANSI[final["veredicto"]]
    unlock = "desbloquea Act" if final["veredicto"] == "pasa" else "Act queda bloqueado"
    print(f"   {c}{BOLD}██ {final['veredicto'].upper()} ██{RESET}  {DIM}{unlock}{RESET}\n")
    write_json(LAST_JUDGE, {
        "mock": MOCK, "grupo": ask.get("grupo"), "corte_utc": ask["corte_utc"], "ts": utc_iso(),
        "veredicto": final["veredicto"], "evidencia": final["evidencia"], "motivo": final["motivo"],
        "veredicto_modelo": model_v["veredicto"], "degradado_por": reasons,
        "invariantes": invariants, "recalculo": recalc,
    })
    return 0


# ---------------------------------------------------------------------------
# ACT: el modelo propone, la aplicacion valida/ejecuta
# ---------------------------------------------------------------------------

def act_prompt(pedido: str, code: str) -> str:
    tools = "\n".join(f"- {name}: {desc}" for name, desc in ALLOWLIST.items())
    return textwrap.dedent(f"""\
        Eres el planificador de una aplicación. Propones UNA acción; la aplicación decide si se ejecuta.
        Herramientas que la aplicación ejecuta (lista permitida):
        {tools}
        Código del grupo de encuesta actual: {code}

        Pedido del usuario: «{pedido}»

        Si el pedido corresponde a una herramienta de la lista, usa su nombre exacto y como objetivo el
        código del grupo. Si el pedido pide otra cosa, propón de todos modos lo que el usuario pide, con un
        nombre descriptivo en snake_case (por ejemplo borrar_votos), y deja que la aplicación valide.
        El motivo es una frase en español.""")


def propose_action(pedido: str, code: str) -> tuple[dict, str]:
    if MOCK:
        low = _norm(pedido)
        name = "harness_act_borrar.json" if re.search(r"borr|elimin|vaci|delete|purg", low) else "harness_act_cerrar.json"
        fx = load_fixture(name)
        pause(0.8)
        prop = dict(fx["propuesta"])
        if prop.get("accion") in ALLOWLIST:
            prop["objetivo"] = code
        return prop, "ensayo"
    sf = SfSession()
    try:
        raw, model = ai_complete_json(sf, act_prompt(pedido, code), ACT_SCHEMA)
    finally:
        sf.close()
    prop = {k: str(raw.get(k, "")).strip() for k in ("accion", "objetivo", "motivo")}
    return prop, model


def new_client() -> httpx.Client:
    return httpx.Client(transport=TRANSPORT, timeout=httpx.Timeout(20.0, connect=10.0), follow_redirects=False,
                        headers={"User-Agent": "Mozilla/5.0 (compatible; swt-demo-harness/1.0)"})


def summarize_group(payload: dict) -> dict:
    g = payload.get("group") or {}
    return {"id": g.get("id"), "code": g.get("code"), "title": g.get("title"),
            "polls": [{"question": p.get("question"), "status": p.get("status"), "total": p.get("total")}
                      for p in g.get("polls") or []]}


def fetch_group(client: httpx.Client, base: str, code: str) -> dict:
    """Estado publico del grupo (GET sin credenciales)."""
    try:
        r = client.get(f"{base}/api/polls/public/groups/{code}")
    except httpx.HTTPError as exc:
        log.exception("fetch_group failed")
        raise StageError(f"no se pudo leer el estado del grupo en {urlsplit(base).netloc} ({type(exc).__name__})") from None
    if r.status_code == 404:
        raise StageError(f"el grupo {code} no existe en {urlsplit(base).netloc}")
    if r.status_code != 200:
        raise StageError(f"h1sort.com respondió HTTP {r.status_code} al leer el grupo")
    return summarize_group(r.json())


def execute_close(client: httpx.Client, base: str, group_id: str) -> dict:
    """login admin + PATCH {status: closed}. Origin obligatorio; la cookie queda en el cliente."""
    origin = "{0.scheme}://{0.netloc}".format(urlsplit(base))
    user, pw = env("POLLS_ADMIN_USERNAME", required=True), env("POLLS_ADMIN_PASSWORD", required=True)
    try:
        r = client.post(f"{base}/api/polls/auth/login", json={"username": user, "password": pw},
                        headers={"Origin": origin})
        if r.status_code != 200:
            hint = {401: "credenciales inválidas", 429: "demasiados intentos, espera unos minutos",
                    403: "origen rechazado"}.get(r.status_code, "respuesta inesperada")
            raise StageError(f"login de administrador falló (HTTP {r.status_code}): {hint}")
        r = client.patch(f"{base}/api/polls/admin/groups/{group_id}", json={"status": "closed"},
                         headers={"Origin": origin})
    except httpx.HTTPError as exc:
        log.exception("execute_close failed")
        raise StageError(f"no se pudo contactar a {urlsplit(base).netloc} ({type(exc).__name__})") from None
    try:
        updated = r.json().get("updated")
    except ValueError:
        updated = None
    return {"http_status": r.status_code, "updated": updated, "path": f"/api/polls/admin/groups/{group_id}"}


def validation_steps(prop: dict, code: str, ask: dict | None, judge: dict | None, state: dict,
                     lookup: Any) -> Iterator[dict]:
    """Reglas del contrato en orden; se detiene en la primera que falla. `lookup()` hace el GET publico."""
    accion = str(prop.get("accion", "")).strip()
    ok = accion in ALLOWLIST
    yield {"ok": ok, "titulo": "herramienta en la lista permitida",
           "detalle": accion if ok else f"«{accion or '(vacía)'}» no existe: la lista permitida es {', '.join(ALLOWLIST)}"}
    if not ok:
        return
    objetivo = str(prop.get("objetivo", "")).strip()
    ok = objetivo.upper() == code.upper()
    yield {"ok": ok, "titulo": "objetivo = grupo de esta sesión",
           "detalle": code if ok else f"«{objetivo or '(vacío)'}» no es el grupo de esta sesión"}
    if not ok:
        return
    reason, ok = "", True
    if judge is None:
        ok, reason = False, "no hay veredicto: corre «judge» primero"
    elif bool(judge.get("mock")) != MOCK:
        ok, reason = False, "el veredicto es " + ("de ensayo" if judge.get("mock") else "real") + " y esta ejecución no"
    elif (ask and judge.get("corte_utc") != ask.get("corte_utc")) or str(judge.get("grupo", "")).upper() != code.upper():
        ok, reason = False, "el veredicto no corresponde a la última consulta: vuelve a correr «judge»"
    elif judge.get("veredicto") != "pasa":
        ok, reason = False, f"último veredicto: «{judge.get('veredicto')}»; solo «pasa» desbloquea Act"
    yield {"ok": ok, "titulo": "último veredicto del Judge = pasa", "detalle": "pasa" if ok else reason}
    if not ok:
        return
    info = lookup()
    state["group"] = info
    open_polls = [p for p in info["polls"] if p.get("status") == "open"]
    ok = bool(open_polls)
    yield {"ok": ok, "titulo": "el grupo está abierto ahora",
           "detalle": f"{len(open_polls)} de {len(info['polls'])} preguntas abiertas" if ok else "ya está cerrado: no hay nada que cerrar"}


def append_receipt(receipt: dict) -> Path:
    path = RECEIPTS_MOCK if MOCK else RECEIPTS
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    return path


def confirm(prompt: str = "¿Aprobar? [s/N] ") -> bool:
    try:
        answer = input(f"   {BOLD}{prompt}{RESET}")
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer.strip().lower() in {"s", "si", "sí", "y", "yes"}


def reject(reason: str, touched_site: bool = False) -> int:
    print()
    print(f"{ORANGE}{BOLD}RECHAZADA · sin efecto{RESET}")
    say(reason, style=ORANGE)
    say("Solo se leyó el estado público del grupo; nada se modificó." if touched_site
        else "No hubo ninguna llamada a h1sort.com.", style=DIM)
    print()
    log.info("act rechazada: %s", reason)
    return 0


def cmd_act(args: argparse.Namespace) -> int:
    code = group_code()
    banner("ACT · el modelo propone, la aplicación ejecuta")
    pedido = (args.pedido or "").strip()
    if not pedido:
        try:
            pedido = input(f"{BOLD}tú › {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
    if not pedido:
        raise StageError("falta el pedido (--pedido \"...\")")
    stage("PEDIDO", f"«{pedido}»")
    print()
    prop, model = propose_action(pedido, code)
    stage("SOLICITUD", f"{DIM}propuesta del modelo · {model}{RESET}")
    console.print(Panel(Text(json.dumps(prop, ensure_ascii=False, indent=2), style="#af5fd7"), border_style="#af5fd7",
                        padding=(1, 2), width=min(console.width, 78)))
    print()
    ask = read_json(LAST_ASK) if LAST_ASK.is_file() else None
    judge = read_json(LAST_JUDGE) if LAST_JUDGE.is_file() else None
    base = h1sort_base()
    client = None if MOCK else new_client()
    state: dict = {}

    def lookup() -> dict:
        if MOCK:
            pause(0.4)
            return load_fixture("harness_act_cerrar.json")["grupo_antes"]
        return fetch_group(client, base, code)

    try:
        stage("VALIDACIÓN", f"{DIM}reglas de la aplicación, no del modelo{RESET}")
        for step in validation_steps(prop, code, ask, judge, state, lookup):
            mark = f"\033[32m✓{RESET}" if step["ok"] else f"{ORANGE}✕{RESET}"
            print(f"   {mark} {BOLD}{step['titulo']}{RESET}")
            if step["ok"]:
                print(f"       {DIM}{step['detalle']}{RESET}")
            pause(0.4)
            if not step["ok"]:
                return reject(step["detalle"], touched_site="group" in state)
        info = state["group"]
        n_open = sum(1 for p in info["polls"] if p.get("status") == "open")
        print()
        stage("APROBACIÓN", f"cerrará {BOLD}{n_open} preguntas{RESET} del grupo {code} y publicará los resultados")
        if args.dry_run:
            print()
            stage("DRY-RUN", "se detiene antes del PATCH")
            say(f"PATCH {base}/api/polls/admin/groups/{str(info['id'])[:8]}…  {{\"status\": \"closed\"}}", style=DIM)
            say("no se pidió aprobación ni se hizo login", style=DIM)
            return 0
        if not confirm():
            print()
            print(f"{ORANGE}{BOLD}RECHAZADA · sin efecto{RESET}")
            say("No aprobada por el humano.", style=ORANGE)
            say("El humano dijo que no. No hubo ninguna llamada de escritura.", style=DIM)
            return 0
        print()
        stage("EJECUCIÓN", f"login de administrador · PATCH grupo {str(info['id'])[:8]}… {{\"status\": \"closed\"}}")
        if MOCK:
            fx = load_fixture("harness_act_cerrar.json")
            pause(1.0)
            result = {"http_status": fx["recibo"]["http_status"], "updated": fx["recibo"]["updated"],
                      "path": f"/api/polls/admin/groups/{info['id']}"}
            after = fx["grupo_despues"]
        else:
            result = execute_close(client, base, info["id"])
            try:
                after = fetch_group(client, base, code)
            except StageError:
                after = None
        ts = utc_iso()
        ok = result["http_status"] == 200
        print()
        stage("OBSERVACIÓN", f"HTTP {BOLD}{result['http_status']}{RESET} · updated {BOLD}{result['updated']}{RESET} · {ts}")
        if after and ok:
            totals = " · ".join(f"P{i + 1} {p.get('total')}" for i, p in enumerate(after["polls"]) if p.get("total") is not None)
            if all(p.get("status") == "closed" for p in after["polls"]):
                say("Verificado en el endpoint público: todas las preguntas cerradas.")
                if totals:
                    say(f"Votos publicados en los teléfonos: {totals}")
            else:
                say("Atención: el endpoint público aún muestra preguntas abiertas.", style=ORANGE)
        elif not ok:
            say("El servidor no confirmó el cierre; no se asume que ocurrió.", style=ORANGE)
        receipt = {
            "ts": ts, "mock": MOCK, "ok": ok, "accion": "cerrar_encuesta", "grupo": code, "group_id": info["id"],
            "request": {"method": "PATCH", "path": result["path"], "body": {"status": "closed"}},
            "http_status": result["http_status"], "updated": result["updated"],
            "aprobado_por": "humano", "veredicto_previo": judge.get("veredicto") if judge else None,
            "verificacion": [p.get("status") for p in after["polls"]] if after else None,
        }
        path = append_receipt(receipt)
        print()
        stage("RECIBO", f"{DIM}añadido a {rel(path)}{RESET}")
        print()
        return 0 if ok else 1
    finally:
        if client:
            client.close()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def setup_logging() -> None:
    log.handlers.clear()
    log.setLevel(logging.INFO)
    log.propagate = False
    try:
        handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(handler)
    except OSError:
        log.addHandler(logging.NullHandler())


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--mock", action="store_true", default=argparse.SUPPRESS,
                        help="ensayo sin red: usa demo/fixtures/harness_*.json")
    p = argparse.ArgumentParser(prog="stage.py", description="Ask · Judge · Act en escena", parents=[common])
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ask", parents=[common], help="consulta al Cortex Agent")
    a.add_argument("--pregunta", help="reemplaza la pregunta por defecto")
    sub.add_parser("judge", parents=[common], help="invariantes + veredicto tipado")
    c = sub.add_parser("act", parents=[common], help="propuesta, validación, aprobación, ejecución")
    c.add_argument("--pedido", help="pedido en español, p. ej. \"Cierra la encuesta y publica los resultados\"")
    c.add_argument("--dry-run", action="store_true", help="se detiene antes del PATCH")
    return p


def main(argv: list[str] | None = None) -> int:
    global MOCK
    args = build_parser().parse_args(argv)
    MOCK = bool(getattr(args, "mock", False))
    load_dotenv(DEMO_DIR / ".env")
    setup_logging()
    log.info("cmd=%s mock=%s", args.cmd, MOCK)
    try:
        return {"ask": cmd_ask, "judge": cmd_judge, "act": cmd_act}[args.cmd](args)
    except StageError as exc:
        log.error("StageError: %s", redact(str(exc)))
        print(f"\n{ORANGE}{BOLD}ERROR ›{RESET} {redact(str(exc))}")
        print(f"{DIM}  Plan B: repite con --mock (ensayo) o usa la grabación.{RESET}\n")
        return 1
    except KeyboardInterrupt:
        print(f"\n{DIM}cancelado{RESET}")
        return 130
    except Exception as exc:  # noqa: BLE001
        log.exception("error inesperado")
        print(f"\n{ORANGE}{BOLD}ERROR ›{RESET} fallo inesperado ({type(exc).__name__}). Detalle en demo/harness/stage.log")
        print(f"{DIM}  Plan B: repite con --mock (ensayo) o usa la grabación.{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
