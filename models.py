"""Modelo de dominio. Los cuatro pilares de POO sin depender de un framework."""
from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
import hashlib
import hmac
import re
import secrets


class ErrorValidacion(ValueError):
    """Una regla del dominio no se cumple; el mensaje puede mostrarse al usuario."""


def validar_cedula(cedula: str) -> bool:
    if not re.fullmatch(r"[0-9]{10}", cedula):
        return False
    if not 1 <= int(cedula[:2]) <= 24 or int(cedula[2]) > 5:
        return False
    valores = [int(d) * (2 if i % 2 == 0 else 1) for i, d in enumerate(cedula[:9])]
    return (10 - sum(v - 9 if v > 9 else v for v in valores) % 10) % 10 == int(cedula[-1])


def texto(valor, campo, minimo=2, maximo=100):
    if not isinstance(valor, str) or not minimo <= len(valor.strip()) <= maximo:
        raise ErrorValidacion(f"{campo}: escribe entre {minimo} y {maximo} caracteres.")
    return valor.strip()


class Usuario:
    def __init__(self, nombre: str, email: str, cedula: str, telefono: str,
                 password_hash: str = "", id: int | None = None):
        self.id = id
        self.nombre = texto(nombre, "Nombre")
        self.email = texto(email, "Correo", 5, 254).lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", self.email):
            raise ErrorValidacion("Escribe un correo electrónico válido.")
        if not validar_cedula(cedula):
            raise ErrorValidacion("La cédula ecuatoriana no es válida. Revisa sus 10 dígitos.")
        if not re.fullmatch(r"09[0-9]{8}", telefono):
            raise ErrorValidacion("El celular debe tener 10 dígitos y comenzar con 09.")
        self.cedula = cedula
        self.telefono = telefono
        self.__password_hash = password_hash

    @property
    def rol(self):
        return "CLIENTE"

    def set_password(self, password: str):
        if not isinstance(password, str) or not 10 <= len(password) <= 128:
            raise ErrorValidacion("Usa una contraseña de 10 a 128 caracteres.")
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000).hex()
        self.__password_hash = f"pbkdf2_sha256$600000${salt}${digest}"

    def get_password_hash(self):
        """Acceso explícito para persistencia: nunca se entrega en respuestas HTTP."""
        return self.__password_hash

    def verificar_password(self, password: str) -> bool:
        try:
            algorithm, rounds, salt, digest = self.__password_hash.split("$")
            if algorithm != "pbkdf2_sha256" or not isinstance(password, str) or len(password) > 128:
                return False
            candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(rounds)).hex()
            return hmac.compare_digest(digest, candidate)
        except (ValueError, TypeError):
            return False

    def puede_administrar(self) -> bool:
        return False

    @classmethod
    def desde_fila(cls, fila):
        clase = Administrador if fila["rol"] == "ADMIN" else Cliente
        return clase(**{k: fila[k] for k in ("id", "nombre", "email", "cedula", "telefono", "password_hash")})


class Administrador(Usuario):
    @property
    def rol(self):
        return "ADMIN"

    def puede_administrar(self) -> bool:
        return True


class Cliente(Usuario):
    def puede_administrar(self) -> bool:
        return False


class ServicioArena(ABC):
    """Abstracción: todo servicio sabe calcular su costo y describirlo."""
    @abstractmethod
    def calcular_costo(self) -> Decimal:
        pass

    def resumen_costo(self):
        return f"USD {self.calcular_costo():.2f}"


class ReservaCancha(ServicioArena):
    def __init__(self, horas: int, tipo_evento: str, tarifas: dict):
        if type(horas) is not int or not 1 <= horas <= 6:
            raise ErrorValidacion("Elige una duración de 1 a 6 horas.")
        if tipo_evento not in ("HORA", "EVENTO", "CUMPLEANOS"):
            raise ErrorValidacion("Selecciona un tipo de reserva válido.")
        if tipo_evento == "CUMPLEANOS" and horas != 3:
            raise ErrorValidacion("El paquete de cumpleaños tiene una duración de 3 horas.")
        self.__horas = horas
        self.__tipo = tipo_evento
        self.__tarifas = tarifas

    def calcular_costo(self):
        key = {"HORA": "tarifa_hora", "EVENTO": "tarifa_evento", "CUMPLEANOS": "tarifa_cumpleanos"}[self.__tipo]
        return (Decimal(str(self.__tarifas[key])) * self.__horas).quantize(Decimal("0.01"))


class InscripcionTorneo(ServicioArena):
    def __init__(self, tarifa: Decimal, jugadores: int = 0, max_jugadores: int = 20):
        if not 1 <= max_jugadores <= 20 or not 0 <= jugadores <= max_jugadores:
            raise ErrorValidacion(f"El límite es de {max_jugadores} jugadores para este torneo; el tope del sistema es 20.")
        self.__tarifa = Decimal(str(tarifa))
        if self.__tarifa <= 0:
            raise ErrorValidacion("La tarifa del torneo debe ser positiva.")

    def calcular_costo(self):
        return self.__tarifa.quantize(Decimal("0.01"))


class InscripcionSuperChaca(ServicioArena):
    MENSUALIDAD = Decimal("50.00")

    def __init__(self, nacimiento: date, categoria: str, fecha: date):
        edad = fecha.year - nacimiento.year - ((fecha.month, fecha.day) < (nacimiento.month, nacimiento.day))
        if not 4 <= edad < 18:
            raise ErrorValidacion("La escuela recibe alumnos de 4 a 17 años.")
        esperada = f"Sub-{2 * (edad // 2 + 1)}"
        if categoria != esperada:
            raise ErrorValidacion(f"Por su fecha de nacimiento, le corresponde la categoría {esperada}.")
        self.categoria = categoria

    def calcular_costo(self):
        return self.MENSUALIDAD
