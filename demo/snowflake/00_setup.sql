-- =====================================================================
-- 00_setup.sql  ·  Snowflake World Tour CDMX 2026 · demo "Ask · Judge · Act"
-- Ejecutar COMPLETO como ACCOUNTADMIN (una sola vez; es idempotente).
-- Crea: roles, warehouse, base de datos, esquemas, usuario de servicio,
--       política de autenticación para PAT y los GRANT de mínimo privilegio.
-- Contrato: demo/CONTRACT.md  (nombres fijos: SWT_DEMO, RAW, SEM, SWT_WH,
--           SWT_LOADER, SWT_AGENT_RO).
-- Docs verificadas (oct 2026): ver README.md, sección "Qué se verificó".
-- =====================================================================
USE ROLE ACCOUNTADMIN;

-- ---------------------------------------------------------------------
-- 0. Parámetros
-- ---------------------------------------------------------------------
-- Tu usuario humano (el que corre estos scripts) recibe los tres roles para
-- poder ensayar en Snowsight con USE ROLE. Cámbialo si quieres otro usuario:
--   SET my_user = 'MI_USUARIO';
SET my_user = CURRENT_USER();

-- El usuario de servicio (loader + harness vía PAT) se llama SWT_DEMO_USER.
-- Nombre fijo (literal) para que README.md y rest_examples.md coincidan; no se
-- parametriza porque ALTER USER ... ADD PROGRAMMATIC ACCESS TOKEN con
-- IDENTIFIER() no está documentado.

-- ---------------------------------------------------------------------
-- 1. Roles
-- ---------------------------------------------------------------------
CREATE ROLE IF NOT EXISTS SWT_OWNER    COMMENT = 'Demo SWT: dueño de SWT_DEMO (crea vistas, vista semantica y agente)';
CREATE ROLE IF NOT EXISTS SWT_LOADER   COMMENT = 'Demo SWT: loader incremental. Solo escribe en RAW';
CREATE ROLE IF NOT EXISTS SWT_AGENT_RO COMMENT = 'Demo SWT: rol de solo lectura del agente y el harness. Solo lee SEM';

-- Jerarquía recomendada: SYSADMIN hereda los tres.
GRANT ROLE SWT_OWNER    TO ROLE SYSADMIN;
GRANT ROLE SWT_LOADER   TO ROLE SYSADMIN;
GRANT ROLE SWT_AGENT_RO TO ROLE SYSADMIN;

-- ---------------------------------------------------------------------
-- 2. Warehouse (XSMALL, auto-suspend 60 s)  · contrato
-- ---------------------------------------------------------------------
CREATE WAREHOUSE IF NOT EXISTS SWT_WH
  WAREHOUSE_SIZE      = 'XSMALL'
  AUTO_SUSPEND        = 60
  AUTO_RESUME         = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT             = 'Demo SWT: warehouse unico para loader, agente y harness';

-- ---------------------------------------------------------------------
-- 3. Base de datos y esquemas
-- ---------------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS SWT_DEMO COMMENT = 'Demo Snowflake World Tour CDMX 2026';
DROP SCHEMA IF EXISTS SWT_DEMO.PUBLIC;
CREATE SCHEMA IF NOT EXISTS SWT_DEMO.RAW COMMENT = 'Tablas crudas cargadas por el loader desde D1';
CREATE SCHEMA IF NOT EXISTS SWT_DEMO.SEM COMMENT = 'Capa de significado: vista RESPUESTAS, vista semantica y agente';
CREATE SCHEMA IF NOT EXISTS SWT_DEMO.GOV COMMENT = 'Objetos de gobierno (politica de autenticacion). Dueño: ACCOUNTADMIN';

-- ---------------------------------------------------------------------
-- 4. Política de autenticación para el PAT del usuario de servicio
--    Por qué: por defecto un PAT de usuario SERVICE exige estar bajo una
--    network policy (NETWORK_POLICY_EVALUATION = ENFORCED_REQUIRED). En una
--    sede de conferencia no conocemos la IP de salida (wifi / hotspot), así
--    que para ESTA demo relajamos esa exigencia SOLO para este usuario.
--    Se mantiene REQUIRE_ROLE_RESTRICTION: cada PAT queda atado a un rol.
--    Para producción: quita ENFORCED_NOT_REQUIRED y usa network policy con
--    tu IP (ver "Opción B" abajo).
-- ---------------------------------------------------------------------
CREATE AUTHENTICATION POLICY IF NOT EXISTS SWT_DEMO.GOV.SWT_PAT_POLICY
  AUTHENTICATION_METHODS = ('PROGRAMMATIC_ACCESS_TOKEN')
  PAT_POLICY = (
    DEFAULT_EXPIRY_IN_DAYS = 3
    MAX_EXPIRY_IN_DAYS = 7
    NETWORK_POLICY_EVALUATION = ENFORCED_NOT_REQUIRED
    REQUIRE_ROLE_RESTRICTION_FOR_SERVICE_USERS = TRUE
  )
  COMMENT = 'Demo SWT: PAT sin network policy obligatoria, siempre con role restriction';

