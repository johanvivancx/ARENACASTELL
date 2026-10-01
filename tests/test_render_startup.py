"""Comprueba que el servidor conserve el modo local y acepte el puerto de Render."""

import pytest

from server import direccion_escucha


def test_escucha_local_sin_port(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setattr("server.ORIGIN", "http://127.0.0.1:8765")
    assert direccion_escucha() == ("127.0.0.1", 8765)


def test_escucha_render_con_port(monkeypatch):
    monkeypatch.setenv("PORT", "10000")
    assert direccion_escucha() == ("0.0.0.0", 10000)


@pytest.mark.parametrize("value", ["0", "65536", "no-es-un-puerto"])
def test_rechaza_port_invalido(monkeypatch, value):
    monkeypatch.setenv("PORT", value)
    with pytest.raises(ValueError):
        direccion_escucha()
