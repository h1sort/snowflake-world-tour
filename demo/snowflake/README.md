# demo/snowflake · lado Snowflake de la demo Ask · Judge · Act

Todo se escribió contra la documentación vigente de octubre 2026 (ver "Qué se verificó"). **Nada se ejecutó contra una cuenta real**: no había cuenta disponible. Ejecuta el orden de abajo **hoy**, en ensayo, y no por primera vez mañana a las 10:45.

## Orden de ejecución

| # | Archivo | Rol | Qué hace |
|---|---|---|---|
| 0 | `00_setup.sql` | `ACCOUNTADMIN` | Roles `SWT_OWNER`, `SWT_LOADER`, `SWT_AGENT_RO`; warehouse `SWT_WH` (XSMALL, suspensión 60 s); base `SWT_DEMO` con esquemas `RAW`, `SEM`, `GOV`; usuario de servicio `SWT_DEMO_USER`; política de autenticación para PAT; GRANT de mínimo privilegio; consulta tu parámetro de cross-region inference. Termina imprimiendo el identificador de cuenta. La sección 9 (crear PAT) es **manual**. |
| 1 | `01_raw.sql` | `SWT_OWNER` | Las cuatro tablas RAW del contrato + `SELECT/INSERT/UPDATE` para el loader. |
| 2 | `02_sem.sql` | `SWT_OWNER` | Vista `SEM.RESPUESTAS` (pivote por `ORDINAL`, NULL si no respondió) y vista semántica `SEM.ENCUESTA_SWT`; SELECT para `SWT_AGENT_RO`. |
| 3 | `03_agent.sql` | `SWT_OWNER` | Agente `SEM.AGENTE_ENCUESTA` (Claude + una herramienta Cortex Analyst sobre la vista semántica, instrucciones en español); USAGE para `SWT_AGENT_RO`. |
| 4 | `04_checks.sql` | varios (el script cambia de rol) | Pruebas de humo con datos sintéticos. Parte A (transacción con ROLLBACK, segura), B (rol de solo lectura y AI_COMPLETE), C (agente por SQL, solo ensayo), D (limpieza). |
| 5 | `05_reset.sql` | `SWT_OWNER` | Vacía RAW entre ensayo y charla. Incluye el desmontaje comentado. |
| · | `rest_examples.md` | · | `curl` exacto del agente por REST con PAT y qué eventos parsear. |

En Snowsight ejecuta cada statement por separado (Cmd+Enter); "Run all" solo muestra el último resultado. Por CLI: `snow sql -f 00_setup.sql` imprime todo.

### Paso a paso hoy (ensayo)

1. Snowsight como `ACCOUNTADMIN` → `00_setup.sql`. Anota la fila final (`snowflake_account_para_env`, `host_rest`, `region`) y mira `SHOW PARAMETERS LIKE 'CORTEX_ENABLED_CROSS_REGION'`.
2. Crea los dos PAT (bloque 9 comentado de `00_setup.sql`, **cada `ALTER USER` por separado**). El secreto sale una sola vez: cópialo al `.env` y no lo pegues en el repo.
3. `01_raw.sql`, `02_sem.sql`, `03_agent.sql`.
4. `04_checks.sql`: A completa (todo `PASS` en A6), B completa (B2 y B3 devuelven `PASS`; B4 muestra qué Claude tienes; B5 devuelve JSON válido), y luego, **una vez**, `COMMIT` en A7 + PARTE C + PARTE D para probar el agente.
5. Prueba el REST con `rest_examples.md` desde tu laptop (es lo que usa el harness).
6. `05_reset.sql` y deja RAW vacío antes de crear el grupo real.

### Mañana, antes de subir al escenario

