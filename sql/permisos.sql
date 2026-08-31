-- Plantilla administrativa, NO ejecutar sin adaptar usuario/base y contraseña.
-- Ejecutar como dueño de la base después de schema.sql.
-- Crear arena_app sin privilegios elevados desde pgAdmin4 y asignar allí una contraseña segura.
-- Ejemplo de atributos, sin contraseña incorporada:
-- CREATE ROLE arena_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;

GRANT CONNECT ON DATABASE arena_castell TO arena_app;
GRANT USAGE ON SCHEMA public TO arena_app;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO arena_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO arena_app;
REVOKE EXECUTE ON PROCEDURE cobrar_mensualidad(uuid,text) FROM PUBLIC;
GRANT EXECUTE ON PROCEDURE cobrar_mensualidad(uuid,text) TO arena_app;
-- No otorgar TRUNCATE ni permisos de definición al rol de ejecución.
-- No usar este rol para crear bases de pruebas o ejecutar migraciones.
