-- Adapta usuario y clave
-- Ejecuta como dueño
-- Crea arena_app sin privilegios
-- Crea el rol antes
-- Rol creado desde pgAdmin

-- Permite conectar la aplicación
GRANT CONNECT ON DATABASE arena_castell TO arena_app;
GRANT USAGE ON SCHEMA public TO arena_app;

-- Impide crear estructuras
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- Permite trabajar con datos
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO arena_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO arena_app;

-- Limita el procedimiento
REVOKE EXECUTE ON PROCEDURE cobrar_mensualidad(uuid,text) FROM PUBLIC;
GRANT EXECUTE ON PROCEDURE cobrar_mensualidad(uuid,text) TO arena_app;

-- Niega cambios estructurales
-- Evita migraciones con arena_app
