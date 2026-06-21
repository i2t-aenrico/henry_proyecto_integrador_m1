"""
database.py — Base de datos simulada del banco.

En un sistema real esto seria un ORM o llamadas a una API interna.
Aqui son diccionarios en memoria con datos ficticios pero coherentes.
Los IDs de cuenta se usan como clave primaria en todas las tablas.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Clientes y cuentas
# ---------------------------------------------------------------------------

CUENTAS: dict[str, dict] = {
    "CTA001": {
        "titular": "Juan Carlos Mendez",
        "numero_completo": "0720-0001-00012345-6",
        "ultimos_cuatro": "3456",
        "saldo_disponible": 158_430.75,
        "saldo_contable": 162_800.00,
        "moneda": "ARS",
        "email": "jcmendez@gmail.com",
        "telefono": "+54 9 341 512 4521",
        "direccion": "Av. Pellegrini 1245, Rosario",
    },
    "CTA002": {
        "titular": "Maria Laura Gonzalez",
        "numero_completo": "0720-0001-00023456-7",
        "ultimos_cuatro": "3567",
        "saldo_disponible": 45_210.00,
        "saldo_contable": 45_210.00,
        "moneda": "ARS",
        "email": "mlgonzalez@hotmail.com",
        "telefono": "+54 9 11 6234 8910",
        "direccion": "Calle Corrientes 890, Buenos Aires",
    },
    "CTA003": {
        "titular": "Roberto Fabian Alvarez",
        "numero_completo": "0720-0001-00034567-8",
        "ultimos_cuatro": "4678",
        "saldo_disponible": 923_100.50,
        "saldo_contable": 930_000.00,
        "moneda": "ARS",
        "email": "r.alvarez@empresa.com.ar",
        "telefono": "+54 9 351 478 1234",
        "direccion": "San Martin 340, Cordoba",
    },
    "CTA004": {
        "titular": "Sofia Beatriz Romero",
        "numero_completo": "0720-0001-00045678-9",
        "ultimos_cuatro": "5789",
        "saldo_disponible": 12_050.25,
        "saldo_contable": 12_050.25,
        "moneda": "ARS",
        "email": "sofiaromero@yahoo.com.ar",
        "telefono": "+54 9 261 390 7856",
        "direccion": "Patricias Mendocinas 123, Mendoza",
    },
    "CTA005": {
        "titular": "Diego Hernan Suarez",
        "numero_completo": "0720-0001-00056789-0",
        "ultimos_cuatro": "6890",
        "saldo_disponible": 287_640.00,
        "saldo_contable": 290_000.00,
        "moneda": "ARS",
        "email": "d.suarez@gmail.com",
        "telefono": "+54 9 379 512 0034",
        "direccion": "Av. Corrientes 2100, Posadas",
    },
}

# ---------------------------------------------------------------------------
# Movimientos por cuenta y periodo
# ---------------------------------------------------------------------------
# Estructura: (cuenta_id, periodo) -> lista de movimientos
# El periodo es una cadena normalizada, ej: "mayo 2025", "abril 2025"

MOVIMIENTOS: dict[tuple[str, str], list[dict]] = {
    ("CTA001", "mayo 2025"): [
        {"fecha": "02/05/2025", "descripcion": "Acreditacion sueldo",           "importe":  320_000.00, "saldo_posterior": 380_000.00},
        {"fecha": "03/05/2025", "descripcion": "Pago tarjeta Visa",             "importe": -125_000.00, "saldo_posterior": 255_000.00},
        {"fecha": "07/05/2025", "descripcion": "Transferencia recibida - Perez","importe":   15_000.00, "saldo_posterior": 270_000.00},
        {"fecha": "10/05/2025", "descripcion": "Debito automatico Edesur",      "importe":  -18_430.00, "saldo_posterior": 251_570.00},
        {"fecha": "15/05/2025", "descripcion": "Extraccion cajero 7234",        "importe":  -20_000.00, "saldo_posterior": 231_570.00},
        {"fecha": "20/05/2025", "descripcion": "Compra POS - Supermercado Dia", "importe":  -12_500.00, "saldo_posterior": 219_070.00},
        {"fecha": "22/05/2025", "descripcion": "Transferencia enviada - Lopez", "importe":  -30_000.00, "saldo_posterior": 189_070.00},
        {"fecha": "28/05/2025", "descripcion": "Debito automatico OSDE",        "importe":  -26_640.00, "saldo_posterior": 162_430.00},
        {"fecha": "30/05/2025", "descripcion": "Interes acreditado",            "importe":      370.75, "saldo_posterior": 162_800.75},
    ],
    ("CTA001", "abril 2025"): [
        {"fecha": "01/04/2025", "descripcion": "Acreditacion sueldo",           "importe":  310_000.00, "saldo_posterior": 355_000.00},
        {"fecha": "05/04/2025", "descripcion": "Pago tarjeta Visa",             "importe":  -98_000.00, "saldo_posterior": 257_000.00},
        {"fecha": "12/04/2025", "descripcion": "Debito automatico Edesur",      "importe":  -17_200.00, "saldo_posterior": 239_800.00},
        {"fecha": "18/04/2025", "descripcion": "Extraccion cajero 7234",        "importe":  -30_000.00, "saldo_posterior": 209_800.00},
        {"fecha": "25/04/2025", "descripcion": "Compra POS - Farmacia",         "importe":   -4_100.00, "saldo_posterior": 205_700.00},
        {"fecha": "30/04/2025", "descripcion": "Interes acreditado",            "importe":      310.00, "saldo_posterior": 206_010.00},
    ],
    ("CTA002", "mayo 2025"): [
        {"fecha": "05/05/2025", "descripcion": "Deposito en efectivo",          "importe":   50_000.00, "saldo_posterior":  75_210.00},
        {"fecha": "10/05/2025", "descripcion": "Pago servicio Metrogas",        "importe":   -8_500.00, "saldo_posterior":  66_710.00},
        {"fecha": "15/05/2025", "descripcion": "Transferencia enviada",         "importe":  -21_500.00, "saldo_posterior":  45_210.00},
    ],
    ("CTA003", "mayo 2025"): [
        {"fecha": "02/05/2025", "descripcion": "Acreditacion honorarios",       "importe":  950_000.00, "saldo_posterior": 980_000.00},
        {"fecha": "08/05/2025", "descripcion": "Transferencia enviada - Ramirez","importe": -50_000.00, "saldo_posterior": 930_000.00},
    ],
}

# ---------------------------------------------------------------------------
# Campos permitidos para actualizar en datos personales
# ---------------------------------------------------------------------------

CAMPOS_ACTUALIZABLES: dict[str, str] = {
    "email":     "Correo electronico",
    "telefono":  "Numero de telefono",
    "direccion": "Domicilio",
}
