"""
Generador de datos sintéticos para el demo de Senties Chauvet.

Produce datos realistas del sector fianzas mexicano:
  - ~500 fianzas activas
  - ~200 propuestas en distintos estatus
  - 40 fiados realistas (mezcla de sectores)
  - 15 beneficiarios reales del sector público federal
  - 10 ejecutivos con carteras asignadas

Uso:
    python scripts/generate_synthetic_data.py

Output: data/senties_demo.db (SQLite)
"""

from __future__ import annotations

import os
import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

random.seed(42)  # reproducibilidad

# ============================================================
# CATÁLOGOS REALISTAS
# ============================================================

# Beneficiarios reales del sector fianzas mexicano (los que vimos en la data real de Chubb)
BENEFICIARIOS = [
    ("729736", "A FAVOR DE PETRÓLEOS MEXICANOS"),
    ("42259", "PETRÓLEOS MEXICANOS"),
    ("880627", "PEMEX TRANSFORMACIÓN INDUSTRIAL"),
    ("844067", "PEMEX EXPLORACIÓN Y PRODUCCIÓN"),
    ("210318", "TESORERÍA DE LA FEDERACIÓN"),
    ("284210", "INSTITUTO NACIONAL DE CANCEROLOGÍA"),
    ("352080", "INSTITUTO MEXICANO DEL SEGURO SOCIAL"),
    ("938309", "SERVICIOS DE SALUD DEL INSTITUTO NACIONAL DE PERINATOLOGÍA"),
    ("694047", "SECRETARÍA DE SALUD FEDERAL"),
    ("231132", "COMISIÓN FEDERAL DE ELECTRICIDAD"),
    ("1010742", "CEMENTOS CRUZ AZUL CAMPECHE, S.A. DE C.V."),
    ("627762", "PEMEX LOGÍSTICA"),
    ("202768", "INSTITUTO DE SEGURIDAD Y SERVICIOS SOCIALES DE LOS TRABAJADORES DEL ESTADO"),
    ("594607", "ADMINISTRACIÓN PORTUARIA INTEGRAL DE VERACRUZ"),
    ("668314", "SECRETARÍA DE INFRAESTRUCTURA Y OBRAS PÚBLICAS"),
]

