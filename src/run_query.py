"""
run_query.py — Asistente bancario con salida estructurada en JSON.

Uso:
    python run_query.py -m "cuanto tengo en la cuenta?"
    python run_query.py -m "olvide mi clave" --cuenta CTA002
    python run_query.py -m "dame el resumen de mayo 2025" --cuenta CTA001
    python run_query.py -m "quiero cambiar mi email a nuevo@gmail.com" --cuenta CTA003
    python run_query.py -m "consulta de saldo" --dry-run   # sin llamar a la API

Cada ejecucion registra las metricas en metrics/metrics.csv.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Agrega src/ al path para imports relativos
sys.path.insert(0, str(Path(__file__).parent / "src"))

from settings import MODELO, TEMPERATURA, calcular_costo, validar_credenciales
from schemas import MetricasEjecucion, RespuestaAsistente
from tools import HERRAMIENTAS, consultar_saldo, obtener_resumen
from safety import auditar_entrada, auditar_respeto, FALLBACK_ADVERSARIAL
from prompts_loader import SYSTEM_ASISTENTE, TEMPLATE_USUARIO
from metrics_writer import registrar_metrica

# ---------------------------------------------------------------------------
# Clasificacion de intencion (sin LLM — reglas deterministicas simples)
# ---------------------------------------------------------------------------

_KEYWORDS: dict[str, list[str]] = {
    "consulta_saldo":   ["saldo", "plata", "cuanto tengo", "dinero", "disponible", "cuanto hay"],
    "gestion_clave":    ["clave", "contrasena", "password", "no puedo entrar", "bloqueo", "olvide", "acceso"],
    "resumen_cuenta":   ["resumen", "movimientos", "extracto", "historial", "mayo", "abril", "junio", "periodo"],
    "datos_personales": ["email", "correo", "telefono", "direccion", "domicilio", "actualizar", "cambiar"],
}


def detectar_intencion(mensaje: str) -> str:
    """
    Clasifica la intencion del cliente por coincidencia de keywords.

    Esta clasificacion pre-LLM sirve para determinar que herramienta
    ejecutar antes de la llamada principal. No reemplaza al LLM: el
    modelo puede corregir la intencion en su respuesta JSON.

    Args:
        mensaje: Mensaje del cliente en lenguaje natural.

    Returns:
        Una de las 5 intenciones posibles.
    """
    msg_lower = mensaje.lower()
    scores: dict[str, int] = {intent: 0 for intent in _KEYWORDS}

    for intent, keywords in _KEYWORDS.items():
        for kw in keywords:
            if kw in msg_lower:
                scores[intent] += 1

    mejor = max(scores, key=lambda k: scores[k])
    return mejor if scores[mejor] > 0 else "no_reconocido"


def ejecutar_herramienta(intencion: str, cuenta_id: str, mensaje: str) -> str:
    """
    Ejecuta la herramienta correspondiente a la intencion detectada.

    Devuelve el resultado como string JSON para incluirlo en el prompt.
    Si no hay herramienta aplicable, devuelve una cadena vacia.

    Args:
        intencion: Intencion detectada por detectar_intencion().
        cuenta_id: ID de la cuenta del cliente autenticado.
        mensaje: Mensaje original del cliente (para extraer parametros).

    Returns:
        Resultado de la herramienta en formato JSON, o "" si no aplica.
    """
    msg_lower = mensaje.lower()

    if intencion == "consulta_saldo":
        return consultar_saldo(cuenta_id)

    if intencion == "resumen_cuenta":
        # Extraer periodo del mensaje (busca "mes anio")
        meses = [
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
        ]
        periodo = "mayo 2025"  # valor por defecto
        for mes in meses:
            if mes in msg_lower:
                # Buscar anio de 4 digitos cerca del mes
                import re
                match = re.search(r"\b(20\d{2})\b", msg_lower)
                anio = match.group(1) if match else "2025"
                periodo = f"{mes} {anio}"
                break
        from tools import obtener_resumen
        return obtener_resumen(cuenta_id, periodo)

    if intencion == "gestion_clave":
        # Detectar canal preferido en el mensaje
        canal = "email"
        if "sms" in msg_lower or "celular" in msg_lower or "telefono" in msg_lower:
            canal = "sms"
        elif "sucursal" in msg_lower or "presencial" in msg_lower:
            canal = "sucursal"
        from tools import iniciar_reset_clave
        return iniciar_reset_clave(cuenta_id, canal)

    if intencion == "datos_personales":
        # Detectar campo y valor — simplificado para el demo
        from tools import actualizar_dato
        campos = {"email": "email", "correo": "email", "telefono": "telefono",
                  "celular": "telefono", "direccion": "direccion", "domicilio": "direccion"}
        campo_detectado = None
        for kw, campo in campos.items():
            if kw in msg_lower:
                campo_detectado = campo
                break
        if campo_detectado:
            # Extraer el nuevo valor (todo lo que aparece despues de "a " o "por ")
            import re
            match = re.search(r"(?:a |por |nuevo[: ]+)([^\s,\.]+(?:\.[^\s,\.]+)*)", msg_lower)
            nuevo_valor = match.group(1) if match else "PENDIENTE_DE_CONFIRMACION"
            return actualizar_dato(cuenta_id, campo_detectado, nuevo_valor)

    return ""  # sin herramienta para no_reconocido


# ---------------------------------------------------------------------------
# Llamada principal a la API de OpenAI
# ---------------------------------------------------------------------------

def llamar_llm(
    cuenta_id: str,
    mensaje: str,
    resultados_herramientas: str,
    dry_run: bool = False,
) -> tuple[RespuestaAsistente, MetricasEjecucion]:
    """
    Llama a la API de OpenAI con el prompt few-shot + CoT y devuelve
    la respuesta validada con Pydantic junto a las metricas de la llamada.

    Args:
        cuenta_id: ID de la cuenta del cliente.
        mensaje: Mensaje original del cliente.
        resultados_herramientas: JSON de la herramienta ejecutada, o "Ninguna."
        dry_run: Si es True, omite la llamada real a la API.

    Returns:
        Tupla (RespuestaAsistente, MetricasEjecucion).
    """
    intencion_pre = detectar_intencion(mensaje)

    prompt_usuario = TEMPLATE_USUARIO.format(
        cuenta_id=cuenta_id,
        resultados_herramientas=resultados_herramientas or "Ninguna herramienta ejecutada.",
        mensaje=mensaje,
    )

    if dry_run:
        respuesta_mock = RespuestaAsistente(
            answer="[DRY RUN] Respuesta simulada sin llamar a la API.",
            confidence=1.0,
            intent=intencion_pre,  # type: ignore[arg-type]
            actions=["Este es un dry-run; no se realizo ninguna llamada real."],
            data={},
        )
        metricas_mock = MetricasEjecucion(
            timestamp=datetime.now(timezone.utc).isoformat(),
            cuenta_id=cuenta_id,
            intencion=intencion_pre,
            tokens_prompt=0,
            tokens_completion=0,
            total_tokens=0,
            latency_ms=0.0,
            estimated_cost_usd=0.0,
            model=MODELO,
            guardrail_aprobado=True,
        )
        return respuesta_mock, metricas_mock

    validar_credenciales()
    inicio = time.perf_counter()

    import litellm
    # response_format json_object solo lo soporta OpenAI.
    # Claude y Gemini lo ignoran o tiran error — el JSON se pide via prompt.
    modelo_lower = MODELO.lower()
    kwargs = dict(
        model=MODELO,
        temperature=TEMPERATURA,
        messages=[
            {"role": "system", "content": SYSTEM_ASISTENTE},
            {"role": "user",   "content": prompt_usuario},
        ]
    )
    if "gpt" in modelo_lower or "o1" in modelo_lower:
        kwargs["response_format"] = {"type": "json_object"}

    raw = litellm.completion(**kwargs)
    
    latencia_ms = (time.perf_counter() - inicio) * 1000

    # Tokens reales devueltos por la API (no estimacion)
    tokens_prompt     = raw.usage.prompt_tokens
    tokens_completion = raw.usage.completion_tokens
    total_tokens      = raw.usage.total_tokens
    costo             = calcular_costo(tokens_prompt, tokens_completion)

    contenido_raw = raw.choices[0].message.content or "{}"
    
    # Claude devuelve el JSON envuelto en ```json ... ``` y con <thinking> afuera.
    # Limpiamos ambos antes de parsear.
    import re as _re
    # 1. Extraer bloque ```json ... ``` si existe
    _match_json = _re.search(r"```json\s*([\s\S]*?)\s*```", contenido_raw)
    if _match_json:
        contenido = _match_json.group(1).strip()
    else:
        # 2. Si no hay backticks, eliminar bloque <thinking>...</thinking>
        contenido = _re.sub(r"<thinking>[\s\S]*?</thinking>", "", contenido_raw).strip()
        # 3. Si empieza con { es JSON directo
        if not contenido.startswith("{"):
            contenido = "{}"

    # Parsear y validar con Pydantic
    try:
        datos = json.loads(contenido)
        # Eliminar bloque <thinking> si el modelo lo incluyo en el JSON
        datos.pop("thinking", None)
        respuesta = RespuestaAsistente(**datos)
    except Exception as exc:
        # Si el JSON es invalido, devolver un fallback controlado
        respuesta = RespuestaAsistente(
            answer=(
                "Hubo un inconveniente al procesar tu consulta. "
                "Por favor, intenta de nuevo o comunicate con nosotros al 0800-333-2265."
            ),
            confidence=0.0,
            intent="no_reconocido",
            actions=["Llamar al 0800-333-2265"],
            data={"parse_error": str(exc)},
        )

    # Guardrail de seguridad en codigo
    auditoria = auditar_respeto(respuesta.answer)
    if not auditoria.aprobado:
        respuesta = RespuestaAsistente(
            answer=(
                "Tu consulta fue procesada, pero la respuesta generada no paso "
                "los controles de seguridad. Por favor, comunicate con nosotros "
                "al 0800-333-2265 para recibir asistencia personalizada."
            ),
            confidence=0.5,
            intent=respuesta.intent,
            actions=["Llamar al 0800-333-2265"],
            data={"guardrail_motivos": auditoria.motivos},
        )

    metricas = MetricasEjecucion(
        timestamp=datetime.now(timezone.utc).isoformat(),
        cuenta_id=cuenta_id,
        intencion=respuesta.intent,
        tokens_prompt=tokens_prompt,
        tokens_completion=tokens_completion,
        total_tokens=total_tokens,
        latency_ms=round(latencia_ms, 2),
        estimated_cost_usd=costo,
        model=MODELO,
        guardrail_aprobado=auditoria.aprobado,
    )

    return respuesta, metricas


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parsear_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Asistente bancario — devuelve JSON estructurado por consulta.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python run_query.py -m "cuanto tengo en la cuenta?"
  python run_query.py -m "olvide mi clave" --cuenta CTA002
  python run_query.py -m "dame el resumen de mayo 2025" --cuenta CTA001
  python run_query.py -m "quiero cambiar mi email a nuevo@mail.com"
  python run_query.py -m "consulta de saldo" --dry-run
        """,
    )
    parser.add_argument(
        "-m", "--mensaje",
        required=True,
        help="Mensaje del cliente en lenguaje natural.",
    )
    parser.add_argument(
        "--cuenta",
        default="CTA001",
        help="ID de la cuenta del cliente autenticado (default: CTA001).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Ejecuta sin llamar a la API de OpenAI (para pruebas locales).",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        default=True,
        help="Imprime el JSON con sangria (default: True).",
    )
    return parser.parse_args()


