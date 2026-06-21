"""
schemas.py — Contratos de datos del asistente bancario.

Cada clase define la forma exacta de un dato que entra o sale del sistema.
El LLM nunca devuelve texto libre cuando se necesita tomar una decision:
siempre devuelve uno de estos esquemas validados por Pydantic.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Intenciones reconocidas por el router
# ---------------------------------------------------------------------------

TipoIntencion = Literal[
    "consulta_saldo",
    "gestion_clave",
    "resumen_cuenta",
    "datos_personales",
    "no_reconocido",
]

CanalReset = Literal["email", "sms", "sucursal"]


# ---------------------------------------------------------------------------
# Salida principal del asistente (contrato JSON hacia downstream)
# ---------------------------------------------------------------------------

class RespuestaAsistente(BaseModel):
    """
    Salida estructurada del asistente bancario.

    Este es el contrato JSON que el sistema devuelve por cada consulta.
    Cualquier sistema downstream puede consumirlo sin transformaciones.
    """

    answer: str = Field(
        description="Respuesta en lenguaje natural para el cliente.",
        min_length=10,
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confianza del modelo en la respuesta (0.0 a 1.0).",
    )
    intent: TipoIntencion = Field(
        description="Intencion detectada en la consulta del cliente.",
    )
    actions: list[str] = Field(
        default_factory=list,
        description="Pasos concretos que el cliente debe seguir.",
    )
    data: dict = Field(
        default_factory=dict,
        description="Datos estructurados adicionales (saldo, movimientos, etc.).",
    )


# ---------------------------------------------------------------------------
# Salidas de herramientas internas
# ---------------------------------------------------------------------------

class Saldo(BaseModel):
    """Resultado de consultar_saldo."""

    cuenta_id: str = Field(description="Identificador interno de la cuenta.")
    ultimos_cuatro: str = Field(
        description="Ultimos 4 digitos del numero de cuenta.",
        min_length=4,
        max_length=4,
    )
    saldo_disponible: float = Field(description="Saldo disponible en pesos.")
    saldo_contable: float = Field(description="Saldo contable en pesos.")
    moneda: str = Field(default="ARS", description="Moneda de la cuenta.")
    titular: str = Field(description="Nombre del titular de la cuenta.")


class Movimiento(BaseModel):
    """Un unico movimiento de cuenta."""

    fecha: str = Field(description="Fecha del movimiento en formato DD/MM/YYYY.")
    descripcion: str = Field(description="Descripcion del movimiento.")
    importe: float = Field(description="Importe del movimiento (negativo = debito).")
    saldo_posterior: float = Field(description="Saldo luego del movimiento.")


class ResumenCuenta(BaseModel):
    """Resultado de obtener_resumen."""

    cuenta_id: str
    ultimos_cuatro: str = Field(min_length=4, max_length=4)
    titular: str
    periodo: str = Field(description="Periodo consultado, ej: 'mayo 2025'.")
    movimientos: list[Movimiento] = Field(description="Lista de movimientos del periodo.")
    total_debitos: float
    total_creditos: float


class ResultadoResetClave(BaseModel):
    """Resultado de iniciar_reset_clave."""

    canal: CanalReset
    destino_enmascarado: str = Field(
        description="Destino del reset con datos parciales."
    )
    referencia: str = Field(description="Codigo de referencia del tramite.")
    mensaje: str = Field(description="Instrucciones para el cliente.")


class ResultadoActualizacion(BaseModel):
    """Resultado de actualizar_dato."""

    campo: str
    exito: bool
    mensaje: str


class AuditoriaGuardrail(BaseModel):
    """
    Resultado del guardrail de seguridad.

    Esta validacion ocurre en codigo (no en el LLM): si aprobado=False
    el sistema rechaza la respuesta y devuelve un error controlado.
    """

    aprobado: bool = Field(
        description="True si la respuesta paso todas las reglas de seguridad."
    )
    motivos: list[str] = Field(
        default_factory=list,
        description="Lista de motivos de rechazo (vacia si aprobado=True).",
    )


# ---------------------------------------------------------------------------
# Metricas de ejecucion
# ---------------------------------------------------------------------------

class MetricasEjecucion(BaseModel):
    """Registro de metricas por cada llamada a la API."""

    timestamp: str = Field(description="Fecha y hora de la ejecucion (ISO 8601).")
    cuenta_id: str = Field(description="ID de la cuenta consultada.")
    intencion: str = Field(description="Intencion detectada.")
    tokens_prompt: int = Field(ge=0, description="Tokens del prompt enviado.")
    tokens_completion: int = Field(ge=0, description="Tokens de la respuesta recibida.")
    total_tokens: int = Field(ge=0, description="Total de tokens consumidos.")
    latency_ms: float = Field(ge=0.0, description="Latencia de la llamada en milisegundos.")
    estimated_cost_usd: float = Field(ge=0.0, description="Costo estimado en USD.")
    model: str = Field(description="Modelo de OpenAI utilizado.")
    guardrail_aprobado: bool = Field(description="True si paso el guardrail de seguridad.")
