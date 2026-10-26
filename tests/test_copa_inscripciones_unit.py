from decimal import Decimal

import copa_inscripciones as inscripciones


def test_acuerdo_de_inscripcion_no_genera_ingreso_y_carnets_quedan_completos():
    team = {
        "equipo": "Colombia", "carnets_cantidad": 14,
        "inscripcion_inicial": Decimal("0"), "carnets_inicial": Decimal("3"),
        "inscripcion_completa_inicial": True, "carnets_completos_inicial": False,
        "inscripcion_acuerdo": True,
    }
    payments = [{
        "equipo": "Colombia", "concepto": "CARNETS", "monto": Decimal("6.50"),
        "anulado_en": None,
    }]
    totals = inscripciones._totales(team, payments)
    assert totals["inscripcion"]["pendiente"] == 0
    assert totals["inscripcion"]["acuerdo"] is True
    assert totals["inscripcion"]["cobrado_nuevo"] == 0
    assert totals["carnets"]["abono_inicial"] == Decimal("3")
    assert totals["carnets"]["cobrado_nuevo"] == Decimal("6.50")
    assert totals["carnets"]["pendiente"] == 0