-- Opción B (más estricta, comentada): network rule + policy con tu IP pública
--   CREATE NETWORK RULE SWT_DEMO.GOV.SWT_ALLOW_MY_IP TYPE = IPV4 MODE = INGRESS VALUE_LIST = ('<TU_IP_PUBLICA>/32');
--   CREATE NETWORK POLICY SWT_NP ALLOWED_NETWORK_RULE_LIST = ('SWT_DEMO.GOV.SWT_ALLOW_MY_IP');
--   ALTER USER SWT_DEMO_USER SET NETWORK_POLICY = SWT_NP;
-- (y cambia NETWORK_POLICY_EVALUATION a ENFORCED_REQUIRED en la política de arriba)

-- ---------------------------------------------------------------------
-- 5. Usuario de servicio (sin contraseña; solo PAT)
--    DEFAULT_ROLE = SWT_AGENT_RO es IMPORTANTE: Cortex Agents evalúa permisos
--    con el rol por defecto del usuario, no con el rol de la sesión.
--    DEFAULT_WAREHOUSE con USAGE para ese rol también es obligatorio.
-- ---------------------------------------------------------------------
CREATE USER IF NOT EXISTS SWT_DEMO_USER
  TYPE              = SERVICE
  DEFAULT_ROLE      = SWT_AGENT_RO
  DEFAULT_WAREHOUSE = SWT_WH
  DEFAULT_NAMESPACE = SWT_DEMO.SEM
  COMMENT           = 'Demo SWT: usuario de servicio (loader + harness) autenticado con PAT';

-- Zona horaria UTC: CREATED_AT de D1 viene en UTC y _LOADED_AT usa CURRENT_TIMESTAMP().
ALTER USER SWT_DEMO_USER SET TIMEZONE = 'UTC';
ALTER USER SWT_DEMO_USER SET AUTHENTICATION POLICY = SWT_DEMO.GOV.SWT_PAT_POLICY;

GRANT ROLE SWT_LOADER   TO USER SWT_DEMO_USER;
GRANT ROLE SWT_AGENT_RO TO USER SWT_DEMO_USER;

-- Tu usuario humano: los tres roles (para ensayar y para correr 01..04).
SET g1 = 'GRANT ROLE SWT_OWNER    TO USER "' || $my_user || '"';
SET g2 = 'GRANT ROLE SWT_LOADER   TO USER "' || $my_user || '"';
SET g3 = 'GRANT ROLE SWT_AGENT_RO TO USER "' || $my_user || '"';
EXECUTE IMMEDIATE $g1;
EXECUTE IMMEDIATE $g2;
EXECUTE IMMEDIATE $g3;

-- ---------------------------------------------------------------------
-- 6. Privilegios de mínimo acceso (antes de transferir la propiedad)
-- ---------------------------------------------------------------------
-- 6.1 Warehouse
GRANT USAGE ON WAREHOUSE SWT_WH TO ROLE SWT_OWNER;
GRANT USAGE ON WAREHOUSE SWT_WH TO ROLE SWT_LOADER;
GRANT USAGE ON WAREHOUSE SWT_WH TO ROLE SWT_AGENT_RO;

-- 6.2 SWT_LOADER: USAGE en db + RAW. Los privilegios sobre tablas se dan en
--     01_raw.sql (SELECT/INSERT/UPDATE; MERGE no es un privilegio: se hace
--     con INSERT + UPDATE y SELECT para el ON del MERGE).
GRANT USAGE ON DATABASE SWT_DEMO     TO ROLE SWT_LOADER;
GRANT USAGE ON SCHEMA   SWT_DEMO.RAW TO ROLE SWT_LOADER;

-- 6.3 SWT_AGENT_RO: USAGE en db + SEM. SIN acceso a RAW (la vista RESPUESTAS
--     lee RAW con los derechos del dueño). SELECT en la vista, la vista
--     semantica y USAGE en el agente se dan en 02_sem.sql / 03_agent.sql.
GRANT USAGE ON DATABASE SWT_DEMO     TO ROLE SWT_AGENT_RO;
GRANT USAGE ON SCHEMA   SWT_DEMO.SEM TO ROLE SWT_AGENT_RO;

-- 6.4 Cortex. SNOWFLAKE.CORTEX_USER ya está en PUBLIC por defecto; se otorga
--     explícito para que la demo no dependa de ese default. Cubre Cortex
--     Agents, Cortex Analyst y AI_COMPLETE.
--     USE AI FUNCTIONS (privilegio de cuenta, ene-feb 2026) también está en
--     PUBLIC por defecto; explícito por la misma razón.
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE SWT_AGENT_RO;
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE SWT_OWNER;
GRANT USE AI FUNCTIONS ON ACCOUNT TO ROLE SWT_AGENT_RO;
GRANT USE AI FUNCTIONS ON ACCOUNT TO ROLE SWT_OWNER;