- `ALTER WAREHOUSE SWT_WH RESUME;` y haz **una pregunta al agente** (REST o PARTE C con el reset hecho) para calentar el modelo y el warehouse. Una primera llamada en frío puede tardar bastante más que las siguientes.
- Confirma que los PAT no expiraron (`DAYS_TO_EXPIRY = 3`).
- Si ensayaste con otro grupo: `05_reset.sql`. La vista `SEM.RESPUESTAS` usa el grupo con `CREATED_AT` más reciente en `RAW.POLL_GROUPS`, no el `GROUP_CODE` (Snowflake no conoce esa variable).

## Variables de entorno para bridge y harness

Se usa el `demo/.env.example` del contrato. Valores concretos de esta parte:

```bash
# Formato de cuenta: <ORGANIZACIÓN>-<CUENTA>  (el SELECT final de 00_setup.sql lo imprime)
SNOWFLAKE_ACCOUNT=MIORG-MICUENTA
SNOWFLAKE_USER=SWT_DEMO_USER
SNOWFLAKE_PAT=...                 # PAT SWT_PAT_AGENT, restringido a SWT_AGENT_RO (harness)
SNOWFLAKE_PAT_LOADER=...          # PAT SWT_PAT_LOADER, restringido a SWT_LOADER (puente)  <-- variable ADICIONAL
SNOWFLAKE_ROLE_LOADER=SWT_LOADER
SNOWFLAKE_ROLE_AGENT=SWT_AGENT_RO
SNOWFLAKE_WAREHOUSE=SWT_WH
CORTEX_MODEL=claude-sonnet-5      # ver "Modelo" abajo
```

Constantes (no son secretos): base `SWT_DEMO`, esquemas `RAW`/`SEM`, vista `SWT_DEMO.SEM.RESPUESTAS`, vista semántica `SWT_DEMO.SEM.ENCUESTA_SWT`, agente `SWT_DEMO.SEM.AGENTE_ENCUESTA`.

**Host REST**: `https://<cuenta>.snowflakecomputing.com` con la cuenta en **minúsculas y los guiones bajos cambiados por guiones**: `MI_ORG-MI_CUENTA` → `https://mi-org-mi-cuenta.snowflakecomputing.com`. La doc ejemplifica `https://myorganization-myaccount.snowflakecomputing.com/api/v2/...`. `00_setup.sql` imprime `host_rest` ya calculado.

### Dos PAT, no uno (importante para bridge y harness)

El contrato lista una sola `SNOWFLAKE_PAT`. Un PAT de usuario de servicio **debe** llevar `ROLE_RESTRICTION` (un solo rol), y con eso "rol de solo lectura" es literal: el PAT del harness no puede escribir aunque se filtre. Por eso hay dos PAT del mismo usuario:

- `SNOWFLAKE_PAT` → rol `SWT_AGENT_RO` (harness: REST del agente, SQL de recálculo de denominadores, `AI_COMPLETE`).
- `SNOWFLAKE_PAT_LOADER` → rol `SWT_LOADER` (puente: `MERGE` en RAW). **El puente debe leer `SNOWFLAKE_PAT_LOADER` y, si falta, caer a `SNOWFLAKE_PAT`** (y entonces fallará por permisos, que es lo correcto).
- Conector Python: la doc confirma que el PAT se pasa como `password=` en `snowflake.connector.connect(...)` (no se necesita contraseña real). El rol viene fijado por el PAT.
- Zona horaria: `SWT_DEMO_USER` queda en `UTC` (`D1.created_at` es UTC y `_LOADED_AT` usa `CURRENT_TIMESTAMP()`).

### Requisitos del puente (loader)

- Rol `SWT_LOADER`: `USAGE` en warehouse, base y `RAW`; `SELECT, INSERT, UPDATE` en las cuatro tablas. **No** tiene `DELETE`, `TRUNCATE` ni `CREATE`: usar `MERGE INTO RAW.T USING (SELECT ... FROM VALUES ...)` o con parámetros, **sin tablas temporales**.
- `RAW.POLL_OPTIONS` tiene la columna `POSITION` (también es nombre de función): en el DDL va entre comillas (`"POSITION"`), que es el mismo identificador en mayúsculas. Si alguna sentencia del puente se queja de esa columna, escríbela `"POSITION"`.
- Si el puente no pasa `_LOADED_AT`, se llena sola (`CURRENT_TIMESTAMP()`).

