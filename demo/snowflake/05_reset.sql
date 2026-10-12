-- =====================================================================
-- 05_reset.sql · Limpiar los datos entre ensayo y charla (rol: SWT_OWNER)
-- Vacía las cuatro tablas RAW. Hazlo ANTES de crear/abrir el grupo real, o
-- apunta el puente al grupo real (la vista usa el grupo más reciente).
-- =====================================================================
USE ROLE SWT_OWNER;
USE WAREHOUSE SWT_WH;

TRUNCATE TABLE SWT_DEMO.RAW.POLL_VOTES;
TRUNCATE TABLE SWT_DEMO.RAW.POLL_OPTIONS;
TRUNCATE TABLE SWT_DEMO.RAW.POLLS;
TRUNCATE TABLE SWT_DEMO.RAW.POLL_GROUPS;

SELECT COUNT(*) AS filas_restantes FROM SWT_DEMO.SEM.RESPUESTAS;   -- 0

-- ---------------------------------------------------------------------
-- Desmontaje completo tras la charla (como ACCOUNTADMIN; descomentar):
--   USE ROLE ACCOUNTADMIN;
--   ALTER USER SWT_DEMO_USER REMOVE PROGRAMMATIC ACCESS TOKEN SWT_PAT_AGENT;
--   ALTER USER SWT_DEMO_USER REMOVE PROGRAMMATIC ACCESS TOKEN SWT_PAT_LOADER;
--   ALTER USER SWT_DEMO_USER UNSET AUTHENTICATION POLICY;
--   DROP USER IF EXISTS SWT_DEMO_USER;
--   DROP DATABASE IF EXISTS SWT_DEMO;     -- incluye RAW, SEM (vistas, agente) y GOV (política)
--   DROP WAREHOUSE IF EXISTS SWT_WH;
--   DROP ROLE IF EXISTS SWT_LOADER;
--   DROP ROLE IF EXISTS SWT_AGENT_RO;
--   DROP ROLE IF EXISTS SWT_OWNER;
-- ---------------------------------------------------------------------
