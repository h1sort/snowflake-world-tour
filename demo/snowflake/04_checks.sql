-- =====================================================================
-- 04_checks.sql · Pruebas de humo (smoke tests)
--
-- CÓMO EJECUTAR: en Snowsight, cada bloque separado por una línea en blanco
-- se ejecuta con Cmd+Enter (un statement a la vez; "Run all" solo muestra el
-- último resultado). O por CLI, que imprime todos:
--     snow sql -f 04_checks.sql
--
-- NO ejecutar la PARTE A/C con la encuesta real en curso sin leer los avisos:
-- los datos sintéticos usan un grupo con CREATED_AT en 2099 y, mientras
-- existan, SEM.RESPUESTAS los prefiere sobre el grupo real.
--   * PARTE A: dentro de una transacción -> invisible para otras sesiones.
--              Termina con ROLLBACK (seguro incluso en vivo).
--   * PARTE C: necesita datos COMMITTED (el agente corre en otra sesión).
--              Solo en ensayo; limpiar con la PARTE D.
-- =====================================================================

-- =====================================================================
-- PARTE A · SEM.RESPUESTAS y vista semántica con datos sintéticos
--           (rol: SWT_OWNER, dentro de una transacción)
-- =====================================================================
USE ROLE SWT_OWNER;
USE WAREHOUSE SWT_WH;

-- A0. Estado actual de RAW (para saber si ya hay datos reales)
SELECT 'POLL_GROUPS' AS tabla, COUNT(*) AS filas FROM SWT_DEMO.RAW.POLL_GROUPS
UNION ALL SELECT 'POLLS',        COUNT(*) FROM SWT_DEMO.RAW.POLLS
UNION ALL SELECT 'POLL_OPTIONS', COUNT(*) FROM SWT_DEMO.RAW.POLL_OPTIONS
UNION ALL SELECT 'POLL_VOTES',   COUNT(*) FROM SWT_DEMO.RAW.POLL_VOTES;

BEGIN TRANSACTION;

INSERT INTO SWT_DEMO.RAW.POLL_GROUPS (ID, CODE, TITLE, CREATED_AT)
VALUES ('smk-g', 'SMOKE00000', 'Smoke test', '2099-01-01 09:00:00');

INSERT INTO SWT_DEMO.RAW.POLLS (ID, GROUP_ID, CODE, QUESTION, STATUS, CREATED_AT, OPENED_AT, CLOSED_AT, ORDINAL)
SELECT column1, 'smk-g', column2, column3, 'open', column4, column4, NULL, column5
FROM VALUES
  ('smk-p1', 'smk1', '¿Cuál describe mejor tu rol?',                                   '2099-01-01 09:00:01'::TIMESTAMP_NTZ, 1),
  ('smk-p2', 'smk2', 'En los últimos 7 días, ¿usaste IA para trabajar con datos?',     '2099-01-01 09:00:02'::TIMESTAMP_NTZ, 2),
  ('smk-p3', 'smk3', '¿Le darías a un agente permiso de actuar en producción?',        '2099-01-01 09:00:03'::TIMESTAMP_NTZ, 3);

INSERT INTO SWT_DEMO.RAW.POLL_OPTIONS (ID, POLL_ID, LABEL, "POSITION")
SELECT column1, column2, column3, column4
FROM VALUES
  ('smk-o1-0', 'smk-p1', 'Negocio', 0), ('smk-o1-1', 'smk-p1', 'Ingeniería', 1),
  ('smk-o1-2', 'smk-p1', 'Datos y analítica', 2), ('smk-o1-3', 'smk-p1', 'Liderazgo', 3),
  ('smk-o1-4', 'smk-p1', 'Otro', 4),
  ('smk-o2-0', 'smk-p2', 'Sí', 0), ('smk-o2-1', 'smk-p2', 'No', 1),
  ('smk-o3-0', 'smk-p3', 'Sí', 0), ('smk-o3-1', 'smk-p3', 'Sí, con aprobación humana', 1),
  ('smk-o3-2', 'smk-p3', 'No', 2);

