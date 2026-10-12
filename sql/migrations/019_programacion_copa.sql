-- Permite añadir partidos de las próximas fechas sin editar archivos ni alterar resultados.
CREATE TABLE IF NOT EXISTS copa_partidos_programados (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  fecha smallint NOT NULL CHECK (fecha BETWEEN 1 AND 30),
  local varchar(50) NOT NULL,
  visitante varchar(50) NOT NULL CHECK (visitante <> local),
  dia date NOT NULL,
  hora time NOT NULL,
  creado_por bigint NOT NULL REFERENCES usuarios(id),
  creado_en timestamptz NOT NULL DEFAULT current_timestamp,
  UNIQUE (fecha,local,visitante)
);
