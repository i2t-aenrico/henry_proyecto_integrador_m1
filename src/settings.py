"""
settings.py — Configuracion del entorno y fabrica del LLM.

Centraliza la carga del .env y expone funciones perezosas (lazy) para
obtener el cliente de OpenAI. Lazy significa que la conexion se crea
la primera vez que se necesita, no al importar el modulo.
"""

from __future__ import annotations

import functools
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ---------------------------------------------------------------------------
# Constantes configurables via .env (con valores por defecto sensatos)
# ---------------------------------------------------------------------------

MODELO: str = os.getenv("MODELO", "gpt-4o-mini")

# Temperatura baja para respuestas bancarias: precision > creatividad.
TEMPERATURA: float = float(os.getenv("TEMPERATURA", "0.2"))

# Precios gpt-4o-mini (USD por 1M tokens) — actualizar si cambian.
PRECIO_INPUT_POR_MILLON: float = 0.15
PRECIO_OUTPUT_POR_MILLON: float = 0.60


@functools.lru_cache(maxsize=1)
def get_client() -> OpenAI:
    """
    Devuelve una instancia de OpenAI cacheada.

    lru_cache garantiza que se crea un solo cliente por proceso,
    evitando overhead de reconexion en ejecuciones con multiples consultas.

    Raises:
        EnvironmentError: si OPENAI_API_KEY no esta configurada.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY no encontrada. "
            "Copia .env.example a .env y completa tu clave de OpenAI."
        )
    return OpenAI(api_key=api_key)


def calcular_costo(tokens_prompt: int, tokens_completion: int) -> float:
    """
    Calcula el costo estimado en USD para una llamada a gpt-4o-mini.

    Usa los precios oficiales de OpenAI (input: $0.15/1M, output: $0.60/1M).
    El calculo es exacto (no estimacion) cuando se usan los tokens reales
    devueltos por la API en usage.prompt_tokens y usage.completion_tokens.

    Args:
        tokens_prompt: Tokens del prompt enviado.
        tokens_completion: Tokens de la respuesta recibida.

    Returns:
        Costo en USD redondeado a 6 decimales.
    """
    costo = (
        tokens_prompt * PRECIO_INPUT_POR_MILLON / 1_000_000
        + tokens_completion * PRECIO_OUTPUT_POR_MILLON / 1_000_000
    )
    return round(costo, 6)
