# Cortex Agent por REST con PAT · ejemplos y eventos a parsear

Referencias (todas leídas en oct 2026):
- Run API: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-run
- Autenticación REST con PAT: https://docs.snowflake.com/en/developer-guide/snowflake-rest-api/authentication
- Permisos del agente: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-setup
- Cambio de abril 2026 (`system_execute_sql`): https://docs.snowflake.com/en/release-notes/2026/other/2026-04-13-cortex-agents-agentic-analyst

> Estado: la **forma de los eventos** sale de la documentación; no se ejecutó contra una cuenta. Parsear de forma **tolerante** (abajo) y probar hoy con el `curl` de este archivo; guarda una respuesta real como fixture para `--mock`.

## 1. Variables

```bash
export SNOWFLAKE_ACCOUNT=MIORG-MICUENTA          # ORG-CUENTA (lo imprime 00_setup.sql)
export SNOWFLAKE_PAT='...'                       # PAT SWT_PAT_AGENT (rol SWT_AGENT_RO)
# host: minúsculas y guiones bajos -> guiones
export SF_HOST="$(echo "$SNOWFLAKE_ACCOUNT" | tr '[:upper:]_' '[:lower:]-').snowflakecomputing.com"
export AGENT_URL="https://${SF_HOST}/api/v2/databases/SWT_DEMO/schemas/SEM/agents/AGENTE_ENCUESTA:run"
```

## 2. Llamada sin streaming (recomendada para el harness)

`stream:false` devuelve **un solo JSON** (el mismo objeto del último evento `response`): más fácil de parsear y de guardar como fixture. Si quieres ver la respuesta "escribiéndose" en pantalla, usa el modo streaming (sección 4) y toma el resultado del evento final.

```bash
cat > /tmp/swt_body.json <<'JSON'
{
  "stream": false,
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text",
         "text": "Por rol, ¿qué porcentaje le daría a un agente permiso de actuar en producción? Solo cuenta a quien respondió rol y P3."}
      ]
    }
  ]
}
JSON

curl -sS --max-time 120 -X POST "$AGENT_URL" \
  -H "Authorization: Bearer ${SNOWFLAKE_PAT}" \
  -H "X-Snowflake-Authorization-Token-Type: PROGRAMMATIC_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d @/tmp/swt_body.json | tee /tmp/swt_agent_response.json | python3 -m json.tool | head -120
```

Notas:
- `X-Snowflake-Authorization-Token-Type` es opcional (Snowflake deduce el tipo); se manda por claridad.
- El rol sale del PAT (`ROLE_RESTRICTION = SWT_AGENT_RO`) y el agente evalúa permisos con el **rol por defecto** de `SWT_DEMO_USER` (también `SWT_AGENT_RO`). No hay encabezado de rol.
- Un solo turno: no mandes `thread_id` ni `parent_message_id` (si usas hilos, la doc exige ambos y `parent_message_id: 0` en el primer mensaje).
- El endpoint del agente nombrado **no** acepta `models`, `instructions` ni `orchestration` en el cuerpo: viven en el objeto agente (`03_agent.sql`).
- Timeout del cliente: ≥ 90 s (el `budget` del agente es 90 s). Calentar antes de salir al escenario.

## 3. Forma de la respuesta no-streaming

Objeto con `role` ("assistant"), `content[]`, `status` ("completed" | "cancelled" | "timed_out"), `warnings[]`, `metadata{run_id,...}`. Cada elemento de `content[]` tiene `type`:

| `type` | Qué es | Dónde está lo útil |
|---|---|---|
| `thinking` | razonamiento del modelo | **ignorar** |
| `tool_use` (`name` / `type` = `system_execute_sql`, o `cortex_analyst_text_to_sql` en versiones anteriores) | el SQL que el agente va a ejecutar | `tool_use.input.sql` |
| `tool_result` (mismo `type`/`name`) | resultado de la consulta | `tool_result.content[0].json` = `{query_id, result_set, sql}` |
| `table` | tabla de resultados (puede o no aparecer) | `table.result_set` |
| `chart` | gráfica Vega-Lite (no se usa) | ignorar |
| `text` | **texto final** (y a veces texto intermedio) | `text` |

`result_set`:

```json
{ "statementHandle": "<query_id>",
  "resultSetMetaData": {"format": "jsonv2", "numRows": 2, "partition": 0, "rowType": [{"name": "ROL", "type": "text", "...": "..."}]},
  "data": [["Negocio", "3", "5", "0.6", "2026-10-13 ..."], ["Ingeniería", "..."]] }
```

- `data` es **matriz de strings** (jsonv2): convertir números en el harness. `rowType` puede venir o no; si no, el orden de columnas es el de la proyección del SQL.
- **La doc es inconsistente sobre el anidamiento**: unos ejemplos ponen los campos planos en el item y otros dentro de una clave con el nombre del tipo (`{"type":"tool_use","tool_use":{...}}`, `{"type":"text","text":"..."}`). Normaliza siempre con `body = item.get(item["type"], item)` y busca con `.get`.
- Si no hay tabla en un `table` item, saca la tabla del `tool_result` (`json.result_set`).

### Parser tolerante (Python)

