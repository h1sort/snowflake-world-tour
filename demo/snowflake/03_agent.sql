-- =====================================================================
-- 03_agent.sql · Cortex Agent SEM.AGENTE_ENCUESTA
-- Ejecutar como SWT_OWNER (después de 02_sem.sql).
-- Docs: https://docs.snowflake.com/en/sql-reference/sql/create-agent
--       https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-manage
--
-- Modelo de orquestación: claude-sonnet-5 (GA, vía cross-region inference).
-- Plan B, en este orden, si el CREATE o la primera consulta se queja del modelo:
--   1) claude-sonnet-4-5   (el Claude con más cobertura regional)
--   2) auto                (Snowflake elige; es la recomendación de la doc)
-- Cambia SOLO la línea "orchestration: ..." bajo "models:" y re-ejecuta.
--
-- NOTA: CREATE AGENT no valida las herramientas al crearse; el éxito del DDL
-- no prueba que funcione. Probar con 04_checks.sql (parte C).
-- Desde abril 2026 el agente genera el SQL directamente: los bloques de
-- herramienta salen como tipo "system_execute_sql" (ver rest_examples.md),
-- aunque la configuración sigue declarando cortex_analyst_text_to_sql.
-- =====================================================================
USE ROLE SWT_OWNER;
USE WAREHOUSE SWT_WH;
USE SCHEMA SWT_DEMO.SEM;

CREATE OR REPLACE AGENT SWT_DEMO.SEM.AGENTE_ENCUESTA
  COMMENT = 'Demo SWT: agente de consulta (Ask) sobre la vista semántica SEM.ENCUESTA_SWT. Solo lectura.'
  FROM SPECIFICATION
  $$
models:
  orchestration: claude-sonnet-5

orchestration:
  budget:
    seconds: 90
    tokens: 20000

instructions:
  response: |
    Responde siempre en español, de forma breve y directa, para una sala de personas de negocio e ingeniería.
    Formato de cada respuesta con cifras:
    1) Una frase con la conclusión.
    2) Una tabla con una fila por grupo y estas columnas: grupo, con permiso (numerador), navegadores con rol y P3 (denominador), porcentaje.
    3) Una línea: "Corte de datos: <valor de corte_datos> UTC".
    4) El SQL que usaste, en un bloque de código.
    Reglas obligatorias:
    - Muestra siempre numerador y denominador junto a cada porcentaje.
    - Si un grupo tiene menos de 5 navegadores en el denominador (navegadores_con_rol_y_p3 < 5), NO muestres su porcentaje: escribe "muestra insuficiente" y deja visible su numerador y denominador.
    - Una respuesta faltante (NULL) NO es un "No". Quien omitió una pregunta queda fuera del denominador de esa pregunta.
    - Una fila es un navegador, no una persona. Di "navegadores", nunca "personas" ni "usuarios".
    - "Permiso" significa que la respuesta a la pregunta 3 es "Sí" o "Sí, con aprobación humana".
    - Nunca muestres identificadores de navegador (VOTER_KEY), hashes ni cadenas largas de caracteres hexadecimales.
    - Nunca inventes cifras. Si la herramienta falla, no devuelve filas o no puedes responder con la vista semántica, dilo con claridad.
    - No tienes herramientas para modificar, borrar ni cerrar nada. Si te lo piden, explica que solo puedes consultar.
    - Si el total de navegadores con rol y P3 es muy pequeño, dilo: la muestra es de esta sala, no representa a ninguna organización.
  orchestration: |
    Para cualquier pregunta sobre la encuesta, roles, uso de IA o permisos, usa la herramienta consulta_encuesta.
    Para porcentajes de permiso pide en UNA sola consulta: pct_permiso, con_permiso, navegadores_con_rol_y_p3 y corte_datos, agrupando por rol si la pregunta dice "por rol".
    No uses herramientas para nada que no sea esa encuesta.
  sample_questions:
    - question: "Por rol, ¿qué porcentaje le daría a un agente permiso de actuar en producción? Solo cuenta a quien respondió rol y P3."
    - question: "¿Cuántos navegadores respondieron rol y P3, y cuál es el corte de datos?"
    - question: "¿Cuántos navegadores usaron IA para trabajar con datos en los últimos 7 días?"

tools:
  - tool_spec:
      type: "cortex_analyst_text_to_sql"
      name: "consulta_encuesta"
      description: "Consulta en SQL, solo lectura, la encuesta en vivo del Snowflake World Tour CDMX a través de la vista semántica ENCUESTA_SWT: rol (P1), uso de IA en 7 días (P2), permiso de actuar en producción (P3), numeradores, denominadores, porcentajes y fecha de corte. Cada fila es un navegador, no una persona."

tool_resources:
  consulta_encuesta:
    semantic_view: "SWT_DEMO.SEM.ENCUESTA_SWT"
    execution_environment:
      type: "warehouse"
      warehouse: "SWT_WH"
  $$;

-- Rol de solo lectura: USAGE en el agente (más USAGE db/esquema/warehouse y
-- SELECT en la vista semantica, ya otorgados). Re-ejecutar tras CREATE OR REPLACE.
GRANT USAGE ON AGENT SWT_DEMO.SEM.AGENTE_ENCUESTA TO ROLE SWT_AGENT_RO;

SHOW AGENTS IN SCHEMA SWT_DEMO.SEM;
DESCRIBE AGENT SWT_DEMO.SEM.AGENTE_ENCUESTA;