# Fiados sintéticos (empresas mexicanas típicas del sector)
FIADOS = [
    ("657687", "MOTORES E INGENIERÍA MEXMOT, S.A. DE C.V.", "MEM980101ABC"),
    ("1034868", "BEIGENE MÉXICO, S. DE R.L. DE C.V.", "BEM150523XYZ"),
    ("123418", "MITSUBISHI ELECTRIC DE MEXICO, S.A. DE C.V.", "MEM760401DJ7"),
    ("845921", "GRUPO CONSTRUCTOR VALDÉS Y ASOCIADOS", "GCV020508A11"),
    ("512367", "INDUSTRIAS TERMOELÉCTRICAS DEL BAJÍO", "ITB980612PQ2"),
    ("734589", "SUMINISTROS MÉDICOS ESPECIALIZADOS DE MÉXICO", "SME120315BQ8"),
    ("623471", "TRANSPORTES ESPECIALIZADOS DEL NORTE", "TEN050723C48"),
    ("891234", "CONSTRUCCIONES Y OBRAS CIVILES ROMERO", "COC100418ZK5"),
    ("456789", "SERVICIOS INDUSTRIALES MENDOZA HERMANOS", "SIM950608MB3"),
    ("312945", "TECNOLOGÍA APLICADA MEXICANA, S.A. DE C.V.", "TAM110902TR6"),
    ("789012", "GRUPO EMPRESARIAL FARMACÉUTICO ANDINO", "GEF080115PL9"),
    ("567890", "INSTALACIONES ELÉCTRICAS MONTERREY", "IEM071122KJ4"),
    ("234567", "SUMINISTRO DE EQUIPO MÉDICO GARCÍA", "SEM020603FN7"),
    ("678901", "CORPORATIVO INDUSTRIAL DEL SURESTE", "CIS130409UV2"),
    ("345678", "MAQUINARIA Y REFACCIONES DEL PACÍFICO", "MRP991216HS8"),
    ("901234", "PROVEEDORA HOSPITALARIA INTEGRAL", "PHI040820BM1"),
    ("890123", "GRUPO CONSTRUCTOR PENINSULAR, S.A.", "GCP060517QW3"),
    ("456123", "SOLUCIONES TÉCNICAS DEL NORESTE", "STN081205YZ6"),
    ("789456", "MANTENIMIENTO INDUSTRIAL PROFESIONAL", "MIP030129CP4"),
    ("123789", "COMERCIALIZADORA DE PRODUCTOS FARMACÉUTICOS", "CPF160702LK5"),
    ("456321", "AUTOMATIZACIÓN Y CONTROL INDUSTRIAL", "ACI111014XN8"),
    ("789654", "INGENIERÍA CIVIL Y ELECTROMECÁNICA", "ICE070826BD2"),
    ("321654", "REDES Y SISTEMAS DE TELECOMUNICACIONES", "RST100307VG9"),
    ("654987", "PROVEEDORES DEL SECTOR ENERGÉTICO", "PSE050914RM3"),
    ("987321", "MATERIALES PARA CONSTRUCCIÓN DEL NORTE", "MCN020225TP7"),
    ("147258", "PRODUCTOS METÁLICOS Y ACEROS ESPECIALES", "PMA130418HW4"),
    ("258147", "SERVICIOS AMBIENTALES DEL GOLFO", "SAG090630DE1"),
    ("369852", "INGENIERÍA HIDRÁULICA APLICADA", "IHA110905BJ6"),
    ("852369", "TRANSPORTES REFRIGERADOS DEL BAJÍO", "TRB060118NC8"),
    ("741963", "EQUIPOS DE LABORATORIO ESPECIALIZADO", "ELE081210SR2"),
    ("963741", "SISTEMAS DE SEGURIDAD INDUSTRIAL", "SSI040527QP5"),
    ("159357", "SOLDADURA Y ESTRUCTURAS METÁLICAS", "SEM120820MH7"),
    ("357159", "GRUPO CORPORATIVO INDUSTRIAL AZTECA", "GCI070315BF3"),
    ("753951", "PROVEEDOR INTEGRAL DE EQUIPO MÉDICO", "PIE100628KV9"),
    ("951753", "DESARROLLO DE INFRAESTRUCTURA URBANA", "DIU051010LT4"),
    ("264813", "OPERADORA DE SERVICIOS DE MANTENIMIENTO", "OSM090722XB6"),
    ("813264", "DISTRIBUIDORA MEXICANA DE MEDICAMENTOS", "DMM020424QR1"),
    ("482613", "CONSULTORÍA EN INGENIERÍA CIVIL Y AMBIENTAL", "CIC110907JD8"),
    ("613482", "SERVICIOS TÉCNICOS ESPECIALIZADOS DEL VALLE", "STE060213PW2"),
    ("735916", "INSUMOS INDUSTRIALES DEL PACÍFICO NORTE", "IIP131118NR5"),
]

# Productos de fianza (tipos reales)
PRODUCTOS = [
    "PROVEEDURÍA - CUMPLIMIENTO DE CONTRATO",
    "PROVEEDURÍA - BUENA CALIDAD",
    "PROVEEDURÍA - ANTICIPO DE PEDIDO",
    "OBRA - CUMPLIMIENTO",
    "OBRA - ANTICIPO",
    "OBRA - VICIOS OCULTOS",
    "JUDICIAL - APELACIÓN",
    "JUDICIAL - AMPARO",
    "ADMINISTRATIVA - AUTORIZACIÓN",
    "ADMINISTRATIVA - CONCESIÓN",
    "FIDELIDAD - EMPLEADOS",
    "CRÉDITO - GARANTÍA DE PAGO",
]

# Afianzadoras
AFIANZADORAS = ["CHUBB", "ACERTA", "TOKIO MARINE", "BERKELEY", "SOFIMEX", "MAPFRE"]