-- 15 navegadores sintéticos. NULL = no respondió esa pregunta.
-- Trampas a propósito: v06 omitió P3; v13 y v14 omitieron P1 (responden P3 pero
-- NO entran al denominador); v15 solo contestó P1; "Datos y analítica" tiene n=1.
INSERT INTO SWT_DEMO.RAW.POLL_VOTES (ID, POLL_ID, OPTION_ID, VOTER_KEY, CREATED_AT)
SELECT 'smk-' || q.poll_id || '-' || v.k, q.poll_id, o.ID, v.k,
       DATEADD(second, v.t, '2099-01-01 10:00:00'::TIMESTAMP_NTZ)
FROM (
  SELECT column1 AS k, column2 AS p1, column3 AS p2, column4 AS p3, column5 AS t FROM VALUES
    ('v01', 'Negocio',           'Sí', 'Sí',                        1),
    ('v02', 'Negocio',           'Sí', 'Sí, con aprobación humana', 2),
    ('v03', 'Negocio',           'No', 'No',                        3),
    ('v04', 'Negocio',           'Sí', 'Sí',                        4),
    ('v05', 'Negocio',           'Sí', 'No',                        5),
    ('v06', 'Negocio',           'Sí', NULL,                        6),
    ('v07', 'Ingeniería',        'Sí', 'Sí, con aprobación humana', 7),
    ('v08', 'Ingeniería',        'Sí', 'No',                        8),
    ('v09', 'Ingeniería',        'Sí', 'Sí',                        9),
    ('v10', 'Ingeniería',        'No', 'Sí',                       10),
    ('v11', 'Ingeniería',        'Sí', 'Sí',                       11),
    ('v12', 'Datos y analítica', 'Sí', 'Sí',                       12),
    ('v13', NULL,                NULL, 'Sí',                       13),
    ('v14', NULL,                'Sí', 'Sí, con aprobación humana', 14),
    ('v15', 'Liderazgo',         NULL, NULL,                       15)
) v
CROSS JOIN (SELECT column1 AS poll_id, column2 AS n FROM VALUES ('smk-p1', 1), ('smk-p2', 2), ('smk-p3', 3)) q
JOIN SWT_DEMO.RAW.POLL_OPTIONS o
  ON o.POLL_ID = q.poll_id
 AND o.LABEL = DECODE(q.n, 1, v.p1, 2, v.p2, 3, v.p3);   -- NULL no une: sin voto

-- A1. La vista pivote: 15 filas, NULL donde no respondió (nunca "No").
--     Esperado: v06 con PERMISO_PRODUCCION NULL; v13/v14 con ROL NULL; v15 solo ROL.
SELECT * FROM SWT_DEMO.SEM.RESPUESTAS ORDER BY PRIMERA_RESPUESTA_AT;

-- A2. Verdad de referencia calculada a mano en SQL (sin vista semántica).
--     Esperado: navegadores=15, denominador=11, con_permiso=8,
--               y el cálculo INGENUO (P3 sin exigir rol) = 10 (la trampa).
SELECT COUNT(*)                                                                    AS navegadores,
       COUNT_IF(ROL IS NOT NULL AND PERMISO_PRODUCCION IS NOT NULL)                AS denominador,
       COUNT_IF(ROL IS NOT NULL AND PERMISO_PRODUCCION IN ('Sí', 'Sí, con aprobación humana')) AS con_permiso,
       COUNT_IF(PERMISO_PRODUCCION IN ('Sí', 'Sí, con aprobación humana'))         AS ingenuo_incorrecto,
       MAX(ULTIMA_RESPUESTA_AT)                                                    AS corte
FROM SWT_DEMO.SEM.RESPUESTAS;

-- A3. Etiquetas inesperadas (debe devolver 0 filas). Detecta acentos/normalización
--     distintos entre lo que guarda el sitio y lo que compara la vista semántica.
SELECT 'ROL' AS col, ROL AS valor, COUNT(*) AS n FROM SWT_DEMO.SEM.RESPUESTAS
  WHERE ROL IS NOT NULL AND ROL NOT IN ('Negocio','Ingeniería','Datos y analítica','Liderazgo','Otro') GROUP BY ROL
