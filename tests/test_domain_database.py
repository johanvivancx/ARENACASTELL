from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from decimal import Decimal
from threading import Barrier
import pytest
import psycopg
from psycopg.rows import dict_row
from manage import cedula_demo
from models import (validar_cedula,Usuario,Cliente,Administrador,ReservaCancha,
                    ServicioArena,InscripcionTorneo,InscripcionSuperChaca,ErrorValidacion)
import services as s


def reservation(hour="10:00",hours=1):
    return {"cancha_id":1,"tipo_evento":"HORA","fecha":str(datetime.now(s.TZ).date()+timedelta(days=3)),"hora":hour,"horas":hours}


def school(index=200):
    today=datetime.now(s.TZ).date()
    born=date(today.year-10,1,1)
    return {"alumno":"Alumno Sintético","cedula":cedula_demo(index),"nacimiento":str(born),"categoria":"Sub-12","horario_id":5,"consentimiento":True}


def school_data(conn,index=200):
    data=school(index)
    data["horario_id"]=conn.execute("SELECT id FROM horarios_chaca WHERE categoria='Sub-12' ORDER BY id LIMIT 1").fetchone()["id"]
    return data


@pytest.mark.parametrize("value,expected",[(cedula_demo(1),True),("0000000000",False),("9999999999",False),("1712345678",False),("17x0000010",False),("123",False)])
def test_cedula_python_y_sql(conn,value,expected):
    assert validar_cedula(value) is expected
    assert conn.execute("SELECT validar_cedula(%s) AS ok",(value,)).fetchone()["ok"] is expected


def test_poo_y_calculo_monetario():
    with pytest.raises(TypeError): ServicioArena()
    services=[ReservaCancha(3,"HORA",{"tarifa_hora":Decimal("27")}),InscripcionTorneo(120),InscripcionSuperChaca(date(2016,1,1),"Sub-12",date(2026,8,30))]
    assert [service.calcular_costo() for service in services]==[Decimal("81.00"),Decimal("120.00"),Decimal("50.00")]
    with pytest.raises(ErrorValidacion):ReservaCancha(0,"HORA",{})
    with pytest.raises(ErrorValidacion):InscripcionSuperChaca(date(2016,1,1),"Sub-8",date(2026,8,30))


def test_password_y_roles(conn,user):
    cliente=Usuario.desde_fila(user)
    assert isinstance(cliente,Cliente)
    assert not cliente.puede_administrar()
    assert cliente.verificar_password("PruebaSegura!2026")
    assert not cliente.verificar_password("incorrecta")
    assert not hasattr(cliente,"__password_hash")
    assert "PruebaSegura!2026" not in cliente.get_password_hash()
    admin=Usuario.desde_fila({**user,"rol":"ADMIN"})
    assert isinstance(admin,Administrador) and admin.puede_administrar()


def test_registro_no_permite_rol_admin(conn):
    row=s.registrar(conn,{"nombre":"Usuario Rol","email":"rol@arena.test","cedula":cedula_demo(8),"telefono":"0990000000","password":"UnaContraseña!2026","confirmacion":"UnaContraseña!2026","consentimiento":True,"rol":"ADMIN"})
    assert row["rol"]=="CLIENTE"


def test_reserva_y_pago_idempotente(conn,user,pay_data):
    order=s.reservar(conn,user["id"],reservation(hours=2))
    s.pagar(conn,user["id"],order["id"],{**pay_data,"monto":"0.01"})
    s.pagar(conn,user["id"],order["id"],pay_data)
    detail=s.detalle_orden(conn,user["id"],order["id"])
    assert detail["monto"]==Decimal("54") and detail["estado"]=="PAGADA"
    assert detail["reserva"]["estado"]=="CONFIRMADA"
    assert conn.execute("SELECT count(*) AS n FROM pagos").fetchone()["n"]==1
    assert conn.execute("SELECT count(*) AS n FROM correo_salida").fetchone()["n"]==1


def test_solapamiento_revierte_pago_y_permite_contiguas(conn,user,pay_data):
    first=s.reservar(conn,user["id"],reservation("10:00",2))
    overlap=s.reservar(conn,user["id"],reservation("11:00"))
    next_order=s.reservar(conn,user["id"],reservation("12:00"))
    s.pagar(conn,user["id"],first["id"],pay_data)
    with pytest.raises(psycopg.errors.ExclusionViolation):
        with conn.transaction():s.pagar(conn,user["id"],overlap["id"],pay_data)
    s.pagar(conn,user["id"],next_order["id"],pay_data)
    assert s.detalle_orden(conn,user["id"],overlap["id"])["estado"]=="PENDIENTE"
    assert conn.execute("SELECT count(*) AS n FROM pagos").fetchone()["n"]==2


@pytest.mark.parametrize("hour,hours",[("22:00",2),("10:00",7)])
def test_reserva_fuera_de_horario(conn,user,hour,hours):
    with pytest.raises((ErrorValidacion,psycopg.errors.CheckViolation)):
        with conn.transaction():s.reservar(conn,user["id"],reservation(hour,hours))