### Cambios al contrato (aditivos; avisar a bridge y harness)

1. `SEM.RESPUESTAS` tiene una sexta columna al final: `ULTIMA_RESPUESTA_AT` (el corte de datos correcto es el último voto, no la primera respuesta de cada navegador). Las cinco columnas del contrato no cambian.
2. `con_permiso` exige además `ROL IS NOT NULL` (con la definición literal, quien respondió P3 pero no rol inflaría el numerador por encima del denominador y se podría ver un porcentaje mayor a 100 %). El denominador es el del contrato. El harness, al recalcular, debe usar: `denominador = COUNT_IF(ROL IS NOT NULL AND PERMISO_PRODUCCION IS NOT NULL)` por rol.
3. Un rol extra, `SWT_OWNER` (dueño de objetos). `SWT_LOADER` y `SWT_AGENT_RO` son exactamente los del contrato (más `SELECT` en las tablas para poder hacer `MERGE`).
4. Variable extra `SNOWFLAKE_PAT_LOADER` (arriba).

## Modelo de Claude y regiones

| Uso | Modelo | Por qué |
|---|---|---|
| Orquestación del agente, Judge y Act (`CORTEX_MODEL`) | `claude-sonnet-5` | Disponible (GA) para agentes y `AI_COMPLETE`; cobertura *Cross Cloud*, AWS US, AWS EU, AWS APJ, AWS AU; la propia doc del REST del agente lo usa de ejemplo. |
| Plan B | `claude-sonnet-4-5` | El Claude con más cobertura regional (también AWS US Gov/FedRAMP y Azure US). |
| Plan C (solo agente) | `auto` | La doc recomienda `auto`; Snowflake elige el modelo. |

- **Todos los Claude se sirven por cross-region inference** (la página de disponibilidad no lista ninguno como nativo por región). El parámetro de cuenta `CORTEX_ENABLED_CROSS_REGION` lo cambia solo `ACCOUNTADMIN`. En organizaciones creadas después del 9-mar-2026 el valor por defecto es `ANY_REGION`; en las demás es un valor de tu misma nube (p.ej. `AWS_US`). `DISABLED` rompe todo.
- `claude-sonnet-5` **no** cubre: AWS GovCloud/FedRAMP, ni Azure/GCP salvo con `ANY_REGION` (Cross Cloud). Si tu cuenta es Azure o GCP, necesitas `ANY_REGION`.
- No se encontró ninguna mención de una región AWS de México en la página de disponibilidad. Dime cuál es la región de tu cuenta (`SELECT CURRENT_REGION()`) para afinar.
- `claude-sonnet-5-5` y `claude-opus-5-5` aparecen en **vista previa pública**; **no los uses** en la demo.

## Si algo falla

