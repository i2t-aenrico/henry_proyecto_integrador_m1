"""
tools.py — Herramientas de consulta bancaria.

Cada funcion es determinista (sin LLM): recibe parametros tipados,
consulta la base de datos simulada y devuelve un resultado estructurado
en JSON o un mensaje de error que el sistema puede interpretar.

El guardrail de seguridad (auditar_respeto, auditar_entrada) vive en
safety.py — no en este archivo.
"""

from __future__ import annotations

import json
import random

from database import CAMPOS_ACTUALIZABLES, CUENTAS, MOVIMIENTOS
from schemas import (
    Movimiento,
    ResultadoActualizacion,
    ResultadoResetClave,
    ResumenCuenta,
    Saldo,
)


# ---------------------------------------------------------------------------
# Herramienta 1: consultar_saldo
# ---------------------------------------------------------------------------

def consultar_saldo(cuenta_id: str) -> str:
    """
    Consulta el saldo disponible y contable de una cuenta bancaria.

    Args:
        cuenta_id: Identificador de la cuenta, por ejemplo 'CTA001'.

    Returns:
        JSON con saldo_disponible, saldo_contable, moneda y titular.
        Solo expone los ultimos 4 digitos del numero de cuenta.
    """
    cuenta = CUENTAS.get(cuenta_id.upper())
    if not cuenta:
        return json.dumps({"error": f"No se encontro la cuenta '{cuenta_id}'."})

    resultado = Saldo(
        cuenta_id=cuenta_id.upper(),
        ultimos_cuatro=cuenta["ultimos_cuatro"],
        saldo_disponible=cuenta["saldo_disponible"],
        saldo_contable=cuenta["saldo_contable"],
        moneda=cuenta["moneda"],
        titular=cuenta["titular"],
    )
    return resultado.model_dump_json()


# ---------------------------------------------------------------------------
# Herramienta 2: obtener_resumen
# ---------------------------------------------------------------------------

def obtener_resumen(cuenta_id: str, periodo: str) -> str:
    """
    Obtiene el resumen de movimientos de una cuenta para un periodo dado.

    Args:
        cuenta_id: Identificador de la cuenta, por ejemplo 'CTA001'.
        periodo: Periodo en formato 'mes anio', por ejemplo 'mayo 2025'.

    Returns:
        JSON con la lista de movimientos y totales de debitos y creditos.
    """
    periodo_norm = periodo.lower().strip()
    clave = (cuenta_id.upper(), periodo_norm)
    cuenta = CUENTAS.get(cuenta_id.upper())

    if not cuenta:
        return json.dumps({"error": f"No se encontro la cuenta '{cuenta_id}'."})

    movimientos_raw = MOVIMIENTOS.get(clave)
    if movimientos_raw is None:
        periodos_disponibles = [k[1] for k in MOVIMIENTOS if k[0] == cuenta_id.upper()]
        return json.dumps({
            "error": (
                f"No se encontraron movimientos para '{cuenta_id}' "
                f"en el periodo '{periodo}'."
            ),
            "periodos_disponibles": periodos_disponibles,
        })

    movimientos = [Movimiento(**m) for m in movimientos_raw]
    total_creditos = sum(m.importe for m in movimientos if m.importe > 0)
    total_debitos  = sum(m.importe for m in movimientos if m.importe < 0)

    resultado = ResumenCuenta(
        cuenta_id=cuenta_id.upper(),
        ultimos_cuatro=cuenta["ultimos_cuatro"],
        titular=cuenta["titular"],
        periodo=periodo_norm,
        movimientos=movimientos,
        total_debitos=total_debitos,
        total_creditos=total_creditos,
    )
    return resultado.model_dump_json()


# ---------------------------------------------------------------------------
# Herramienta 3: iniciar_reset_clave
# ---------------------------------------------------------------------------

def iniciar_reset_clave(cuenta_id: str, canal: str) -> str:
    """
    Inicia el proceso de recuperacion de clave de acceso al home banking.

    Args:
        cuenta_id: Identificador de la cuenta.
        canal: Canal de recuperacion: 'email', 'sms' o 'sucursal'.

    Returns:
        JSON con el destino enmascarado, codigo de referencia e instrucciones.
    """
    canales_validos = ("email", "sms", "sucursal")
    canal_norm = canal.lower().strip()

    if canal_norm not in canales_validos:
        return json.dumps({
            "error": (
                f"Canal '{canal}' no valido. "
                f"Opciones disponibles: {', '.join(canales_validos)}."
            )
        })

    cuenta = CUENTAS.get(cuenta_id.upper())
    if not cuenta:
        return json.dumps({"error": f"No se encontro la cuenta '{cuenta_id}'."})

    if canal_norm == "email":
        email = cuenta["email"]
        partes = email.split("@")
        destino = partes[0][0] + "***" + partes[0][-1] + "@" + partes[1]
    elif canal_norm == "sms":
        tel = cuenta["telefono"]
        destino = tel[:7] + "*** ***" + tel[-4:]
    else:
        destino = "cualquier sucursal con DNI"

    referencia = f"RST-{random.randint(100000, 999999)}"

    instrucciones = {
        "email":    f"Se enviara un enlace de recuperacion a {destino}. Vence en 30 minutos.",
        "sms":      f"Se enviara un codigo de 6 digitos a {destino}. Vence en 10 minutos.",
        "sucursal": "Presentese en cualquier sucursal con su DNI.",
    }

    resultado = ResultadoResetClave(
        canal=canal_norm,  # type: ignore[arg-type]
        destino_enmascarado=destino,
        referencia=referencia,
        mensaje=instrucciones[canal_norm],
    )
    return resultado.model_dump_json()


# ---------------------------------------------------------------------------
# Herramienta 4: actualizar_dato
# ---------------------------------------------------------------------------

def actualizar_dato(cuenta_id: str, campo: str, valor: str) -> str:
    """
    Actualiza un dato personal del cliente: email, telefono o direccion.

    Args:
        cuenta_id: Identificador de la cuenta.
        campo: Campo a actualizar: 'email', 'telefono' o 'direccion'.
        valor: Nuevo valor para el campo.

    Returns:
        JSON indicando si la actualizacion fue exitosa.
    """
    campo_norm = campo.lower().strip()

    if campo_norm not in CAMPOS_ACTUALIZABLES:
        return json.dumps({
            "error": (
                f"Campo '{campo}' no modificable. "
                f"Campos permitidos: {', '.join(CAMPOS_ACTUALIZABLES.keys())}."
            )
        })

    cuenta = CUENTAS.get(cuenta_id.upper())
    if not cuenta:
        return json.dumps({"error": f"No se encontro la cuenta '{cuenta_id}'."})

    if not valor or not valor.strip():
        return json.dumps({"error": f"El valor para '{campo}' no puede estar vacio."})

    CUENTAS[cuenta_id.upper()][campo_norm] = valor.strip()

    nombre_campo = CAMPOS_ACTUALIZABLES[campo_norm]
    resultado = ResultadoActualizacion(
        campo=nombre_campo,
        exito=True,
        mensaje=(
            f"{nombre_campo} actualizado correctamente. "
            f"El cambio puede demorar hasta 24 hs en reflejarse en todos los canales."
        ),
    )
    return resultado.model_dump_json()


# ---------------------------------------------------------------------------
# Mapa de herramientas disponibles para el agente
# ---------------------------------------------------------------------------

HERRAMIENTAS: dict[str, object] = {
    "consultar_saldo":     consultar_saldo,
    "obtener_resumen":     obtener_resumen,
    "iniciar_reset_clave": iniciar_reset_clave,
    "actualizar_dato":     actualizar_dato,
}