-- 6.5 Propiedad: SWT_OWNER es dueño de la base y de RAW/SEM (GOV queda con
--     ACCOUNTADMIN). COPY CURRENT GRANTS conserva los USAGE de arriba.
GRANT OWNERSHIP ON SCHEMA   SWT_DEMO.RAW TO ROLE SWT_OWNER COPY CURRENT GRANTS;
GRANT OWNERSHIP ON SCHEMA   SWT_DEMO.SEM TO ROLE SWT_OWNER COPY CURRENT GRANTS;
GRANT OWNERSHIP ON DATABASE SWT_DEMO     TO ROLE SWT_OWNER COPY CURRENT GRANTS;

-- ---------------------------------------------------------------------
-- 7. Inferencia entre regiones (Claude en Cortex)
--    Ningún modelo Claude aparece como "nativo" por región en la página de
--    disponibilidad: todos se sirven por cross-region inference (CRIS).
--    Si el parámetro está en DISABLED, AI_COMPLETE y el agente fallan con
--    "model not available". Valor por defecto: ANY_REGION en organizaciones
--    nuevas (después del 9 mar 2026); en otras, un valor de la misma nube
--    (p.ej. AWS_US). claude-sonnet-5 está en: Cross Cloud, AWS US, EU, APJ, AU.
-- ---------------------------------------------------------------------
SHOW PARAMETERS LIKE 'CORTEX_ENABLED_CROSS_REGION' IN ACCOUNT;
-- Si "value" es DISABLED (o tu región/nube no cubre el modelo), descomenta UNA:
-- ALTER ACCOUNT SET CORTEX_ENABLED_CROSS_REGION = 'ANY_REGION';
-- ALTER ACCOUNT SET CORTEX_ENABLED_CROSS_REGION = 'AWS_US';   -- cuenta AWS en EE.UU.
-- Implicación de datos: los datos siguen guardados en tu región; los prompts
-- viajan temporalmente a la región de proceso y no se persisten allá. La demo
-- usa datos sintéticos / votos anónimos de la sala (VOTER_KEY ya viene hasheado).

-- ---------------------------------------------------------------------
-- 8. Valores para el .env de la demo
-- ---------------------------------------------------------------------
SELECT CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() AS snowflake_account_para_env,
       LOWER(REPLACE(CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME(), '_', '-')) || '.snowflakecomputing.com' AS host_rest,
       CURRENT_REGION() AS region;
-- SNOWFLAKE_ACCOUNT = snowflake_account_para_env   (formato ORG-CUENTA)
-- SNOWFLAKE_USER    = SWT_DEMO_USER

-- ---------------------------------------------------------------------
-- 9. SECCIÓN MANUAL: crear los PAT (NO ejecutar con "Run all")
--    El secreto (token_secret) solo aparece UNA vez en el resultado del
--    comando. Cópialo de inmediato al .env (nunca al repo). Ejecuta cada
--    ALTER USER por separado, como ACCOUNTADMIN.
--
--    Dos PAT, uno por rol, para que "rol de solo lectura" sea literal: el
--    PAT del harness NO puede escribir aunque se filtre.
--
--    PAT del agente/harness  ->  SNOWFLAKE_PAT
--    ALTER USER SWT_DEMO_USER ADD PROGRAMMATIC ACCESS TOKEN SWT_PAT_AGENT
--      ROLE_RESTRICTION = 'SWT_AGENT_RO'
--      DAYS_TO_EXPIRY = 3
--      COMMENT = 'Harness de la demo (solo lectura)';
--
--    PAT del loader (puente)  ->  SNOWFLAKE_PAT_LOADER   (variable adicional)
--    ALTER USER SWT_DEMO_USER ADD PROGRAMMATIC ACCESS TOKEN SWT_PAT_LOADER
--      ROLE_RESTRICTION = 'SWT_LOADER'
--      DAYS_TO_EXPIRY = 3
--      COMMENT = 'Loader incremental de la demo (escribe en RAW)';
--
--    Revocar después de la charla:
--    ALTER USER SWT_DEMO_USER REMOVE PROGRAMMATIC ACCESS TOKEN SWT_PAT_AGENT;
--    ALTER USER SWT_DEMO_USER REMOVE PROGRAMMATIC ACCESS TOKEN SWT_PAT_LOADER;
--
--    Alternativa sin usuario de servicio: usa tu usuario humano (TYPE=PERSON)
--    y un PAT con MINS_TO_BYPASS_NETWORK_POLICY_REQUIREMENT = 1440 (24 h). Los
--    PAT de personas pueden no llevar ROLE_RESTRICTION, pero entonces el PAT
--    hereda TODOS tus roles: no lo recomendamos para el harness.
-- ---------------------------------------------------------------------