# Ejecutivos (10 de cuenta)
EJECUTIVOS = [
    ("MBARRERA5274", "Marlene Barrera"),
    ("AVAZQUEZ5274", "Alfonso Vázquez"),
    ("VCACH5274", "Verónica Cachutt"),
    ("MOSORIO5274", "María Osorio"),
    ("JGARCIA5274", "Javier García"),
    ("PLOPEZ5274", "Patricia López"),
    ("RMTZ5274", "Ricardo Martínez"),
    ("LSANCHEZ5274", "Lourdes Sánchez"),
    ("FTORRES5274", "Fernando Torres"),
    ("CRUIZ5274", "Claudia Ruiz"),
]

# Ramos
RAMOS = ["Proveeduría", "Obra", "Judicial", "Administrativa", "Fidelidad", "Crédito"]

# Estatus de fianza
ESTATUS_FIANZA = [
    ("T", "En Trámite"),
    ("M", "Por Autorizar"),
    ("N", "Autorizada"),
    ("P", "Producción"),
    ("C", "Cancelada"),
    ("O", "Cancelada en Oficina"),
    ("L", "En Lote"),
    ("X", "En Lote Expedida"),
]

# Estatus de propuesta
ESTATUS_PROPUESTA = [
    ("T", "Trámite"),
    ("A", "Autorizada"),
    ("R", "Rechazada"),
]

# Movimientos
MOVIMIENTOS = ["EN PROCESO", "RENOVACIÓN", "EXPEDICIÓN", "CANCELACIÓN", "REPOSICIÓN DE TEXTO", "MODIFICACIÓN"]

# Estados (campo derivado del API)
ESTADOS = ["CANCELAR", "RENOVAR", None, None, None]  # None con más peso (mayoría sin acción pendiente)


# ============================================================
# GENERACIÓN
# ============================================================

def random_date(start: date, end: date) -> date:
    """Fecha aleatoria entre start y end."""
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def money(min_val: int, max_val: int) -> float:
    """Cantidad monetaria realista."""
    # Distribución sesgada hacia montos menores pero con outliers grandes
    r = random.random()
    if r < 0.6:
        return round(random.uniform(min_val, min_val * 10), 2)
    elif r < 0.9:
        return round(random.uniform(min_val * 10, min_val * 100), 2)
    else:
        return round(random.uniform(min_val * 100, max_val), 2)


