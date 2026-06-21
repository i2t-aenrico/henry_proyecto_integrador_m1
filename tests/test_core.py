"""
test_core.py — Tests automatizados del asistente bancario.

Ejecucion:
    pytest tests/test_core.py -v

Los tests NO consumen tokens (no llaman a la API de OpenAI):
- Las herramientas son deterministicas y no usan LLM.
- El guardrail es una funcion pura.
- La validacion de JSON se hace con instancias mock.

Cobertura:
    1. Herramientas deterministicas (consultar_saldo, obtener_resumen,
       iniciar_reset_clave, actualizar_dato).
    2. Guardrail de seguridad: cada regla debe rechazar correctamente.
    3. Validacion del schema JSON de salida (RespuestaAsistente).
    4. Deteccion de intencion por keywords.
    5. Calculo de costo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Agregar src/ al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from database import CUENTAS
from schemas import RespuestaAsistente, MetricasEjecucion
from tools import (
    consultar_saldo,
    obtener_resumen,
    iniciar_reset_clave,
    actualizar_dato,
)
from safety import auditar_respeto
from settings import calcular_costo
from run_query import detectar_intencion


# ===========================================================================
# 1. Herramientas deterministicas
# ===========================================================================

class TestConsultarSaldo:
    def test_cuenta_existente(self) -> None:
        resultado = json.loads(consultar_saldo("CTA001"))
        assert resultado["cuenta_id"] == "CTA001"
        assert resultado["ultimos_cuatro"] == "3456"
        assert resultado["saldo_disponible"] == 158_430.75
        assert resultado["moneda"] == "ARS"

    def test_cuenta_lowercase(self) -> None:
        """El ID de cuenta debe aceptarse en minusculas."""
        resultado = json.loads(consultar_saldo("cta001"))
        assert resultado["cuenta_id"] == "CTA001"

    def test_cuenta_inexistente(self) -> None:
        resultado = json.loads(consultar_saldo("CTA999"))
        assert "error" in resultado

    def test_no_expone_numero_completo(self) -> None:
        """La herramienta nunca debe exponer el numero de cuenta completo."""
        resultado_str = consultar_saldo("CTA001")
        assert "0720-0001-00012345-6" not in resultado_str


class TestObtenerResumen:
    def test_periodo_existente(self) -> None:
        resultado = json.loads(obtener_resumen("CTA001", "mayo 2025"))
        assert resultado["periodo"] == "mayo 2025"
        assert len(resultado["movimientos"]) == 9
        assert resultado["total_creditos"] > 0
        assert resultado["total_debitos"] < 0

    def test_periodo_inexistente(self) -> None:
        resultado = json.loads(obtener_resumen("CTA001", "enero 2020"))
        assert "error" in resultado
        assert "periodos_disponibles" in resultado

    def test_cuenta_inexistente(self) -> None:
        resultado = json.loads(obtener_resumen("CTA999", "mayo 2025"))
        assert "error" in resultado

    def test_totales_son_correctos(self) -> None:
        resultado = json.loads(obtener_resumen("CTA001", "mayo 2025"))
        movimientos = resultado["movimientos"]
        creditos_calculados = sum(m["importe"] for m in movimientos if m["importe"] > 0)
        debitos_calculados  = sum(m["importe"] for m in movimientos if m["importe"] < 0)
        assert abs(resultado["total_creditos"] - creditos_calculados) < 0.01
        assert abs(resultado["total_debitos"]  - debitos_calculados)  < 0.01


class TestIniciarResetClave:
    def test_canal_email(self) -> None:
        resultado = json.loads(iniciar_reset_clave("CTA001", "email"))
        assert resultado["canal"] == "email"
        assert "referencia" in resultado
        assert resultado["referencia"].startswith("RST-")
        # El email debe estar enmascarado
        assert "jcmendez@gmail.com" not in resultado["destino_enmascarado"]

    def test_canal_sms(self) -> None:
        resultado = json.loads(iniciar_reset_clave("CTA001", "sms"))
        assert resultado["canal"] == "sms"

    def test_canal_sucursal(self) -> None:
        resultado = json.loads(iniciar_reset_clave("CTA001", "sucursal"))
        assert resultado["canal"] == "sucursal"
        assert "DNI" in resultado["mensaje"]

    def test_canal_invalido(self) -> None:
        resultado = json.loads(iniciar_reset_clave("CTA001", "whatsapp"))
        assert "error" in resultado

    def test_referencia_es_unica(self) -> None:
        """Dos llamadas deben generar referencias distintas (probabilisticamente)."""
        r1 = json.loads(iniciar_reset_clave("CTA001", "email"))["referencia"]
        r2 = json.loads(iniciar_reset_clave("CTA001", "email"))["referencia"]
        # Con numeros de 6 digitos la probabilidad de colision es 1/900000
        assert r1 != r2


class TestActualizarDato:
    def test_actualizar_email(self) -> None:
        resultado = json.loads(actualizar_dato("CTA002", "email", "nuevo@test.com"))
        assert resultado["exito"] is True
        assert CUENTAS["CTA002"]["email"] == "nuevo@test.com"

    def test_campo_invalido(self) -> None:
        resultado = json.loads(actualizar_dato("CTA001", "saldo", "999999"))
        assert "error" in resultado

    def test_valor_vacio(self) -> None:
        resultado = json.loads(actualizar_dato("CTA001", "email", ""))
        assert "error" in resultado

    def test_cuenta_inexistente(self) -> None:
        resultado = json.loads(actualizar_dato("CTA999", "email", "x@x.com"))
        assert "error" in resultado


# ===========================================================================
# 2. Guardrail de seguridad
# ===========================================================================

class TestGuardrail:
    def test_respuesta_valida_aprueba(self) -> None:
        respuesta = "Su saldo disponible en la cuenta terminada en 3456 es de $158.430,75."
        auditoria = auditar_respeto(respuesta)
        assert auditoria.aprobado is True
        assert len(auditoria.motivos) == 0

    def test_regla1_numero_cuenta_completo(self) -> None:
        """Una respuesta con el numero completo SIEMPRE debe ser rechazada."""
        respuesta = "Su cuenta 0720-0001-00012345-6 tiene saldo disponible."
        auditoria = auditar_respeto(respuesta)
        assert auditoria.aprobado is False
        assert any("numero de cuenta completo" in m for m in auditoria.motivos)

    def test_regla2_respuesta_vacia(self) -> None:
        auditoria = auditar_respeto("")
        assert auditoria.aprobado is False

    def test_regla2_respuesta_muy_corta(self) -> None:
        auditoria = auditar_respeto("OK")
        assert auditoria.aprobado is False

    def test_regla3_palabras_prohibidas(self) -> None:
        respuesta = "No sea idiota, lea el manual antes de llamar."
        auditoria = auditar_respeto(respuesta)
        assert auditoria.aprobado is False
        assert any("inapropiado" in m for m in auditoria.motivos)

    def test_regla4_canal_externo(self) -> None:
        respuesta = "Por favor escribanos a soporte@terceros.com para resolver su problema."
        auditoria = auditar_respeto(respuesta)
        assert auditoria.aprobado is False

    def test_multiples_violaciones(self) -> None:
        """Una respuesta puede violar mas de una regla a la vez."""
        respuesta = "OK"  # muy corta y potencialmente vacia
        auditoria = auditar_respeto(respuesta)
        assert auditoria.aprobado is False
        assert len(auditoria.motivos) >= 1


# ===========================================================================
# 3. Validacion del schema JSON de salida
# ===========================================================================

class TestRespuestaAsistente:
    def test_instancia_valida(self) -> None:
        r = RespuestaAsistente(
            answer="Su saldo es de $100.000,00.",
            confidence=0.95,
            intent="consulta_saldo",
            actions=[],
            data={"saldo": 100000.0},
        )
        assert r.confidence == 0.95
        assert r.intent == "consulta_saldo"

    def test_confidence_fuera_de_rango(self) -> None:
        with pytest.raises(Exception):
            RespuestaAsistente(
                answer="Respuesta de prueba para el test.",
                confidence=1.5,  # invalido
                intent="consulta_saldo",
            )

    def test_intent_invalido(self) -> None:
        with pytest.raises(Exception):
            RespuestaAsistente(
                answer="Respuesta de prueba para el test.",
                confidence=0.9,
                intent="intencion_inventada",  # invalido
            )

    def test_answer_muy_corto(self) -> None:
        with pytest.raises(Exception):
            RespuestaAsistente(
                answer="Hi",  # menos de 10 caracteres
                confidence=0.9,
                intent="consulta_saldo",
            )

    def test_serializa_a_json(self) -> None:
        r = RespuestaAsistente(
            answer="Su saldo es de $158.430,75 en la cuenta terminada en 3456.",
            confidence=0.98,
            intent="consulta_saldo",
            actions=[],
            data={},
        )
        datos = json.loads(r.model_dump_json())
        assert "answer" in datos
        assert "confidence" in datos
        assert "intent" in datos
        assert "actions" in datos
        assert "data" in datos


# ===========================================================================
# 4. Deteccion de intencion
# ===========================================================================

class TestDetectarIntencion:
    @pytest.mark.parametrize("mensaje,esperado", [
        ("cuanto tengo en la cuenta",   "consulta_saldo"),
        ("quiero ver mi saldo",          "consulta_saldo"),
        ("olvide mi clave",              "gestion_clave"),
        ("no puedo entrar al home",      "gestion_clave"),
        ("dame el resumen de mayo",      "resumen_cuenta"),
        ("quiero el extracto",           "resumen_cuenta"),
        ("quiero cambiar mi email",      "datos_personales"),
        ("actualizar mi telefono",       "datos_personales"),
        ("precio del dolar",             "no_reconocido"),
    ])
    def test_intencion(self, mensaje: str, esperado: str) -> None:
        assert detectar_intencion(mensaje) == esperado


# ===========================================================================
# 5. Calculo de costo
# ===========================================================================

class TestCalcularCosto:
    def test_cero_tokens(self) -> None:
        assert calcular_costo(0, 0) == 0.0

    def test_calculo_conocido(self) -> None:
        """
        1000 tokens prompt  @ $0.15/1M = $0.00015
        500  tokens output  @ $0.60/1M = $0.00030
        Total = $0.00045
        """
        costo = calcular_costo(1000, 500)
        assert abs(costo - 0.00045) < 1e-9

    def test_siempre_positivo(self) -> None:
        assert calcular_costo(100, 50) >= 0.0