def test_dos_pagos_concurrentes_mismo_horario(conn,user,pay_data,database_url):
    orders=[s.reservar(conn,user["id"],reservation()) for _ in range(2)]
    conn.commit();barrier=Barrier(2)
    def worker(order):
        try:
            with psycopg.connect(database_url,row_factory=dict_row) as c:
                barrier.wait(timeout=10)
                s.pagar(c,user["id"],order["id"],pay_data)
            return "ok"
        except psycopg.errors.ExclusionViolation:return "overlap"
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(worker,orders))
    assert sorted(results)==["ok","overlap"]
    assert conn.execute("SELECT count(*) AS n FROM pagos").fetchone()["n"]==1


def test_limite_jugadores_en_base(conn,user,pay_data):
    order=s.inscribir_torneo(conn,user["id"],{"torneo_id":1,"equipo":"Equipo Prueba","acepta_reglamento":True})
    s.pagar(conn,user["id"],order["id"],pay_data)
    team=s.detalle_orden(conn,user["id"],order["id"])["equipo"]
    for n in range(20):s.agregar_jugador(conn,user["id"],team["id"],{"nombre":f"Jugador {n}","cedula":cedula_demo(n+300)})
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            conn.execute("INSERT INTO jugadores(equipo_id,nombre,cedula) VALUES(%s,'Jugador 21',%s)",(team["id"],cedula_demo(399)))
    assert len(s.lista_equipo(conn,user["id"],team["id"])["jugadores"])==20


def test_ultimo_cupo_torneo_concurrente(conn,user,pay_data,database_url):
    conn.execute("UPDATE torneos SET cupos=2 WHERE id=1")
    orders=[s.inscribir_torneo(conn,user["id"],{"torneo_id":1,"equipo":f"Equipo {n}","acepta_reglamento":True}) for n in range(3)]
    s.pagar(conn,user["id"],orders[0]["id"],pay_data);conn.commit();barrier=Barrier(2)
    def worker(order):
        try:
            with psycopg.connect(database_url,row_factory=dict_row) as c:
                barrier.wait(timeout=10);s.pagar(c,user["id"],order["id"],pay_data)
            return True
        except psycopg.errors.CheckViolation:return False
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(worker,orders[1:]))
    assert sorted(results)==[False,True]


def test_escuela_periodos_sin_duplicar_y_reportes(conn,user,pay_data):
    order=s.inscribir_escuela(conn,user["id"],school_data(conn))
    s.pagar(conn,user["id"],order["id"],pay_data)
    detail=s.detalle_orden(conn,user["id"],order["id"])
    assert detail["escuela"]["estado"]=="ACTIVA" and detail["pago"]["monto"]==50
    current=datetime.now(s.TZ).date().replace(day=1)
    assert s.renovar_escuela(conn,user["id"],detail["escuela"]["id"],{"periodo":current.strftime("%Y-%m")})["id"]==order["id"]
    following=(current+timedelta(days=32)).replace(day=1)
    next_order=s.renovar_escuela(conn,user["id"],detail["escuela"]["id"],{"periodo":following.strftime("%Y-%m")})
    s.pagar(conn,user["id"],next_order["id"],pay_data)
    report=conn.execute("SELECT * FROM vista_mensualidades_escuela").fetchone()
    assert report["total_pagado"]==100 and report["cuotas_pagadas"]==2 and report["mes_actual_pagado"]
    assert len(conn.execute("SELECT * FROM vista_reporte_administrador").fetchall())==2


def test_horario_categoria_replicado_en_bd(conn,user):
    data=school_data(conn)
    order=s.inscribir_escuela(conn,user["id"],data)
    wrong=conn.execute("SELECT id FROM horarios_chaca WHERE categoria='Sub-8' LIMIT 1").fetchone()["id"]
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with conn.transaction():conn.execute("UPDATE inscripciones_chaca SET horario_id=%s WHERE orden_id=%s",(wrong,order["id"]))


def test_recuperacion_un_solo_uso_y_sesiones_revocadas(conn,user):
    token,_=s.nueva_sesion(conn,user["id"])
    s.solicitar_restablecimiento(conn,{"email":user["email"]})
    body=conn.execute("SELECT cuerpo FROM correo_salida ORDER BY id DESC LIMIT 1").fetchone()["cuerpo"]
    reset_token=body.split('#token=')[1].split()[0]
    data={"token":reset_token,"password":"NuevaClaveSegura!","confirmacion":"NuevaClaveSegura!"}
    s.restablecer_password(conn,data)
    assert s.obtener_sesion(conn,token) is None
    with pytest.raises(ErrorValidacion):s.restablecer_password(conn,data)
    assert s.iniciar_sesion(conn,{"email":user["email"],"password":"NuevaClaveSegura!"})["id"]==user["id"]


def test_propiedad_y_admin(conn,user):
    order=s.reservar(conn,user["id"],reservation())
    with pytest.raises(s.HTTPError) as forbidden:s.detalle_orden(conn,user["id"]+1,order["id"])
    assert forbidden.value.status==404
    with pytest.raises(s.HTTPError) as admin:s.reportes(conn,user["id"],{})
    assert admin.value.status==403


def test_datos_criticos_cambio_requiere_password(conn,user):
    with pytest.raises(ErrorValidacion):s.actualizar_perfil(conn,user["id"],{**user,"email":"otro@arena.test"})
    s.actualizar_perfil(conn,user["id"],{**user,"email":"otro@arena.test","password_actual":"PruebaSegura!2026"})
    assert conn.execute("SELECT email FROM usuarios WHERE id=%s",(user["id"],)).fetchone()["email"]=="otro@arena.test"