def build_database(db_path: Path):
    """Construye la DB SQLite con todos los datos sintéticos."""
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # === Schema ===
    cur.executescript("""
        CREATE TABLE afianzadoras (
            id TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            tipo_integracion TEXT NOT NULL  -- 'API' o 'CORREO'
        );

        CREATE TABLE ejecutivos (
            id TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            fecha_alta DATE NOT NULL
        );

        CREATE TABLE fiados (
            id TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            rfc TEXT NOT NULL,
            ejecutivo_id TEXT NOT NULL,
            linea_afianzamiento REAL NOT NULL,
            linea_disponible REAL NOT NULL,
            expediente_vigente_hasta DATE NOT NULL,
            buro_vigente_hasta DATE NOT NULL,
            dictamen_vigente_hasta DATE NOT NULL,
            fecha_alta DATE NOT NULL,
            categoria_buro TEXT NOT NULL,  -- A, B, C, D
            FOREIGN KEY (ejecutivo_id) REFERENCES ejecutivos(id)
        );

        CREATE TABLE beneficiarios (
            id TEXT PRIMARY KEY,
            nombre TEXT NOT NULL
        );

        CREATE TABLE fianzas_vigor (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fianza_real TEXT NOT NULL,
            inclusion INTEGER DEFAULT 0,
            fiado_id TEXT NOT NULL,
            beneficiario_id TEXT NOT NULL,
            afianzadora_id TEXT NOT NULL,
            monto REAL NOT NULL,
            prima_anual REAL NOT NULL,
            vigencia_del DATE NOT NULL,
            vigencia_al DATE NOT NULL,
            fecha_cumplimiento DATE NOT NULL,
            fecha_expedicion DATE NOT NULL,
            documento_fuente TEXT,
            relativo TEXT,
            producto TEXT NOT NULL,
            ramo TEXT NOT NULL,
            estatus_fianza TEXT NOT NULL,
            estatus_fianza_desc TEXT NOT NULL,
            estado TEXT,  -- CANCELAR / RENOVAR / NULL
            ultimo_movimiento TEXT NOT NULL,
            FOREIGN KEY (fiado_id) REFERENCES fiados(id),
            FOREIGN KEY (beneficiario_id) REFERENCES beneficiarios(id),
            FOREIGN KEY (afianzadora_id) REFERENCES afianzadoras(id)
        );

        CREATE TABLE propuestas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            propuesta INTEGER NOT NULL,
            fecha_inserto TIMESTAMP NOT NULL,
            fiado_id TEXT NOT NULL,
            beneficiario_id TEXT NOT NULL,
            afianzadora_id TEXT NOT NULL,
            monto_afianzado REAL NOT NULL,
            vigencia_del DATE NOT NULL,
            vigencia_al DATE NOT NULL,
            cve_estatus_propuesta TEXT NOT NULL,
            desc_estatus_propuesta TEXT NOT NULL,
            cve_estatus_fianza TEXT NOT NULL,
            desc_estatus_fianza TEXT NOT NULL,
            desc_movto_fianza TEXT NOT NULL,
            producto TEXT NOT NULL,
            estructura TEXT DEFAULT 'CIUDAD DE MEXICO',
            dias_en_estatus INTEGER NOT NULL,  -- para detectar atoradas
            FOREIGN KEY (fiado_id) REFERENCES fiados(id),
            FOREIGN KEY (beneficiario_id) REFERENCES beneficiarios(id),
            FOREIGN KEY (afianzadora_id) REFERENCES afianzadoras(id)
        );

        CREATE TABLE cobranza (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fianza_id INTEGER NOT NULL,
            fecha_vencimiento DATE NOT NULL,
            monto_prima REAL NOT NULL,
            monto_pagado REAL DEFAULT 0,
            estatus TEXT NOT NULL,  -- PENDIENTE, PAGADO, VENCIDO
            dias_vencido INTEGER DEFAULT 0,
            FOREIGN KEY (fianza_id) REFERENCES fianzas_vigor(id)
        );

        CREATE INDEX idx_fianzas_fiado ON fianzas_vigor(fiado_id);
        CREATE INDEX idx_fianzas_beneficiario ON fianzas_vigor(beneficiario_id);
        CREATE INDEX idx_fianzas_afianzadora ON fianzas_vigor(afianzadora_id);
        CREATE INDEX idx_fianzas_cumplimiento ON fianzas_vigor(fecha_cumplimiento);
        CREATE INDEX idx_fianzas_estado ON fianzas_vigor(estado);
        CREATE INDEX idx_propuestas_estatus ON propuestas(cve_estatus_propuesta, cve_estatus_fianza);
        CREATE INDEX idx_fiados_ejecutivo ON fiados(ejecutivo_id);
    """)

    # === Afianzadoras ===
    afianzadoras_data = [
        ("CHUBB", "Chubb Fianzas Monterrey", "API"),
        ("ACERTA", "Aserta Fianzas", "API"),
        ("TOKIO", "Tokio Marine México", "API"),
        ("BERKELEY", "Berkeley Fianzas", "CORREO"),
        ("SOFIMEX", "Sofimex Fianzas", "CORREO"),
        ("MAPFRE", "Mapfre Fianzas", "CORREO"),
    ]
    cur.executemany("INSERT INTO afianzadoras VALUES (?, ?, ?)", afianzadoras_data)

    # === Ejecutivos ===
    for eid, nombre in EJECUTIVOS:
        fecha_alta = random_date(date(2018, 1, 1), date(2023, 12, 31))
        cur.execute("INSERT INTO ejecutivos VALUES (?, ?, ?)", (eid, nombre, fecha_alta))

    # === Fiados con carteras asignadas ===
    hoy = date.today()
    fiados_list = []

    # FIX #3: Distribución no uniforme de fiados por ejecutivo (suma = 40, len(FIADOS))
    # Sustituye el round-robin exacto que daba "4 fiados por ejecutivo" para todos.
    # Orden EJECUTIVOS: Marlene, Alfonso, Verónica, María, Javier, Patricia, Ricardo, Lourdes, Fernando, Claudia
    n_fiados_target = [6, 5, 5, 4, 4, 4, 4, 3, 3, 2]  # suma = 40
    asignaciones_ejecutivo = []
    for exec_idx, n in enumerate(n_fiados_target):
        asignaciones_ejecutivo.extend([EJECUTIVOS[exec_idx][0]] * n)
    # asignaciones_ejecutivo tiene 40 entries; el i-ésimo fiado toma asignaciones_ejecutivo[i]

    for i, (fid, nombre, rfc) in enumerate(FIADOS):
        ejecutivo = asignaciones_ejecutivo[i]
        linea = round(random.choice([5_000_000, 10_000_000, 25_000_000, 50_000_000, 100_000_000, 250_000_000, 500_000_000]) * random.uniform(0.5, 1.5), 0)
        disponible_pct = random.uniform(0.15, 0.95)
        disponible = round(linea * disponible_pct, 0)
        expediente = hoy + timedelta(days=random.randint(-90, 365))
        buro = hoy + timedelta(days=random.randint(-30, 300))
        dictamen = hoy + timedelta(days=random.randint(-60, 400))
        fecha_alta = random_date(date(2015, 1, 1), date(2024, 6, 30))
        categoria = random.choices(["A", "B", "C", "D"], weights=[45, 35, 15, 5])[0]

        fiados_list.append((fid, nombre, rfc, ejecutivo, linea, disponible, expediente, buro, dictamen, fecha_alta, categoria))
        cur.execute("INSERT INTO fiados VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (fid, nombre, rfc, ejecutivo, linea, disponible, expediente, buro, dictamen, fecha_alta, categoria))

    # === Beneficiarios ===
    for bid, nombre in BENEFICIARIOS:
        cur.execute("INSERT INTO beneficiarios VALUES (?, ?)", (bid, nombre))

    # === Fianzas en vigor (500 registros) ===
    # Distribución por afianzadora: Chubb tiene la mayoría (broker real)
    afianzadora_weights = {"CHUBB": 60, "ACERTA": 20, "TOKIO": 10, "BERKELEY": 4, "SOFIMEX": 4, "MAPFRE": 2}
    afianzadora_ids = list(afianzadora_weights.keys())
    afianzadora_w = list(afianzadora_weights.values())

    fianzas_count = 500
    fianzas_records = []
    for i in range(fianzas_count):
        fiado_id = random.choice([f[0] for f in FIADOS])
        beneficiario_id = random.choice([b[0] for b in BENEFICIARIOS])
        afianzadora_id = random.choices(afianzadora_ids, weights=afianzadora_w)[0]

        fianza_real = str(2100000 + i * random.randint(1, 3))
        monto = money(50_000, 100_000_000)
        prima_anual = round(monto * random.uniform(0.005, 0.02), 2)

        vigencia_del = random_date(date(2023, 1, 1), date(2026, 6, 30))
        vigencia_al = vigencia_del + timedelta(days=random.choice([365, 365, 365, 730]))
        fecha_cumplimiento = vigencia_del + timedelta(days=random.randint(30, (vigencia_al - vigencia_del).days))
        fecha_expedicion = vigencia_del - timedelta(days=random.randint(1, 15))

        # Estatus con distribución realista
        estatus_key, estatus_desc = random.choices(
            ESTATUS_FIANZA,
            weights=[5, 8, 12, 55, 10, 3, 4, 3]  # mayoría en Producción
        )[0]

        # Estado: derivado de fecha_cumplimiento
        if fecha_cumplimiento < hoy:
            estado = "CANCELAR"
        elif fecha_cumplimiento < hoy + timedelta(days=60):
            estado = "RENOVAR"
        else:
            estado = None

        producto = random.choice(PRODUCTOS)
        ramo = random.choice(RAMOS)
        ultimo_movimiento = random.choice(MOVIMIENTOS)
        documento_fuente = f"{random.randint(5100000000, 5400999999)}"
        relativo = ""  # placeholder

        cur.execute("""
            INSERT INTO fianzas_vigor
            (fianza_real, inclusion, fiado_id, beneficiario_id, afianzadora_id, monto, prima_anual,
             vigencia_del, vigencia_al, fecha_cumplimiento, fecha_expedicion, documento_fuente,
             relativo, producto, ramo, estatus_fianza, estatus_fianza_desc, estado, ultimo_movimiento)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (fianza_real, 0, fiado_id, beneficiario_id, afianzadora_id, monto, prima_anual,
              vigencia_del, vigencia_al, fecha_cumplimiento, fecha_expedicion, documento_fuente,
              relativo, producto, ramo, estatus_key, estatus_desc, estado, ultimo_movimiento))

    # === Propuestas (200 registros, últimos 90 días) ===
    for i in range(200):
        fiado_id = random.choice([f[0] for f in FIADOS])
        beneficiario_id = random.choice([b[0] for b in BENEFICIARIOS])
        afianzadora_id = random.choices(afianzadora_ids, weights=afianzadora_w)[0]

        fecha_inserto = datetime.combine(
            random_date(hoy - timedelta(days=90), hoy),
            datetime.min.time().replace(hour=random.randint(7, 18), minute=random.randint(0, 59))
        )

        monto = money(50_000, 50_000_000)
        vigencia_del = fecha_inserto.date() + timedelta(days=random.randint(1, 30))
        vigencia_al = vigencia_del + timedelta(days=365)

        # Estatus propuesta con distribución realista
        estatus_p_key, estatus_p_desc = random.choices(
            ESTATUS_PROPUESTA,
            weights=[50, 40, 10]
        )[0]

        # Estatus fianza dependiente
        if estatus_p_key == "A":
            estatus_f_key, estatus_f_desc = random.choice([("N", "Autorizada"), ("P", "Producción")])
        elif estatus_p_key == "R":
            estatus_f_key, estatus_f_desc = ("C", "Cancelada")
        else:
            estatus_f_key, estatus_f_desc = random.choice([("T", "Trámite"), ("M", "Por Autorizar")])

        movto = random.choice(MOVIMIENTOS)
        producto = random.choice(PRODUCTOS)
        propuesta_num = 8500000 + i * random.randint(1, 3)
        dias_en_estatus = (hoy - fecha_inserto.date()).days

        cur.execute("""
            INSERT INTO propuestas
            (propuesta, fecha_inserto, fiado_id, beneficiario_id, afianzadora_id, monto_afianzado,
             vigencia_del, vigencia_al, cve_estatus_propuesta, desc_estatus_propuesta,
             cve_estatus_fianza, desc_estatus_fianza, desc_movto_fianza, producto, dias_en_estatus)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (propuesta_num, fecha_inserto, fiado_id, beneficiario_id, afianzadora_id, monto,
              vigencia_del, vigencia_al, estatus_p_key, estatus_p_desc,
              estatus_f_key, estatus_f_desc, movto, producto, dias_en_estatus))

    # === Cobranza (generar registros para fianzas en Producción) ===
    # FIX #1: Distribución realista de saldos vencidos en 4 buckets.
    # Antes: dias_vencido = (hoy - fecha_venc) donde fecha_venc era antigua → casi todo caía en 90+.
    # Ahora: forzamos que los VENCIDOs se distribuyan en 1-30 / 31-60 / 61-90 / 90+ con curva realista.
    BUCKET_ANTIGUEDAD = [
        (1, 30, 15),      # 15% en 1-30 días (deuda reciente)
        (31, 60, 20),     # 20% en 31-60 días
        (61, 90, 25),     # 25% en 61-90 días
        (91, 250, 40),    # 40% en 90+ días (deuda persistente)
    ]
    bucket_ranges = [(b[0], b[1]) for b in BUCKET_ANTIGUEDAD]
    bucket_weights = [b[2] for b in BUCKET_ANTIGUEDAD]

    cur.execute("SELECT id, prima_anual, vigencia_del FROM fianzas_vigor WHERE estatus_fianza = 'P' LIMIT 200")
    fianzas_prod = cur.fetchall()
    for fianza_id, prima_anual, vig_del in fianzas_prod:
        vig_del_date = datetime.strptime(vig_del, "%Y-%m-%d").date() if isinstance(vig_del, str) else vig_del
        for mes in range(random.randint(3, 12)):
            fecha_venc_natural = vig_del_date + timedelta(days=mes * 30)
            monto_prima = round(prima_anual / 12, 2)

            if fecha_venc_natural > hoy:
                # Recibo futuro: PENDIENTE (mantiene fecha natural)
                estatus = "PENDIENTE"
                pagado = 0
                dias_venc = 0
                fecha_venc_final = fecha_venc_natural
            else:
                # Recibo pasado: 70% PAGADO, 30% VENCIDO
                r = random.random()
                if r < 0.70:
                    estatus = "PAGADO"
                    pagado = monto_prima
                    dias_venc = 0
                    fecha_venc_final = fecha_venc_natural
                else:
                    # VENCIDO: sortea bucket de antigüedad realista
                    estatus = "VENCIDO"
                    pagado = 0
                    lo, hi = random.choices(bucket_ranges, weights=bucket_weights)[0]
                    dias_venc = random.randint(lo, hi)
                    # fecha_vencimiento = hoy - dias_vencido (consistente con el bucket)
                    fecha_venc_final = hoy - timedelta(days=dias_venc)

            cur.execute("""
                INSERT INTO cobranza (fianza_id, fecha_vencimiento, monto_prima, monto_pagado, estatus, dias_vencido)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (fianza_id, fecha_venc_final, monto_prima, pagado, estatus, dias_venc))

    conn.commit()

    # === Resumen ===
    print("=" * 60)
    print("BASE DE DATOS SINTÉTICA GENERADA")
    print("=" * 60)
    for tabla in ["afianzadoras", "ejecutivos", "fiados", "beneficiarios", "fianzas_vigor", "propuestas", "cobranza"]:
        cur.execute(f"SELECT COUNT(*) FROM {tabla}")
        count = cur.fetchone()[0]
        print(f"  {tabla:20s}: {count:>6,} registros")

    # KPIs para dar confianza que los datos son realistas
    print()
    print("KPIs verificables:")
    cur.execute("SELECT SUM(monto) FROM fianzas_vigor WHERE estatus_fianza = 'P'")
    print(f"  Monto total en Producción: ${cur.fetchone()[0]:>18,.2f} MXN")

    cur.execute("SELECT COUNT(*) FROM fianzas_vigor WHERE estado = 'CANCELAR'")
    print(f"  Fianzas a cancelar:        {cur.fetchone()[0]:>18,}")

    cur.execute("SELECT COUNT(*) FROM fianzas_vigor WHERE estado = 'RENOVAR'")
    print(f"  Fianzas a renovar:         {cur.fetchone()[0]:>18,}")

    cur.execute("""
        SELECT b.nombre, COUNT(*), SUM(f.monto)
        FROM fianzas_vigor f JOIN beneficiarios b ON f.beneficiario_id = b.id
        GROUP BY b.id ORDER BY SUM(f.monto) DESC LIMIT 3
    """)
    print("\n  Top 3 beneficiarios por monto:")
    for nombre, count, total in cur.fetchall():
        print(f"    {nombre[:45]:45s}: {count:>3} fianzas, ${total:>15,.2f}")

    # Verificación FIX #1: distribución de buckets de antigüedad
    cur.execute("""
        SELECT
            CASE
                WHEN dias_vencido <= 30 THEN '1-30 días'
                WHEN dias_vencido <= 60 THEN '31-60 días'
                WHEN dias_vencido <= 90 THEN '61-90 días'
                ELSE '90+ días'
            END as bucket,
            COUNT(*) as recibos,
            SUM(monto_prima) as monto
        FROM cobranza WHERE estatus = 'VENCIDO'
        GROUP BY bucket ORDER BY MIN(dias_vencido)
    """)
    print("\n  Distribución de vencidos por antigüedad (FIX #1):")
    for bucket, recibos, monto in cur.fetchall():
        print(f"    {bucket:12s}: {recibos:>4} recibos, ${monto:>15,.2f}")

    # Verificación FIX #3: distribución de fiados por ejecutivo
    cur.execute("""
        SELECT e.nombre, COUNT(fi.id) as n_fiados
        FROM ejecutivos e LEFT JOIN fiados fi ON fi.ejecutivo_id = e.id
        GROUP BY e.id ORDER BY n_fiados DESC
    """)
    print("\n  Distribución de fiados por ejecutivo (FIX #3):")
    for nombre, n in cur.fetchall():
        print(f"    {nombre:22s}: {n} fiados")

    conn.close()
    print("\n✓ Base guardada en:", db_path)


if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    db_path = project_root / "data" / "senties_demo.db"
    db_path.parent.mkdir(exist_ok=True)
    build_database(db_path)
