# Harness en escena: Ask · Judge · Act

Un solo script, `demo/harness/stage.py` (uv, sin instalar nada): corre en la laptop de Carlos y
produce la salida grande y corta que se proyecta en las diapositivas 8, 9 y 10.

```
uv run demo/harness/stage.py ask                # diapositiva 8
uv run demo/harness/stage.py judge              # diapositiva 9
uv run demo/harness/stage.py act --pedido "…"   # diapositiva 10
uv run demo/harness/stage.py --mock <comando>   # ensayo / último recurso: [MODO ENSAYO]
```

## Antes de la charla

1. `demo/.env` completo (ver `demo/.env.example`). Para el harness: `GROUP_CODE`, `SNOWFLAKE_ACCOUNT`,
   `SNOWFLAKE_USER`, `SNOWFLAKE_PAT` (el PAT con `ROLE_RESTRICTION = 'SWT_AGENT_RO'`, no el del loader),
   `POLLS_ADMIN_USERNAME`, `POLLS_ADMIN_PASSWORD`. Opcionales: `CORTEX_MODEL` (por defecto `claude-sonnet-5`),
   `CORTEX_MODEL_FALLBACK` (`claude-sonnet-4-5`), `H1SORT_BASE`.
2. Terminal con letra grande (⌘+ hasta que ~66 columnas llenen el ancho), fondo oscuro, `cd` a la raíz del repo.
3. Prueba sin red (30 s): `uv run demo/harness/stage.py --mock ask && uv run demo/harness/stage.py --mock judge && uv run demo/harness/stage.py --mock act --pedido "Cierra la encuesta y publica los resultados"` (responde `s`).
4. Prueba real con datos de prueba (votos de tu teléfono), **sin cerrar nada**:
   `ask`, `judge`, `act --dry-run --pedido "Cierra la encuesta y publica los resultados"`.
   El `--dry-run` valida y se detiene antes del login y del PATCH.
5. El grupo debe estar **abierto** (3 preguntas OPEN) al empezar el Act: la regla 4 lo comprueba.
6. Pruebas automáticas: `uv run demo/harness/test_stage.py` (49 pruebas, sin red).

## En escena (secuencia exacta)

Los votos ya terminaron para este momento (diapositiva 3 fue hace más de 4 minutos). Si siguen llegando votos
mientras corre el Judge, el recálculo puede diferir y el código degradará a «revisar»: es el comportamiento correcto.

### Diapositiva 8 · Ask (4:35–7:35)

```
uv run demo/harness/stage.py ask
```

Muestra: el **corte UTC** fijado antes de preguntar, la pregunta, el **SQL** que ejecutó el agente, la **tabla**
(numerador, denominador, porcentaje por rol) y la **respuesta**. Señala: denominadores (quien omitió P3 no es un
«No»), el SQL, el corte y los grupos con «muestra insuficiente». Si la muestra es chica, dilo.
Otra pregunta: `ask --pregunta "…"`. Guarda `demo/harness/.last_ask.json`.

### Diapositiva 9 · Judge (7:35–9:20)

```
uv run demo/harness/stage.py judge
```

Orden en pantalla: **RECÁLCULO** (SQL propio como `SWT_AGENT_RO`) → **INVARIANTES** (4 ✓/✕ en código) →
**JUICIO** (AI_COMPLETE, salida tipada) → **VEREDICTO** (tarjeta JSON + `PASA | REVISAR | RECHAZAR`).
Si el modelo dice «pasa» pero una invariante falla, la pantalla dice «El código lo degradó a revisar».
Solo `pasa` desbloquea Act. Guarda `demo/harness/.last_judge.json`.

### Diapositiva 10 · Act (9:20–11:35)

```
uv run demo/harness/stage.py act --pedido "Borra los votos incompletos"
```
Esperado: `SOLICITUD` (el modelo propone `borrar_votos`) → `VALIDACIÓN ✕ herramienta en la lista permitida` →
`RECHAZADA · sin efecto` y «No hubo ninguna llamada a h1sort.com». No existe la herramienta.

```
uv run demo/harness/stage.py act --pedido "Cierra la encuesta y publica los resultados"
```
Esperado: `SOLICITUD` (`cerrar_encuesta`, objetivo = el grupo) → `VALIDACIÓN` 4 ✓ → `APROBACIÓN`
`¿Aprobar? [s/N]` → **Carlos escribe `s` y Enter** (pausa: es el clímax) → `EJECUCIÓN` (login + PATCH) →
`OBSERVACIÓN` (HTTP 200 · updated 3 · hora UTC; verificación en el endpoint público y votos por pregunta) →
`RECIBO` (se añade a `demo/receipts.jsonl`). Los resultados aparecen en los teléfonos.