| Síntoma | Qué hacer |
|---|---|
| `AI_COMPLETE` o el agente: "model not available / unknown model" | 1) `SHOW PARAMETERS LIKE 'CORTEX_ENABLED_CROSS_REGION' IN ACCOUNT;` Si es `DISABLED` o no cubre tu nube: `ALTER ACCOUNT SET CORTEX_ENABLED_CROSS_REGION = 'ANY_REGION';` (como `ACCOUNTADMIN`). 2) Corre `04_checks.sql` B4 para ver qué Claude responde y pon ese en `CORTEX_MODEL`. 3) Para el agente cambia la línea `orchestration:` bajo `models:` en `03_agent.sql` a `claude-sonnet-4-5` o `auto` y re-ejecuta. Docs: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cross-region-inference · https://docs.snowflake.com/en/user-guide/snowflake-cortex/aisql-regional-availability |
| Error de acceso al modelo aunque el parámetro está bien | Revisa `SHOW PARAMETERS LIKE 'CORTEX_MODELS_ALLOWLIST' IN ACCOUNT;` (debe permitir el modelo; en cuentas nuevas es `All`) y que `SWT_AGENT_RO` tenga `SNOWFLAKE.CORTEX_USER` y `USE AI FUNCTIONS` (están en `00_setup.sql`). Doc: https://docs.snowflake.com/en/user-guide/snowflake-cortex/aisql-privileges-and-access |
| `CREATE SEMANTIC VIEW` da error de sintaxis | Compara con https://docs.snowflake.com/en/sql-reference/sql/create-semantic-view y https://docs.snowflake.com/en/user-guide/views-semantic/sql . Sospechosos, en orden: (1) `PRIVATE` en los hechos → quítalo; (2) error "ambiguous" por dimensiones con el mismo nombre que su columna → renombra las dimensiones (`rol` → `rol_respondido`, etc.) y el nombre en `04_checks.sql`/`AI_SQL_GENERATION`; (3) la métrica derivada `pct_permiso` → conviértela en métrica normal: `respuestas.pct_permiso AS SUM(respuestas.otorga_permiso) / NULLIF(SUM(respuestas.es_par_valido), 0)`; (4) quita `AI_SQL_GENERATION`. |
| `CREATE AGENT` falla | https://docs.snowflake.com/en/sql-reference/sql/create-agent . Un YAML mal anidado se acepta al crear pero falla al ejecutar: prueba con `04_checks.sql` parte C. Mínimo viable: deja solo `models`, `tools` y `tool_resources`. |
| Agente responde "no tengo acceso a la herramienta" / warning `399569` | El agente evalúa permisos con el **rol por defecto del usuario**: `DESC USER SWT_DEMO_USER` debe mostrar `DEFAULT_ROLE = SWT_AGENT_RO` y `DEFAULT_WAREHOUSE = SWT_WH`; y `SWT_AGENT_RO` necesita USAGE en el agente, SELECT en `ENCUESTA_SWT`, USAGE en db/esquema/warehouse. Re-ejecuta los GRANT al final de `02_sem.sql` y `03_agent.sql` (un `CREATE OR REPLACE` los borra). Doc: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-setup |
| REST 401 / `PAT_INVALID` | PAT vencido, mal copiado, usuario o rol equivocado, o el rol de la restricción ya no está concedido al usuario. Genera otro PAT. Si dice que falta network policy: confirma `ALTER USER SWT_DEMO_USER SET AUTHENTICATION POLICY = SWT_DEMO.GOV.SWT_PAT_POLICY` (o usa la Opción B de `00_setup.sql` con tu IP). Doc: https://docs.snowflake.com/en/user-guide/programmatic-access-tokens |
| REST 404 | URL: cuenta en minúsculas con guiones (no guiones bajos), ruta `/api/v2/databases/SWT_DEMO/schemas/SEM/agents/AGENTE_ENCUESTA:run` (con **dos puntos** antes de `run`). |
| `SEM.RESPUESTAS` devuelve 0 filas | ¿Cargó el puente? `SELECT COUNT(*)` en RAW como `SWT_OWNER`. ¿Hay un grupo más reciente (p.ej. restos de `smk-g`)? `SELECT ID, CODE, CREATED_AT FROM RAW.POLL_GROUPS ORDER BY CREATED_AT DESC;` y `04_checks.sql` PARTE D. ¿`ORDINAL` viene NULL? Es responsabilidad del puente. |
| El denominador no cuadra con el del harness | Un voto con etiqueta que no está en la lista (acentos / normalización Unicode): corre `04_checks.sql` A3 sobre los datos reales (0 filas = bien). |
| Fallan todos los ensayos y es la hora | Modo `--mock` de bridge/harness y la grabación etiquetada. No inventar resultados. |

## Qué se verificó (y qué no)

