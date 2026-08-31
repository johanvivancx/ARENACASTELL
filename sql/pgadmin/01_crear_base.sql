-- PASO 1. Abrir Query Tool sobre la base postgres de tu servidor.
-- Ejecutar UNA VEZ, con Auto-commit activado y fuera de BEGIN/COMMIT.
-- Si arena_castell ya existe, no la borres: avisa para revisar antes de continuar.
CREATE DATABASE arena_castell
    WITH ENCODING = 'UTF8';
-- Después: refrescar Databases y abrir un NUEVO Query Tool sobre arena_castell.
