-- =====================================================================
-- 02_sem.sql · SEM.RESPUESTAS (vista) + SEM.ENCUESTA_SWT (vista semántica)
-- Ejecutar como SWT_OWNER.
-- Sintaxis CREATE SEMANTIC VIEW:
--   https://docs.snowflake.com/en/sql-reference/sql/create-semantic-view
--   https://docs.snowflake.com/en/user-guide/views-semantic/sql
-- =====================================================================
USE ROLE SWT_OWNER;
USE WAREHOUSE SWT_WH;
USE SCHEMA SWT_DEMO.SEM;

-- ---------------------------------------------------------------------
-- 1. SEM.RESPUESTAS: una fila por navegador (VOTER_KEY) del grupo activo.
--    P1 -> ROL, P2 -> USO_IA_7D, P3 -> PERMISO_PRODUCCION, por ORDINAL.
--    Valores = etiquetas de opción tal cual. Sin respuesta = NULL (nunca "No").
--
--    "Grupo configurado": el loader solo carga el grupo GROUP_CODE, pero RAW
--    puede conservar grupos de ensayos anteriores. La vista usa el grupo MÁS
--    RECIENTE por CREATED_AT en RAW.POLL_GROUPS. Si ensayaste con otro grupo,
--    o limpia con 05_reset.sql o crea el grupo real después del de ensayo.
--
--    Columnas = contrato + ULTIMA_RESPUESTA_AT al final (aditiva): el "corte de
--    datos" correcto es el último voto cargado, no la primera respuesta de
--    cada navegador.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW SWT_DEMO.SEM.RESPUESTAS
  COMMENT = 'Una fila por navegador (no por persona) del grupo activo. P1 rol, P2 uso de IA 7d, P3 permiso en produccion. NULL = no respondio (no es un No).'
AS
WITH grupo AS (
  SELECT ID
  FROM SWT_DEMO.RAW.POLL_GROUPS
  QUALIFY ROW_NUMBER() OVER (ORDER BY CREATED_AT DESC, ID DESC) = 1
),
votos AS (
  SELECT v.VOTER_KEY, p.ORDINAL, o.LABEL, v.CREATED_AT
  FROM SWT_DEMO.RAW.POLL_VOTES   v
  JOIN SWT_DEMO.RAW.POLLS        p ON p.ID = v.POLL_ID
  JOIN grupo                     g ON g.ID = p.GROUP_ID
  JOIN SWT_DEMO.RAW.POLL_OPTIONS o ON o.ID = v.OPTION_ID AND o.POLL_ID = v.POLL_ID
)
SELECT
  VOTER_KEY,
  MAX(IFF(ORDINAL = 1, LABEL, NULL)) AS ROL,
  MAX(IFF(ORDINAL = 2, LABEL, NULL)) AS USO_IA_7D,
  MAX(IFF(ORDINAL = 3, LABEL, NULL)) AS PERMISO_PRODUCCION,
  MIN(CREATED_AT)                    AS PRIMERA_RESPUESTA_AT,
  MAX(CREATED_AT)                    AS ULTIMA_RESPUESTA_AT
FROM votos
GROUP BY VOTER_KEY;