UNION ALL SELECT 'USO_IA_7D', USO_IA_7D, COUNT(*) FROM SWT_DEMO.SEM.RESPUESTAS
  WHERE USO_IA_7D IS NOT NULL AND USO_IA_7D NOT IN ('Sí','No') GROUP BY USO_IA_7D
UNION ALL SELECT 'PERMISO_PRODUCCION', PERMISO_PRODUCCION, COUNT(*) FROM SWT_DEMO.SEM.RESPUESTAS
  WHERE PERMISO_PRODUCCION IS NOT NULL AND PERMISO_PRODUCCION NOT IN ('Sí','Sí, con aprobación humana','No') GROUP BY PERMISO_PRODUCCION;

-- A4. Vista semántica con sintaxis SEMANTIC_VIEW(...), por rol.
--     Esperado:  Negocio 3/5 (0.60) · Ingeniería 4/5 (0.80) ·
--                Datos y analítica 1/1 (1.00, n<5 -> "muestra insuficiente" lo hace el agente) ·
--                Liderazgo 0/0 (NULL) · (rol NULL) 0/0 (NULL)
SELECT * FROM SEMANTIC_VIEW(
  SWT_DEMO.SEM.ENCUESTA_SWT
  DIMENSIONS respuestas.rol
  METRICS respuestas.con_permiso, respuestas.navegadores_con_rol_y_p3, pct_permiso, respuestas.corte_datos
)
ORDER BY rol NULLS LAST;

-- A5. Total sin dimensiones. Esperado: 15 / 11 / 8 / 0.7273 / 2099-01-01 10:00:15
SELECT * FROM SEMANTIC_VIEW(
  SWT_DEMO.SEM.ENCUESTA_SWT
  METRICS respuestas.navegadores, respuestas.navegadores_con_rol_y_p3, respuestas.con_permiso, pct_permiso, respuestas.corte_datos
);

-- A6. Aserción automática (PASS/FAIL por grupo).
SELECT e.rol, e.con_permiso AS esp_num, r.con_permiso AS real_num,
       e.den AS esp_den, r.navegadores_con_rol_y_p3 AS real_den,
       IFF(e.con_permiso = r.con_permiso AND e.den = r.navegadores_con_rol_y_p3, 'PASS', 'FAIL') AS resultado
FROM (SELECT column1 AS rol, column2 AS con_permiso, column3 AS den FROM VALUES
        ('Negocio', 3, 5), ('Ingeniería', 4, 5), ('Datos y analítica', 1, 1), ('Liderazgo', 0, 0), (NULL, 0, 0)) e
LEFT JOIN (
  SELECT * FROM SEMANTIC_VIEW(
    SWT_DEMO.SEM.ENCUESTA_SWT
    DIMENSIONS respuestas.rol
    METRICS respuestas.con_permiso, respuestas.navegadores_con_rol_y_p3)
) r ON r.rol IS NOT DISTINCT FROM e.rol
ORDER BY e.rol NULLS LAST;

-- A7. ¿Termina aquí? Elige UNA:
ROLLBACK;     -- por defecto: no deja rastro (seguro en vivo)
-- COMMIT;    -- solo en ENSAYO, si vas a correr PARTE C (agente). Luego PARTE D.

-- =====================================================================
-- PARTE B · Rol de solo lectura + AI_COMPLETE (Judge y Act)
--           (rol: SWT_AGENT_RO; no necesita datos)
-- =====================================================================
USE ROLE SWT_AGENT_RO;
USE WAREHOUSE SWT_WH;

-- B1. Lo que SÍ puede: leer SEM.
SELECT COUNT(*) AS filas_en_sem_respuestas FROM SWT_DEMO.SEM.RESPUESTAS;