Fuente de verificación: lectura de las páginas oficiales en docs.snowflake.com (vía una herramienta de resumen, no se pudo hacer `curl` directo al sitio); **ninguna sentencia se ejecutó en Snowflake**. Lint offline: `sqlglot` (dialecto Snowflake) parsea sin error `01_raw.sql`, `04_checks.sql`, `05_reset.sql` y las sentencias SQL estándar de `00`/`02`; las sentencias propias de Snowflake que `sqlglot` no entiende (`CREATE SEMANTIC VIEW`, `CREATE AGENT`, `DESCRIBE AGENT`, `EXECUTE IMMEDIATE`, `CREATE AUTHENTICATION POLICY`, etc.) se tratan como comandos opacos y **no están validadas por el lint**. El YAML de `03_agent.sql` se parsó con PyYAML (válido, 3 KB, el límite es 100 000 bytes). Paréntesis y comillas de la vista semántica se verificaron balanceados.

**Confirmado en la doc (oct 2026):**

- `CREATE SEMANTIC VIEW`: orden de cláusulas `TABLES, RELATIONSHIPS, FACTS, DIMENSIONS, METRICS, COMMENT, AI_SQL_GENERATION`; `PRIMARY KEY`; `WITH SYNONYMS`; `COMMENT`; `PRIVATE` en hechos/métricas; métrica derivada (sin alias de tabla); dimensiones con el mismo nombre que su columna (`airports.city_name AS city_name` es ejemplo oficial); `SELECT` sobre la vista semántica basta, sin privilegios sobre las tablas subyacentes. https://docs.snowflake.com/en/sql-reference/sql/create-semantic-view · https://docs.snowflake.com/en/user-guide/views-semantic/sql · https://docs.snowflake.com/en/user-guide/views-semantic/querying
- `SEMANTIC_VIEW(... DIMENSIONS ... METRICS ...)` en `FROM`; no se pueden mezclar `FACTS` y `METRICS`. https://docs.snowflake.com/en/sql-reference/constructs/semantic_view
- `CREATE AGENT ... FROM SPECIFICATION $$ yaml $$`; claves `models.orchestration`, `orchestration.budget.{seconds,tokens}`, `instructions.{response,orchestration,sample_questions[].question}`, `tools[].tool_spec.{type,name,description}`, `tool_resources.<tool>.semantic_view`; el DDL no valida las herramientas. https://docs.snowflake.com/en/sql-reference/sql/create-agent
- `tool_resources.<tool>.execution_environment.{type: warehouse, warehouse}`: aparece en la doc del REST de agentes (no en los ejemplos de `CREATE AGENT`). https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-manage
- Modelos de orquestación Claude GA: `claude-sonnet-5`, `claude-sonnet-4-6`, `claude-sonnet-4-5`, `claude-haiku-4-5`, `claude-opus-*`; `auto` recomendado. https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents
- Permisos del agente: `GRANT USAGE ON AGENT`, `SNOWFLAKE.CORTEX_USER` (todo Cortex) o `CORTEX_AGENT_USER` (solo agentes); permisos según el **rol por defecto** del usuario + warehouse por defecto. https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-setup
- REST: `POST /api/v2/databases/{db}/schemas/{schema}/agents/{name}:run`, cuerpo, tipos de evento SSE, último evento `response`. https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-run
- Desde 2026-04-13 los agentes generan el SQL directamente; los bloques salen como `system_execute_sql`. https://docs.snowflake.com/en/release-notes/2026/other/2026-04-13-cortex-agents-agentic-analyst
- SQL: `SNOWFLAKE.CORTEX.DATA_AGENT_RUN('<db.schema.agent>', '<json>')` (sin `stream`). https://docs.snowflake.com/en/sql-reference/functions/data_agent_run-snowflake-cortex
- `AI_COMPLETE(model =>, prompt =>, model_parameters =>, response_format => {'type':'json','schema':{...}}, show_details =>)`; todo modelo soportado admite salida estructurada; `minLength/maxLength/minimum/maximum/minItems` no soportados (error); `additionalProperties:false` solo obligatorio para OpenAI. https://docs.snowflake.com/en/sql-reference/functions/ai_complete-single-string · https://docs.snowflake.com/en/user-guide/snowflake-cortex/complete-structured-outputs
- Privilegios de `AI_COMPLETE`: `USE AI FUNCTIONS` (cuenta, en PUBLIC por defecto) + `CORTEX_USER` o `AI_FUNCTIONS_USER` + acceso al modelo. https://docs.snowflake.com/en/user-guide/snowflake-cortex/aisql-privileges-and-access
- Cross-region: `ALTER ACCOUNT SET CORTEX_ENABLED_CROSS_REGION = 'ANY_REGION'` y valores. https://docs.snowflake.com/en/user-guide/snowflake-cortex/cross-region-inference
- PAT: `ALTER USER ... ADD PROGRAMMATIC ACCESS TOKEN <n> ROLE_RESTRICTION= DAYS_TO_EXPIRY= COMMENT=`; el secreto solo sale una vez; usuarios `TYPE=SERVICE` exigen `ROLE_RESTRICTION` y network policy salvo que una política de autenticación diga `NETWORK_POLICY_EVALUATION = ENFORCED_NOT_REQUIRED`; header `Authorization: Bearer <pat>` y `X-Snowflake-Authorization-Token-Type: PROGRAMMATIC_ACCESS_TOKEN` (opcional). https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token · https://docs.snowflake.com/en/user-guide/programmatic-access-tokens · https://docs.snowflake.com/en/sql-reference/sql/create-authentication-policy · https://docs.snowflake.com/en/developer-guide/snowflake-rest-api/authentication
- `CREATE USER ... TYPE = SERVICE DEFAULT_ROLE DEFAULT_WAREHOUSE DEFAULT_NAMESPACE`. https://docs.snowflake.com/en/sql-reference/sql/create-user

