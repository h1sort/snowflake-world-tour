-- =====================================================================
-- 01_raw.sql · Tablas RAW (contrato demo/CONTRACT.md)
-- Ejecutar como SWT_OWNER. Idempotente (CREATE ... IF NOT EXISTS).
-- Cargas del loader: MERGE ... ON ID (idempotente). Ver README.
-- Para reiniciar los datos entre ensayo y charla: 05_reset.sql
-- =====================================================================
USE ROLE SWT_OWNER;
USE WAREHOUSE SWT_WH;
USE SCHEMA SWT_DEMO.RAW;

-- Un grupo de encuestas (h1sort poll_groups). CREATED_AT en UTC.
CREATE TABLE IF NOT EXISTS RAW.POLL_GROUPS (
  ID          STRING        NOT NULL,
  CODE        STRING,
  TITLE       STRING,
  CREATED_AT  TIMESTAMP_NTZ,
  _LOADED_AT  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (ID)
);

-- Preguntas. ORDINAL (1..n) lo calcula el puente: created_at ASC, id ASC.
-- P1 -> ROL, P2 -> USO_IA_7D, P3 -> PERMISO_PRODUCCION (ver SEM.RESPUESTAS).
CREATE TABLE IF NOT EXISTS RAW.POLLS (
  ID          STRING        NOT NULL,
  GROUP_ID    STRING,
  CODE        STRING,
  QUESTION    STRING,
  STATUS      STRING,        -- draft | open | closed
  CREATED_AT  TIMESTAMP_NTZ,
  OPENED_AT   TIMESTAMP_NTZ,
  CLOSED_AT   TIMESTAMP_NTZ,
  ORDINAL     NUMBER,
  _LOADED_AT  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (ID)
);

-- Opciones. "POSITION" entre comillas por ser también nombre de función; el
-- identificador resultante es el mismo POSITION (mayúsculas) del contrato.
CREATE TABLE IF NOT EXISTS RAW.POLL_OPTIONS (
  ID          STRING        NOT NULL,
  POLL_ID     STRING,
  LABEL       STRING,
  "POSITION"  NUMBER,
  _LOADED_AT  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (ID)
);

-- Votos. VOTER_KEY = sha256(VOTER_SALT + voter_hash) en hex (calculado en el
-- puente; el voter_hash crudo nunca llega a Snowflake). Un voto por navegador
-- y pregunta. Un navegador no es una persona.
CREATE TABLE IF NOT EXISTS RAW.POLL_VOTES (
  ID          STRING        NOT NULL,
  POLL_ID     STRING,
  OPTION_ID   STRING,
  VOTER_KEY   STRING,
  CREATED_AT  TIMESTAMP_NTZ,
  _LOADED_AT  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (ID)
);

-- ---------------------------------------------------------------------
-- Privilegios del loader: USAGE (ya dado en 00) + SELECT/INSERT/UPDATE.
-- "INSERT/UPDATE/MERGE" del contrato: MERGE no es un privilegio; un MERGE con
-- WHEN MATCHED UPDATE / WHEN NOT MATCHED INSERT necesita INSERT y UPDATE en
-- la tabla destino, y SELECT para evaluar el ON. Sin DELETE, sin TRUNCATE,
-- sin CREATE. Importante para el puente: usar
--   MERGE INTO RAW.T USING (SELECT ... FROM VALUES ...) / (SELECT ?, ?, ...)
-- en lugar de tablas temporales (CREATE TEMPORARY TABLE no está otorgado).
-- ---------------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE ON TABLE SWT_DEMO.RAW.POLL_GROUPS  TO ROLE SWT_LOADER;
GRANT SELECT, INSERT, UPDATE ON TABLE SWT_DEMO.RAW.POLLS        TO ROLE SWT_LOADER;
GRANT SELECT, INSERT, UPDATE ON TABLE SWT_DEMO.RAW.POLL_OPTIONS TO ROLE SWT_LOADER;
GRANT SELECT, INSERT, UPDATE ON TABLE SWT_DEMO.RAW.POLL_VOTES   TO ROLE SWT_LOADER;

SHOW TABLES IN SCHEMA SWT_DEMO.RAW;