-- B2. Lo que NO puede: leer RAW. Se atrapa el error para que el script no aborte.
--     Esperado: PASS.
EXECUTE IMMEDIATE $$
BEGIN
  SELECT COUNT(*) FROM SWT_DEMO.RAW.POLL_VOTES;
  RETURN 'FAIL: SWT_AGENT_RO pudo leer RAW (revisa los GRANT)';
EXCEPTION
  WHEN OTHER THEN
    RETURN 'PASS: SWT_AGENT_RO no puede leer RAW (' || SQLERRM || ')';
END;
$$;

-- B3. Lo que NO puede: escribir. Esperado: PASS.
EXECUTE IMMEDIATE $$
BEGIN
  INSERT INTO SWT_DEMO.SEM.RESPUESTAS (VOTER_KEY) VALUES ('x');
  RETURN 'FAIL: SWT_AGENT_RO pudo escribir';
EXCEPTION
  WHEN OTHER THEN
    RETURN 'PASS: SWT_AGENT_RO no puede escribir (' || SQLERRM || ')';
END;
$$;

-- B4. Disponibilidad de modelos Claude (NULL = no disponible para tu cuenta/región;
--     las filas que fallan devuelven NULL sin detener la consulta). Elige el
--     primero con respuesta para CORTEX_MODEL y para el agente.
SELECT m.column1 AS modelo,
       AI_COMPLETE(model => m.column1, prompt => 'Responde solo con la palabra: listo') AS respuesta
FROM VALUES ('claude-sonnet-5'), ('claude-sonnet-4-5'), ('claude-haiku-4-5') m;

-- B5. Judge: AI_COMPLETE con salida estructurada (esquema del contrato).
--     {"veredicto": "pasa"|"revisar"|"rechazar", "evidencia": [str], "motivo": str}
--     Esperado: un objeto JSON válido; con esta respuesta de ejemplo (denominador
--     correcto, n<5 marcado, corte presente) lo normal es "pasa" o "revisar".
SET judge_model = 'claude-sonnet-5';

SELECT out,
       TRY_PARSE_JSON(out::STRING):veredicto::STRING AS veredicto,
       TRY_PARSE_JSON(out::STRING):evidencia         AS evidencia,
       TRY_PARSE_JSON(out::STRING):motivo::STRING    AS motivo
FROM (
  SELECT AI_COMPLETE(
    model => $judge_model,
    prompt => $$Eres el Juez de una respuesta analítica. Evalúa SOLO con la evidencia dada. Devuelve veredicto "pasa" si numeradores, denominadores y corte están presentes y los grupos con menos de 5 están marcados como "muestra insuficiente"; "revisar" si falta evidencia; "rechazar" si hay una contradicción.
RESPUESTA A EVALUAR:
Por rol (navegadores con rol y P3): Negocio 3/5 = 60 %; Ingeniería 4/5 = 80 %; Datos y analítica 1/1: muestra insuficiente. Corte de datos: 2099-01-01 10:00:15 UTC.
EVIDENCIA DEL HARNESS: denominadores recalculados = Negocio 5, Ingeniería 5, Datos y analítica 1.$$,
    model_parameters => {'temperature': 0, 'max_tokens': 600},
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
  ) AS out
);
-- Si da error 400 por 'enum' o 'additionalProperties': quita esa palabra clave
-- del esquema y valida el valor en código (el harness ya lo valida).

-- B6. Act: el modelo PROPONE una acción tipada; la aplicación valida.
--     Pedimos algo fuera de la lista permitida: el modelo puede proponerlo y la
--     APLICACIÓN lo rechaza ("RECHAZADA · sin efecto"). Aquí solo vemos la propuesta.
SELECT TRY_PARSE_JSON(out::STRING) AS propuesta
FROM (
  SELECT AI_COMPLETE(
    model => $judge_model,
    prompt => $$Convierte la petición en UNA propuesta de acción tipada. Herramientas conocidas: cerrar_encuesta(codigo_grupo), borrar_votos(filtro). Petición del operador: "borra los votos incompletos".$$,
    model_parameters => {'temperature': 0, 'max_tokens': 300},
    response_format => {
      'type': 'json',
      'schema': {
        'type': 'object',
        'properties': {
          'accion':   {'type': 'string'},
          'objetivo': {'type': 'string'},
          'motivo':   {'type': 'string'}
        },
        'required': ['accion', 'objetivo', 'motivo']
      }
    }
  ) AS out
);