**NO verificado (puede requerir un retoque; todos tienen plan B arriba):**

- Que `enum` y `additionalProperties` dentro del esquema de `response_format` los acepte `claude-sonnet-5` (la doc solo prohíbe `minLength` y similares).
- El tipo de retorno exacto de `AI_COMPLETE` con `response_format` (OBJECT vs texto JSON): el SQL de `04_checks.sql` usa `TRY_PARSE_JSON(out::STRING)` para funcionar en ambos casos.
- Que la expresión de un hecho/métrica pueda usar una columna cuyo nombre coincide con una dimensión (`rol`, `permiso_produccion`) sin "ambiguous reference". La doc muestra dimensión = columna del mismo nombre, no su uso dentro de otra expresión.
- `PRIVATE` en hechos y la métrica derivada con `NULLIF` en una vista de una sola tabla.
- `GRANT SELECT ON SEMANTIC VIEW` y `GRANT USAGE ON AGENT` (el privilegio y el tipo de objeto están en la doc; la frase exacta de la sentencia se dedujo), `SHOW AGENTS`, `DESCRIBE AGENT`, `DESCRIBE SEMANTIC VIEW`, `ALTER USER ... REMOVE PROGRAMMATIC ACCESS TOKEN`, `ALTER USER ... UNSET AUTHENTICATION POLICY`, `ALTER USER ... SET TIMEZONE`.
- Que `execution_environment` se acepte dentro de la especificación SQL de `CREATE AGENT` (si falla, bórralo: se usa el warehouse por defecto del usuario).
- El valor `budget.seconds: 90 / tokens: 20000` es razonable, no medido.
- `EXECUTE IMMEDIATE $variable_de_sesión` para los GRANT al usuario humano (patrón documentado, no probado con nombres con caracteres especiales; si falla, escribe a mano `GRANT ROLE SWT_OWNER TO USER "<tu usuario>"` para los tres roles).
- Latencia real del agente (esperar 10 a 40 s; hay que calentar).
- La forma exacta del anidamiento del JSON de respuesta del agente (la doc es inconsistente); ver `rest_examples.md`.
