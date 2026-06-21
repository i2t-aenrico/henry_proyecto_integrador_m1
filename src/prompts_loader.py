"""
prompts_loader.py — Re-exporta los prompts definidos en prompts/main_prompt.txt.

Carga el archivo de texto una sola vez y expone SYSTEM_ASISTENTE y
TEMPLATE_USUARIO como constantes importables desde el resto del proyecto.
El archivo .txt es la fuente de verdad; este modulo solo lo lee.
"""

from __future__ import annotations

import re
from pathlib import Path

_ARCHIVO = Path(__file__).parent.parent / "prompts" / "main_prompt.txt"
_texto = _ARCHIVO.read_text(encoding="utf-8")

# Extraer SYSTEM_ASISTENTE (entre las primeras comillas triples del archivo)
_m_system = re.search(
    r'SYSTEM_ASISTENTE\s*=\s*"""\\\n(.*?)\n"""',
    _texto,
    re.DOTALL,
)
SYSTEM_ASISTENTE: str = _m_system.group(1) if _m_system else ""

# Extraer TEMPLATE_USUARIO (entre las segundas comillas triples)
_m_tmpl = re.search(
    r'TEMPLATE_USUARIO\s*=\s*"""\\\n(.*?)\n"""',
    _texto,
    re.DOTALL,
)
TEMPLATE_USUARIO: str = _m_tmpl.group(1) if _m_tmpl else ""

if not SYSTEM_ASISTENTE or not TEMPLATE_USUARIO:
    raise RuntimeError(
        f"No se pudieron extraer los prompts de {_ARCHIVO}. "
        "Verificar que el archivo tenga el formato correcto."
    )
