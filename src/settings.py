"""
settings.py — Configuracion del entorno y fabrica del LLM.

Soporta multiples proveedores via LiteLLM:
    - OpenAI:    MODELO=gpt-4o-mini        + OPENAI_API_KEY
    - Anthropic: MODELO=claude-haiku-4-5   + ANTHROPIC_API_KEY
    - Gemini:    MODELO=gemini/gemini-pro   + GEMINI_API_KEY

Cambiar de proveedor es cuestion de editar MODELO en el .env.
El resto del codigo no cambia.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Constantes configurables via .env
# ---------------------------------------------------------------------------

MODELO: str = os.getenv("MODELO", "gpt-4o-mini")

# Temperatura baja para respuestas bancarias: precision > creatividad.
TEMPERATURA: float = float(os.getenv("TEMPERATURA", "0.2"))

# ---------------------------------------------------------------------------
# Precios por proveedor (USD por 1M tokens input / output)
# Agregar nuevos modelos segun necesidad.
# ---------------------------------------------------------------------------

_PRECIOS: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o-mini":          (0.15,  0.60),
    "gpt-4o":               (2.50, 10.00),
    "gpt-4.1":              (2.00,  8.00),
    "gpt-4.1-mini":         (0.40,  1.60),
    # Anthropic
    "claude-haiku-4-5":     (0.80,  4.00),
    "claude-sonnet-4-5":    (3.00, 15.00),
    "claude-sonnet-4-6":    (3.00, 15.00),
    "claude-opus-4-6":     (15.00, 75.00),
}

def _precios_modelo() -> tuple[float, float]:
    """Devuelve (precio_input, precio_output) por millon de tokens para el modelo activo."""
    modelo_base = MODELO.split("/")[-1]  # gemini/gemini-pro -> gemini-pro
    for key, precios in _PRECIOS.items():
        if key in modelo_base:
            return precios
    # Default conservador si el modelo no esta en la tabla
    return (1.00, 3.00)


def calcular_costo(tokens_prompt: int, tokens_completion: int) -> float:
    """
    Calcula el costo estimado en USD para el modelo activo.

    Usa la tabla _PRECIOS para el modelo configurado en MODELO.
    Si el modelo no esta en la tabla, usa un precio conservador generico.

    Args:
        tokens_prompt: Tokens del prompt enviado.
        tokens_completion: Tokens de la respuesta recibida.

    Returns:
        Costo en USD redondeado a 6 decimales.
    """
    precio_input, precio_output = _precios_modelo()
    costo = (
        tokens_prompt    * precio_input  / 1_000_000
        + tokens_completion * precio_output / 1_000_000
    )
    return round(costo, 6)


def validar_credenciales() -> None:
    """
    Verifica que la API key correspondiente al proveedor este configurada.

    Raises:
        EnvironmentError: si falta la clave del proveedor detectado.
    """
    modelo_lower = MODELO.lower()

    if "claude" in modelo_lower:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise EnvironmentError(
                f"ANTHROPIC_API_KEY no encontrada para el modelo '{MODELO}'. "
                "Agregala al .env."
            )
    elif "gemini" in modelo_lower:
        if not os.getenv("GEMINI_API_KEY"):
            raise EnvironmentError(
                f"GEMINI_API_KEY no encontrada para el modelo '{MODELO}'. "
                "Agregala al .env."
            )
    else:
        # Default: OpenAI
        if not os.getenv("OPENAI_API_KEY"):
            raise EnvironmentError(
                f"OPENAI_API_KEY no encontrada para el modelo '{MODELO}'. "
                "Copia .env.example a .env y completa tu clave."
            )
