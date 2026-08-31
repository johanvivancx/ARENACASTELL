"""Precios, duración de cumpleaños y conservación de reservas anteriores."""
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest

from models import ErrorValidacion
import services as s

ROOT = Path(__file__).resolve().parents[1]


def datos(tipo, horas):
    return {'cancha_id': 1, 'tipo_evento': tipo, 'horas': horas,
            'fecha': str(datetime.now(s.TZ).date() + timedelta(days=12)), 'hora': '10:00'}


@pytest.mark.parametrize('tipo,horas,total', [
    ('HORA', 1, '27.00'), ('HORA', 6, '162.00'),
    ('EVENTO', 1, '30.00'), ('EVENTO', 4, '120.00'),
    ('CUMPLEANOS', 3, '75.00'),
])
def test_tarifa_en_orden_pago_e_historial(conn, user, pay_data, tipo, horas, total):
    order = s.reservar(conn, user['id'], {**datos(tipo, horas), 'monto': '0.01'})
    s.pagar(conn, user['id'], order['id'], {**pay_data, 'monto': '0.01'})
    detail = s.detalle_orden(conn, user['id'], order['id'])
    assert detail['monto'] == detail['pago']['monto'] == Decimal(total)
    assert detail['reserva']['fin'] - detail['reserva']['inicio'] == timedelta(hours=horas)
    assert s.historial(conn, user['id'])['ordenes'][0]['monto'] == Decimal(total)


@pytest.mark.parametrize('horas', [1, 2, 4, 5, 6])
def test_cumpleanos_rechaza_otra_duracion_en_python(conn, user, horas):
    with pytest.raises(ErrorValidacion, match='3 horas'):
        s.reservar(conn, user['id'], datos('CUMPLEANOS', horas))
    assert conn.execute('SELECT count(*) AS n FROM ordenes').fetchone()['n'] == 0


def test_sql_no_permite_cumpleanos_nuevo_fuera_del_paquete(conn, user):
    order = s.reservar(conn, user['id'], datos('HORA', 2))
    with pytest.raises(psycopg.errors.CheckViolation, match='3 horas'):
        with conn.transaction():
            conn.execute("UPDATE reservas SET tipo_evento='CUMPLEANOS' WHERE orden_id=%s", (order['id'],))
    with pytest.raises(psycopg.errors.CheckViolation, match='3 horas'):
        with conn.transaction():
            conn.execute("""INSERT INTO reservas(orden_id,cancha_id,tipo_evento,inicio,fin)
              SELECT orden_id,cancha_id,'CUMPLEANOS',inicio,fin FROM reservas WHERE orden_id=%s""", (order['id'],))


def test_actualizacion_repetible_conserva_orden_anterior(conn, user, pay_data):
    conn.execute('UPDATE canchas SET tarifa_hora=30,tarifa_evento=45,tarifa_cumpleanos=40 WHERE id=1')
    order = s.reservar(conn, user['id'], datos('HORA', 2))
    # Reproduce una reserva de cumpleaños de la versión anterior, que permitía dos horas.
    old_function = (ROOT/'sql/schema.sql').read_text(encoding='utf8')
    old_function = old_function.split('CREATE FUNCTION controlar_reserva()', 1)[1].split('END; $$;', 1)[0]
    begin = old_function.index('  -- Los cumpleaños nuevos')
    end = old_function.index('  hora_inicio :=')
    old_function = old_function[:begin] + old_function[end:]
    conn.execute('CREATE OR REPLACE FUNCTION controlar_reserva()' + old_function + 'END; $$;')
    conn.execute("UPDATE reservas SET tipo_evento='CUMPLEANOS' WHERE orden_id=%s", (order['id'],))
    conn.execute('UPDATE ordenes SET monto=80 WHERE id=%s', (order['id'],))
    conn.commit()
    for _ in range(2):
        conn.execute((ROOT/'sql/pgadmin/12_actualizar_tarifas_reservas.sql').read_text(encoding='utf8'))
    s.pagar(conn, user['id'], order['id'], pay_data)
    detail = s.detalle_orden(conn, user['id'], order['id'])
    assert detail['pago']['monto'] == Decimal('80.00')
    assert detail['reserva']['fin'] - detail['reserva']['inicio'] == timedelta(hours=2)
    future = s.reservar(conn, user['id'], {**datos('CUMPLEANOS', 3), 'hora': '15:00'})
    assert s.detalle_orden(conn, user['id'], future['id'])['monto'] == Decimal('75.00')
    with pytest.raises(psycopg.errors.CheckViolation, match='3 horas'):
        with conn.transaction():
            conn.execute("UPDATE reservas SET fin=fin+interval '2 hours' WHERE orden_id=%s", (future['id'],))