def main() -> None:
    args = parsear_argumentos()

    cuenta_id = args.cuenta.upper()

    # Guardrail de entrada — detecta prompts adversariales antes de gastar tokens
    auditoria_entrada = auditar_entrada(args.mensaje)
    if not auditoria_entrada.aprobado:
        print(json.dumps({
            "answer": FALLBACK_ADVERSARIAL,
            "confidence": 0.0,
            "intent": "no_reconocido",
            "actions": ["Llamar al 0800-333-2265"],
            "data": {"guardrail_entrada_motivos": auditoria_entrada.motivos}
        }, ensure_ascii=False, indent=2))
        print(f"\n[seguridad] entrada RECHAZADA: {auditoria_entrada.motivos}", file=sys.stderr)
        return

    # Pre-ejecutar herramienta antes de llamar al LLM
    intencion = detectar_intencion(args.mensaje)
    resultado_herramienta = ejecutar_herramienta(intencion, cuenta_id, args.mensaje)

    # Llamada principal
    respuesta, metricas = llamar_llm(
        cuenta_id=cuenta_id,
        mensaje=args.mensaje,
        resultados_herramientas=resultado_herramienta,
        dry_run=args.dry_run,
    )

    # Salida JSON (contrato hacia downstream)
    output = respuesta.model_dump()
    indent = 2 if args.pretty else None
    print(json.dumps(output, ensure_ascii=False, indent=indent))

    # Registrar metricas
    if not args.dry_run:
        registrar_metrica(metricas)
        print(f"\n[metricas] tokens={metricas.total_tokens}  "
              f"latencia={metricas.latency_ms:.0f}ms  "
              f"costo=${metricas.estimated_cost_usd:.6f}  "
              f"guardrail={'OK' if metricas.guardrail_aprobado else 'RECHAZADO'}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