-- ---------------------------------------------------------------------
-- 2. SEM.ENCUESTA_SWT: la capa de significado (definiciones aprobadas).
--
--    Decisiones:
--    * Una sola tabla lógica (RESPUESTAS). VOTER_KEY es solo PRIMARY KEY:
--      NO es dimensión, hecho ni métrica, así que el agente no puede
--      proyectarla (excepto COUNT, que no revela valores).
--    * Los hechos auxiliares son PRIVATE: sirven para definir métricas pero
--      no se ofrecen al agente como columnas consultables.
--    * con_permiso lleva TAMBIÉN la condición ROL NOT NULL (contrato:
--      "count where PERMISO in (...)"); así el numerador siempre está dentro
--      del denominador y pct_permiso nunca pasa de 100 %. Sin esa condición,
--      quien respondió P3 pero no P1 inflaría el numerador.
--    * pct_permiso es una métrica derivada (sin alias de tabla): fracción
--      0 a 1; el agente la presenta como porcentaje.
-- ---------------------------------------------------------------------
CREATE OR REPLACE SEMANTIC VIEW SWT_DEMO.SEM.ENCUESTA_SWT

  TABLES (
    respuestas AS SWT_DEMO.SEM.RESPUESTAS
      PRIMARY KEY (voter_key)
      WITH SYNONYMS = ('encuesta', 'respuestas', 'navegadores', 'votos', 'asistentes')
      COMMENT = 'Una fila es un NAVEGADOR (un dispositivo que votó), no una persona: dos filas pueden ser la misma persona y una persona sin navegador no aparece. Una respuesta faltante (NULL) NO es un "No": significa que ese navegador no respondió esa pregunta. El identificador del navegador (VOTER_KEY) nunca se expone ni se muestra.'
  )

  FACTS (
    PRIVATE respuestas.es_par_valido AS
      CASE WHEN rol IS NOT NULL AND permiso_produccion IS NOT NULL THEN 1 ELSE 0 END
      COMMENT = 'Auxiliar: 1 si el navegador respondió rol (P1) y permiso en producción (P3); 0 si falta alguna.',
    PRIVATE respuestas.otorga_permiso AS
      CASE WHEN rol IS NOT NULL AND permiso_produccion IN ('Sí', 'Sí, con aprobación humana') THEN 1 ELSE 0 END
      COMMENT = 'Auxiliar: 1 si respondió rol y P3 con "Sí" o "Sí, con aprobación humana"; 0 en cualquier otro caso (incluye "No" y sin respuesta).'
  )

  DIMENSIONS (
    respuestas.rol AS rol
      WITH SYNONYMS = ('puesto', 'perfil', 'función', 'área', 'P1', 'pregunta 1')
      COMMENT = 'Rol declarado en la pregunta 1: Negocio, Ingeniería, Datos y analítica, Liderazgo u Otro. NULL = no respondió la pregunta 1 (no es una categoría).',
    respuestas.uso_ia_7d AS uso_ia_7d
      WITH SYNONYMS = ('uso de IA', 'usó IA', 'uso de inteligencia artificial', 'IA últimos 7 días', 'P2', 'pregunta 2')
      COMMENT = 'Pregunta 2: usó IA para trabajar con datos en los últimos 7 días. Valores: "Sí", "No". NULL = no respondió (no es un "No").',
    respuestas.permiso_produccion AS permiso_produccion
      WITH SYNONYMS = ('permiso', 'permiso en producción', 'permiso de actuar', 'autonomía del agente', 'P3', 'pregunta 3')
      COMMENT = 'Pregunta 3: ¿le daría a un agente permiso de actuar en producción? Valores: "Sí", "Sí, con aprobación humana", "No". NULL = no respondió (no es un "No"). Tiene permiso quien contestó "Sí" o "Sí, con aprobación humana".',
    respuestas.primera_respuesta_at AS primera_respuesta_at
      WITH SYNONYMS = ('hora de primera respuesta', 'llegada')
      COMMENT = 'Momento (UTC) de la primera respuesta de ese navegador.',
    respuestas.ultima_respuesta_at AS ultima_respuesta_at
      WITH SYNONYMS = ('hora de última respuesta')
      COMMENT = 'Momento (UTC) de la última respuesta de ese navegador.'
  )

  METRICS (
    respuestas.navegadores AS COUNT(respuestas.voter_key)
      WITH SYNONYMS = ('total de navegadores', 'filas', 'votantes', 'participantes', 'n total')
      COMMENT = 'Navegadores con al menos una respuesta, sin importar qué preguntas contestó. No es el denominador de ningún porcentaje de permiso.',
    respuestas.navegadores_con_rol_y_p3 AS SUM(respuestas.es_par_valido)
      WITH SYNONYMS = ('denominador', 'respuestas válidas', 'pares válidos', 'n', 'base', 'navegadores válidos', 'muestra')
      COMMENT = 'DENOMINADOR aprobado: navegadores que respondieron rol (P1) Y permiso en producción (P3). Quien omitió P1 o P3 no cuenta; omitir no es contestar "No". Si este valor es menor que 5 en un grupo, reportar "muestra insuficiente".',
    respuestas.con_permiso AS SUM(respuestas.otorga_permiso)
      WITH SYNONYMS = ('numerador', 'con permiso', 'dan permiso', 'permiten', 'a favor')
      COMMENT = 'NUMERADOR aprobado: navegadores con rol y P3 respondida cuya P3 es "Sí" o "Sí, con aprobación humana". Siempre es parte de navegadores_con_rol_y_p3.',
    respuestas.corte_datos AS MAX(respuestas.ultima_respuesta_at)
      WITH SYNONYMS = ('corte', 'fecha de corte', 'último voto', 'datos al')
      COMMENT = 'Fecha de corte (UTC): el voto más reciente cargado. Incluirlo siempre en la respuesta.',
    pct_permiso AS
      respuestas.con_permiso / NULLIF(respuestas.navegadores_con_rol_y_p3, 0)
      WITH SYNONYMS = ('porcentaje de permiso', 'porcentaje', 'proporción', 'tasa de permiso', '% permiso')
      COMMENT = 'Porcentaje aprobado = con_permiso / navegadores_con_rol_y_p3, como fracción de 0 a 1 (multiplicar por 100 para mostrar %). NULL cuando el denominador es 0. Mostrarlo siempre junto a numerador y denominador.'
  )

  COMMENT = 'Encuesta en vivo (Snowflake World Tour CDMX). Definiciones aprobadas: "permiso" = P3 es "Sí" o "Sí, con aprobación humana"; denominador = navegadores que respondieron rol y P3; una respuesta faltante nunca es un "No"; una fila es un navegador, no una persona; nunca exponer VOTER_KEY.'

  AI_SQL_GENERATION 'Responde siempre en español. Para cualquier porcentaje de permiso usa la métrica pct_permiso e incluye en la MISMA consulta con_permiso, navegadores_con_rol_y_p3 y corte_datos. Agrupa por rol cuando se pida por rol. Nunca trates un valor NULL como "No" y nunca reemplaces el denominador por el total de navegadores. Una fila es un navegador, no una persona: usa la palabra navegadores. Nunca consultes ni muestres voter_key.'
;

-- ---------------------------------------------------------------------
-- 3. Privilegios del rol de solo lectura (re-ejecutar si haces CREATE OR REPLACE)
-- ---------------------------------------------------------------------
GRANT SELECT ON VIEW          SWT_DEMO.SEM.RESPUESTAS    TO ROLE SWT_AGENT_RO;
GRANT SELECT ON SEMANTIC VIEW SWT_DEMO.SEM.ENCUESTA_SWT  TO ROLE SWT_AGENT_RO;

SHOW SEMANTIC VIEWS IN SCHEMA SWT_DEMO.SEM;
DESCRIBE SEMANTIC VIEW SWT_DEMO.SEM.ENCUESTA_SWT;