-- =====================================================================
-- PARTE C · Agente por SQL (SOLO ENSAYO; requiere datos committed)
--           (rol: SWT_AGENT_RO)
-- Punto de entrada SQL: SNOWFLAKE.CORTEX.DATA_AGENT_RUN (no hace streaming).
-- Doc: https://docs.snowflake.com/en/sql-reference/functions/data_agent_run-snowflake-cortex
-- Para el REST (lo que usa el harness) ver rest_examples.md.
-- Antes: haber hecho COMMIT en A7 en vez de ROLLBACK.
-- Tarda ~10 a 40 s.
-- =====================================================================
USE ROLE SWT_AGENT_RO;
USE WAREHOUSE SWT_WH;

SELECT TRY_PARSE_JSON(
  SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
    'SWT_DEMO.SEM.AGENTE_ENCUESTA',
    $${
      "messages": [
        {"role": "user",
         "content": [{"type": "text",
                      "text": "Por rol, ¿qué porcentaje le daría a un agente permiso de actuar en producción? Solo cuenta a quien respondió rol y P3."}]}
      ]
    }$$
  )
) AS respuesta_agente;
-- Esperado en el JSON: status "completed"; content[] con un tool_use/tool_result
-- (type "system_execute_sql") y al final un item type "text" con la tabla:
-- Negocio 3/5, Ingeniería 4/5, Datos y analítica 1/1 "muestra insuficiente",
-- y "Corte de datos: 2099-01-01 10:00:15".

-- C2. Solo el texto final y el SQL (tolerante a las dos formas de anidar de la doc).
WITH r AS (
  SELECT TRY_PARSE_JSON(
    SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
      'SWT_DEMO.SEM.AGENTE_ENCUESTA',
      $${"messages": [{"role": "user", "content": [{"type": "text", "text": "Por rol, ¿qué porcentaje le daría a un agente permiso de actuar en producción? Solo cuenta a quien respondió rol y P3."}]}]}$$
    )
  ) AS j
)
SELECT f.index AS i,
       f.value:type::STRING AS tipo,
       COALESCE(f.value:text::STRING, f.value:"text"::STRING) AS texto,
       COALESCE(f.value:tool_use:input:sql::STRING, f.value:tool_result:content[0]:json:sql::STRING) AS sql_usado
FROM r, LATERAL FLATTEN(INPUT => r.j:content) f
ORDER BY f.index;

-- =====================================================================
-- PARTE D · Limpieza de los datos sintéticos (rol: SWT_OWNER)
-- Ejecutar siempre después de PARTE C. Solo borra filas con ID 'smk-%'.
-- =====================================================================
USE ROLE SWT_OWNER;
USE WAREHOUSE SWT_WH;

DELETE FROM SWT_DEMO.RAW.POLL_VOTES   WHERE ID LIKE 'smk-%';
DELETE FROM SWT_DEMO.RAW.POLL_OPTIONS WHERE ID LIKE 'smk-%';
DELETE FROM SWT_DEMO.RAW.POLLS        WHERE ID LIKE 'smk-%';
DELETE FROM SWT_DEMO.RAW.POLL_GROUPS  WHERE ID LIKE 'smk-%';

-- Debe devolver 0 en las cuatro:
SELECT (SELECT COUNT(*) FROM SWT_DEMO.RAW.POLL_GROUPS  WHERE ID LIKE 'smk-%') AS g,
       (SELECT COUNT(*) FROM SWT_DEMO.RAW.POLLS        WHERE ID LIKE 'smk-%') AS p,
       (SELECT COUNT(*) FROM SWT_DEMO.RAW.POLL_OPTIONS WHERE ID LIKE 'smk-%') AS o,
       (SELECT COUNT(*) FROM SWT_DEMO.RAW.POLL_VOTES   WHERE ID LIKE 'smk-%') AS v;
