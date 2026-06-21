"""
metrics_writer.py — Registro persistente de metricas en CSV.

Cada ejecucion de run_query.py agrega una fila al archivo metrics/metrics.csv.
El archivo se crea automaticamente si no existe, con encabezados.

Formato de columnas:
    timestamp, cuenta_id, intencion, tokens_prompt, tokens_completion,
    total_tokens, latency_ms, estimated_cost_usd, model, guardrail_aprobado
"""

from __future__ import annotations

import csv
from pathlib import Path

from schemas import MetricasEjecucion

_METRICS_DIR = Path(__file__).parent.parent / "metrics"
_METRICS_FILE = _METRICS_DIR / "metrics.csv"

_COLUMNAS = [
    "timestamp",
    "cuenta_id",
    "intencion",
    "tokens_prompt",
    "tokens_completion",
    "total_tokens",
    "latency_ms",
    "estimated_cost_usd",
    "model",
    "guardrail_aprobado",
]


def registrar_metrica(metricas: MetricasEjecucion) -> None:
    """
    Agrega una fila al archivo metrics/metrics.csv.

    Crea el directorio y el archivo con encabezados si no existen.
    El modo 'a' (append) garantiza que ejecuciones previas no se pierdan.

    Args:
        metricas: Instancia de MetricasEjecucion validada por Pydantic.
    """
    _METRICS_DIR.mkdir(parents=True, exist_ok=True)

    escribir_encabezado = not _METRICS_FILE.exists()

    with _METRICS_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_COLUMNAS)

        if escribir_encabezado:
            writer.writeheader()

        writer.writerow({
            "timestamp":           metricas.timestamp,
            "cuenta_id":           metricas.cuenta_id,
            "intencion":           metricas.intencion,
            "tokens_prompt":       metricas.tokens_prompt,
            "tokens_completion":   metricas.tokens_completion,
            "total_tokens":        metricas.total_tokens,
            "latency_ms":          metricas.latency_ms,
            "estimated_cost_usd":  metricas.estimated_cost_usd,
            "model":               metricas.model,
            "guardrail_aprobado":  metricas.guardrail_aprobado,
        })