```python
def parse_agent_response(resp: dict) -> dict:
    """resp = JSON no-streaming (o el payload del evento SSE `response`)."""
    out = {"text": "", "sql": [], "tables": [], "query_ids": [],
           "status": resp.get("status"), "warnings": resp.get("warnings") or [],
           "run_id": (resp.get("metadata") or {}).get("run_id")}
    texts = []
    for item in resp.get("content") or []:
        t = item.get("type")
        body = item.get(t, item) if isinstance(item.get(t), dict) else item
        if t == "text":
            texts.append(item.get("text") or body.get("text") or "")
        elif t == "tool_use":
            sql = (body.get("input") or {}).get("sql")
            if sql: out["sql"].append(sql)
        elif t == "tool_result":
            for c in body.get("content") or []:
                j = c.get("json") if c.get("type") == "json" else None
                if not isinstance(j, dict):
                    continue
                if j.get("sql"): out["sql"].append(j["sql"])
                if j.get("query_id"): out["query_ids"].append(j["query_id"])
                if isinstance(j.get("result_set"), dict): out["tables"].append(j["result_set"])
        elif t == "table":
            rs = body.get("result_set")
            if isinstance(rs, dict): out["tables"].append(rs)
    out["text"] = texts[-1] if texts else ""      # el texto FINAL es el último item `text`
    out["sql_final"] = out["sql"][-1] if out["sql"] else None   # el último SQL ejecutado
    return out
```

Qué mostrar en pantalla (fases de la demo): `text` (respuesta con numeradores/denominadores y "Corte de datos"), `sql_final` (el SQL que corrió) y la tabla `tables[-1]`. Si hay varias consultas, el agente suele terminar con la que respalda el texto, pero recalcula tú el denominador con tu propio SQL sobre `SEM.RESPUESTAS` (parte del Judge).

Errores a manejar: HTTP 401 con `PAT_INVALID` (token), HTTP 4xx/5xx con JSON de error, `status != "completed"`, `warnings` con `code` 399569 (el rol no puede acceder a una herramienta → el agente respondió sin ella: **tratar como fallo**), `content` sin ningún `text`.

## 4. Streaming (opcional)

```bash
curl -sS -N --max-time 120 -X POST "$AGENT_URL" \
  -H "Authorization: Bearer ${SNOWFLAKE_PAT}" \
  -H "X-Snowflake-Authorization-Token-Type: PROGRAMMATIC_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"stream": true, "messages": [{"role":"user","content":[{"type":"text","text":"¿Cuántos navegadores respondieron rol y P3?"}]}]}'
```

SSE: líneas `event: <nombre>` y `data: <json>`, separadas por línea en blanco. Eventos documentados (ignorar los desconocidos: la doc lo exige):

| Evento | Campos clave | Qué hacer |
|---|---|---|
| `response.status` | `status`, `message` (p.ej. "Planning the next steps") | Mostrar como etiqueta de progreso (opcional) |
| `response.thinking.delta` / `response.thinking` | `text` | Ignorar |
| `response.tool_use` | `tool_use_id`, `type`, `name`, `input` | Guardar `input.sql` si existe (en streaming no está confirmado que venga; si no, el SQL llega en el evento final) |
| `response.tool_result.status` | `tool_use_id`, `status`, `message` | Progreso (opcional) |
| `response.tool_result` | `tool_use_id`, `name`, `content[]` (`{"type":"json","json":{...}}`), `status` | Extraer `json.sql`, `json.query_id`, `json.result_set` |
| `response.tool_result.analyst.delta` | `delta{text, sql, query_id, result_set, ...}` | Solo con el tipo anterior `cortex_analyst_text_to_sql` |
| `response.table` | `tool_use_id`, `query_id`, `result_set`, `title` | Tabla de resultados |
| `response.text.delta` | `content_index`, `text` | Pintar en vivo (concatenar por `content_index`) |
| `response.text` | `content_index`, `text` (completo del bloque) | Texto de un bloque ya terminado |
| `response.warning` | `message`, `code` | Registrar; 399569 = herramienta inaccesible |
| `error` | `code`, `message`, `request_id` | Abortar la fase con mensaje en rojo |
| `metadata` | `role`, `message_id`, `run_id` | Guardar `run_id` en el recibo/auditoría |
| **`response`** (último) | `role`, `content[]`, `warnings`, `metadata`, `status` | **Fuente de verdad**: pasarlo a `parse_agent_response` |

Regla práctica: usa los `*.delta` solo para mostrar progreso y **construye el resultado final siempre del evento `response`** (misma forma que la sección 3). Si la conexión se corta antes de `response`, trátalo como fallo (no uses texto parcial como respuesta).

## 5. Alternativa por SQL (misma respuesta, sin streaming)

```sql
SELECT TRY_PARSE_JSON(SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
  'SWT_DEMO.SEM.AGENTE_ENCUESTA',
  $${"messages":[{"role":"user","content":[{"type":"text","text":"..."}]}]}$$));
```

Útil como respaldo si el REST falla pero el conector SQL funciona (`stream: true` da error en esta función). Doc: https://docs.snowflake.com/en/sql-reference/functions/data_agent_run-snowflake-cortex . Ver `04_checks.sql` parte C.

## 6. Judge y Act con AI_COMPLETE (SQL, mismo PAT/rol)

Esquema del Judge (contrato) para `response_format`:

```sql
response_format => {
  'type': 'json',
  'schema': {
    'type': 'object',
    'properties': {
      'veredicto': {'type': 'string', 'enum': ['pasa', 'revisar', 'rechazar']},
      'evidencia': {'type': 'array', 'items': {'type': 'string'}},
      'motivo':    {'type': 'string'}
    },
    'required': ['veredicto', 'evidencia', 'motivo'],
    'additionalProperties': false
  }
}
```

Con `show_details` omitido el resultado es el propio JSON; pasarlo por `TRY_PARSE_JSON(resultado::STRING)` y **validar siempre en código** (la salida válida no es necesariamente correcta). Con `show_details => TRUE` el JSON viene envuelto en `structured_output[].raw_message`. No usar `minLength`, `maxLength`, `minimum`, `maximum` ni `minItems` en el esquema (error 400). Un error 422 significa que la salida del modelo no cumplió el esquema. Doc: https://docs.snowflake.com/en/user-guide/snowflake-cortex/complete-structured-outputs