Las cuatro reglas de validación, en este orden (se detiene en la primera que falla):
1. la herramienta es exactamente `cerrar_encuesta`;
2. el objetivo es el `GROUP_CODE` de la sesión;
3. el último veredicto del Judge es `pasa` (y es de esta misma consulta y no es de ensayo);
4. el grupo está abierto ahora (`GET /api/polls/public/groups/<codigo>`; única llamada a h1sort.com antes del PATCH).

## Ensayo y último recurso: `--mock`

`--mock` no abre red y lee `demo/fixtures/harness_ask.json`, `harness_judge.json`, `harness_act_cerrar.json`,
`harness_act_borrar.json`. Todo lo que imprime lleva `[MODO ENSAYO]`. Las invariantes y las reglas de
validación corren con el código real sobre los datos del fixture. Un pedido con «borr», «elimin» o «vaci» usa
la propuesta rechazada; cualquier otro usa `cerrar_encuesta`. Los recibos de ensayo van a
`demo/receipts.mock.jsonl`, nunca a `receipts.jsonl`. Un veredicto de ensayo **no** desbloquea un Act real
(ni al revés). `--mock` va antes o después del comando.

Si usas `--mock` en vivo, dilo: «esto es un ensayo con datos de ejemplo». Nunca presentes un resultado de ensayo
como real; la alternativa honesta es la grabación etiquetada.

Para ensayar la degradación: `--mock ask`, edita un denominador en `demo/harness/.last_ask.json`, y corre
`--mock judge`: el modelo (canned) dice «pasa» y el código lo baja a «revisar».

## Si falla

El script nunca muestra un traceback: imprime una línea `ERROR › …` en español (el detalle va a
`demo/harness/stage.log`). Secretos y `VOTER_KEY` nunca se imprimen.

| Síntoma en pantalla | Causa probable | Qué hacer |
|---|---|---|
| `Cortex Agents respondió HTTP 401` | PAT vencido/mal copiado, o sin política de red | Revisa `SNOWFLAKE_PAT` (vigencia 3 días); si no se arregla en 30 s: grabación |
| `HTTP 403 … USAGE sobre el agente` | PAT sin rol `SWT_AGENT_RO` o falta `GRANT USAGE ON AGENT` | Ejecuta los grants de `demo/snowflake/` |
| `HTTP 404 … no existe el agente` | Agente no creado o nombre distinto | `demo/snowflake/03_agent.sql` |
| `el agente no devolvió SQL ni respuesta` | Modelo del agente no disponible en la región | Cambia `orchestration:` en `03_agent.sql` (fallback documentado) |
| `la sesión corre como X, no como SWT_AGENT_RO` | El PAT no está restringido al rol de solo lectura | El harness se detiene a propósito; usa el PAT del agente |
| `AI_COMPLETE no respondió` | Modelo sin cross-region inference | Define `CORTEX_MODEL` con uno disponible (ver `04_checks.sql` B4); el fallback se prueba solo |
| Judge: `✕ denominador`, `✕ corte visible`… | El agente respondió mal o con otro formato | Es el sistema funcionando: lee la invariante, vuelve a correr `ask` |
| Judge: `REVISAR` sin invariantes fallidas | El modelo dudó | Léelo y repite `ask`; no fuerces `pasa` |
| `RECHAZADA · sin efecto … ya está cerrado` | Alguien (o un ensayo real) ya cerró el grupo | Reabre el grupo desde el admin de h1sort.com |
| `login de administrador falló (HTTP 401/429)` | Credenciales o demasiados intentos | Revisa `POLLS_ADMIN_*`; si es 429, espera ~minutos o usa grabación |
| `el servidor no confirmó el cierre` | PATCH ≠ 200 | No se asume que ocurrió; el recibo queda con `ok: false` |
| Cualquier otra cosa | Red del salón | `--mock` con aviso al público, o la grabación etiquetada |

Una ejecución real que cierre el grupo no se puede ensayar dos veces sin reabrirlo: para repetir el Act real,
reabre las tres preguntas en el admin y vuelve a correr `ask` y `judge` (el veredicto debe ser de la última consulta).
