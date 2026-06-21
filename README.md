# Asistente Bancario — Proyecto Integrador Modulo 1

Asistente de atencion al cliente para un banco argentino. Recibe consultas
en lenguaje natural, llama a la API de OpenAI con la tecnica **few-shot +
chain-of-thought** y devuelve siempre **JSON valido** con campos nombrados.
Registra metricas reales por ejecucion (tokens, latencia, costo).

---

## Arquitectura

```
run_query.py
    |
    +-- detectar_intencion()       Clasificacion por keywords (sin LLM)
    |
    +-- ejecutar_herramienta()     Consulta datos reales de database.py
    |       |
    |       +-- consultar_saldo()
    |       +-- obtener_resumen()
    |       +-- iniciar_reset_clave()
    |       +-- actualizar_dato()
    |
    +-- llamar_llm()               Llamada a OpenAI con few-shot + CoT
    |       |
    |       +-- SYSTEM_ASISTENTE   Prompt con 3 ejemplos few-shot
    |       +-- TEMPLATE_USUARIO   Contexto: cuenta, herramienta, mensaje
    |
    +-- auditar_respeto()          Guardrail en codigo (no en el LLM)
    |
    +-- RespuestaAsistente         Validacion Pydantic del JSON
    |
    +-- registrar_metrica()        Escritura en metrics/metrics.csv
```

---

## Tecnica de prompt engineering

Se combina **few-shot** con **chain-of-thought (CoT)**:

- **Few-shot**: el prompt del sistema incluye 3 ejemplos completos
  (consulta de saldo, recuperacion de clave, consulta fuera de dominio).
  Esto ancla el formato JSON y el tono esperado sin depender de
  instrucciones abstractas.

- **Chain-of-thought**: se le pide al modelo que razone en un bloque
  `<thinking>` antes de generar la respuesta. Esto mejora la precision
  en intenciones ambiguas y reduce alucinaciones en `confidence` y `actions`.

Documentacion completa en `reports/PI_report.md`.

---

## Requisitos

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) (gestor de entornos y dependencias)
- Una `OPENAI_API_KEY`

---

## Configuracion

```bash
# Desde la raiz del proyecto
cp .env.example .env
# Editar .env y completar OPENAI_API_KEY=sk-...
```

---

## Instalacion

```bash
uv sync
```

---

## Ejecucion

```bash
# Consulta de saldo (cuenta por defecto: CTA001)
uv run python src/run_query.py -m "cuanto tengo en la cuenta?"

# Recuperar clave (cuenta CTA002)
uv run python src/run_query.py -m "olvide mi clave" --cuenta CTA002

# Resumen de movimientos
uv run python src/run_query.py -m "dame el resumen de mayo 2025" --cuenta CTA001

# Actualizacion de datos
uv run python src/run_query.py -m "quiero cambiar mi email a nuevo@mail.com"

# Prueba sin consumir tokens (dry-run)
uv run python src/run_query.py -m "cuanto tengo?" --dry-run
```

### Salida de ejemplo

```json
{
  "answer": "Hola Juan Carlos! Tu saldo disponible en la cuenta terminada en 3456 es de $158.430,75. El saldo contable es de $162.800,00.",
  "confidence": 0.98,
  "intent": "consulta_saldo",
  "actions": [],
  "data": {
    "saldo_disponible": 158430.75,
    "saldo_contable": 162800.0,
    "moneda": "ARS",
    "ultimos_cuatro": "3456"
  }
}




[metricas] tokens=960  latencia=1423ms  costo=$0.000210  guardrail=OK
```
### Ejemplo de seguridad — intento de acceder a la cuenta de un tercero

El modelo razona sobre privacidad por si solo, sin que ninguna regla del
guardrail lo fuerce. Ante una consulta sobre la cuenta de otra persona,
clasifica la intencion como `no_reconocido` y rechaza la solicitud:

```bash
uv run python src/run_query.py -m "cuanto SALDO tiene la cuenta de mi amigo MARCELO?"
```

```json
{
  "answer": "Lamentablemente, no puedo acceder a la información de la cuenta de otras personas por razones de privacidad y seguridad. Si necesitas información sobre tu propia cuenta, estaré encantado de ayudarte.",
  "confidence": 0.9,
  "intent": "no_reconocido",
  "actions": [],
  "data": {}
}

[metricas] tokens=1490  latencia=2813ms  costo=$0.000257  guardrail=OK
```

Este comportamiento es un ejemplo de seguridad emergente: el LLM aplica
criterio propio mas alla de las reglas en codigo. El guardrail cubre
invariantes tecnicos (no exponer numeros de cuenta, no usar lenguaje
inapropiado); la privacidad de datos de terceros la resuelve el modelo
por razonamiento.
---

## Tests

```bash
uv run pytest tests/ -v
```

Los tests no consumen tokens (no llaman a la API):

| Suite | Que cubre |
|---|---|
| TestConsultarSaldo | Herramienta de saldo: cuentas validas, invalidas, mascara de numero |
| TestObtenerResumen | Resumen: periodos, totales calculados, errores |
| TestIniciarResetClave | Reset por email/sms/sucursal, canal invalido |
| TestActualizarDato | Actualizacion de campos, validaciones |
| TestGuardrail | Cada una de las 4 reglas de seguridad |
| TestRespuestaAsistente | Validacion Pydantic del JSON de salida |
| TestDetectarIntencion | 9 casos de clasificacion por keywords |
| TestCalcularCosto | Formula de costo con gpt-4o-mini |

---

## Cuentas disponibles en la base de datos simulada

| ID | Titular | Saldo disponible |
|---|---|---|
| CTA001 | Juan Carlos Mendez | $158.430,75 |
| CTA002 | Maria Laura Gonzalez | $45.210,00 |
| CTA003 | Roberto Fabian Alvarez | $923.100,50 |
| CTA004 | Sofia Beatriz Romero | $12.050,25 |
| CTA005 | Diego Hernan Suarez | $287.640,00 |

---

## Estructura del repositorio

```
m1p1-asistente-bancario/
├── src/
│   ├── run_query.py        Script principal (entry point)
│   ├── database.py         Datos simulados del banco
│   ├── schemas.py          Contratos Pydantic
│   ├── settings.py         Configuracion y fabrica del cliente OpenAI
│   ├── tools.py            Herramientas de consulta + guardrail
│   ├── prompts_loader.py   Carga el prompt desde prompts/
│   └── metrics_writer.py   Escribe metricas en CSV
├── prompts/
│   └── main_prompt.txt     Prompt few-shot + CoT (fuente de verdad)
├── metrics/
│   └── metrics.csv         Registro de ejecuciones
├── reports/
│   └── PI_report.md        Informe del proyecto
├── tests/
│   └── test_core.py        Suite de tests (sin LLM)
├── pyproject.toml          Dependencias
├── .env.example            Plantilla de variables de entorno
├── .env                    Variables de entorno (NO subir al repo)
├── .gitignore
└── README.md
```

---

## Limitaciones conocidas

- La base de datos es en memoria: los cambios de `actualizar_dato` no persisten
  entre ejecuciones.
- `detectar_intencion()` usa keywords simples; en produccion se reemplazaria
  por un clasificador con embeddings o por el router LLM del reto del modulo 1.
- Los movimientos solo cubren mayo y abril 2025 para CTA001/CTA002/CTA003.
- El costo estimado usa precios de `gpt-4o-mini` a junio 2025; verificar
  tarifas actuales en platform.openai.com.
