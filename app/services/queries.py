"""Queries para los 4 dashboards."""

from datetime import date


def dashboard_salud(db):
    """Dashboard 1: Salud del agente."""
    cur = db.cursor()

    # KPIs globales
    cur.execute("SELECT COUNT(*), COALESCE(SUM(monto), 0) FROM fianzas_vigor WHERE estatus_fianza IN ('P', 'N', 'X')")
    row = cur.fetchone()
    fianzas_activas, monto_afianzado = row[0], row[1]

    cur.execute("SELECT COUNT(*) FROM propuestas WHERE cve_estatus_propuesta = 'T'")
    propuestas_proceso = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM fianzas_vigor WHERE estado = 'CANCELAR'")
    a_cancelar = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM fianzas_vigor WHERE estado = 'RENOVAR'")
    a_renovar = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(monto), 0) FROM fianzas_vigor WHERE estado = 'CANCELAR'")
    monto_liberable = cur.fetchone()[0]

    # Distribución por afianzadora
    cur.execute("""
        SELECT a.nombre, COUNT(*) as fianzas, SUM(f.monto) as monto
        FROM fianzas_vigor f JOIN afianzadoras a ON f.afianzadora_id = a.id
        WHERE f.estatus_fianza IN ('P', 'N', 'X')
        GROUP BY a.id ORDER BY monto DESC
    """)
    por_afianzadora = [dict(row) for row in cur.fetchall()]

    # Top 10 fiados por monto
    cur.execute("""
        SELECT fi.nombre, COUNT(*) as fianzas, SUM(f.monto) as monto
        FROM fianzas_vigor f JOIN fiados fi ON f.fiado_id = fi.id
        WHERE f.estatus_fianza IN ('P', 'N', 'X')
        GROUP BY fi.id ORDER BY monto DESC LIMIT 10
    """)
    top_fiados = [dict(row) for row in cur.fetchall()]

    # Top 10 beneficiarios por monto
    cur.execute("""
        SELECT b.nombre, COUNT(*) as fianzas, SUM(f.monto) as monto
        FROM fianzas_vigor f JOIN beneficiarios b ON f.beneficiario_id = b.id
        WHERE f.estatus_fianza IN ('P', 'N', 'X')
        GROUP BY b.id ORDER BY monto DESC LIMIT 10
    """)
    top_beneficiarios = [dict(row) for row in cur.fetchall()]

    return {
        "fianzas_activas": fianzas_activas,
        "monto_afianzado": monto_afianzado,
        "propuestas_proceso": propuestas_proceso,
        "a_cancelar": a_cancelar,
        "a_renovar": a_renovar,
        "monto_liberable": monto_liberable,
        "por_afianzadora": por_afianzadora,
        "top_fiados": top_fiados,
        "top_beneficiarios": top_beneficiarios,
    }


def dashboard_pipeline(db):
    """Dashboard 2: Pipeline de propuestas."""
    cur = db.cursor()

    # Embudo por estatus propuesta
    cur.execute("""
        SELECT cve_estatus_propuesta, desc_estatus_propuesta,
               COUNT(*) as cnt, SUM(monto_afianzado) as monto
        FROM propuestas
        GROUP BY cve_estatus_propuesta ORDER BY cnt DESC
    """)
    embudo_propuesta = [dict(row) for row in cur.fetchall()]

    # Distribución por estatus fianza
    cur.execute("""
        SELECT cve_estatus_fianza, desc_estatus_fianza,
               COUNT(*) as cnt, SUM(monto_afianzado) as monto
        FROM propuestas
        GROUP BY cve_estatus_fianza ORDER BY cnt DESC
    """)
    por_estatus_fianza = [dict(row) for row in cur.fetchall()]

    # Propuestas atoradas (>5 días en trámite)
    cur.execute("""
        SELECT p.propuesta, fi.nombre as fiado, b.nombre as beneficiario,
               p.monto_afianzado, p.dias_en_estatus, p.desc_estatus_fianza,
               p.desc_movto_fianza, p.fecha_inserto
        FROM propuestas p
        JOIN fiados fi ON p.fiado_id = fi.id
        JOIN beneficiarios b ON p.beneficiario_id = b.id
        WHERE p.cve_estatus_propuesta = 'T' AND p.dias_en_estatus > 5
        ORDER BY p.dias_en_estatus DESC LIMIT 20
    """)
    atoradas = [dict(row) for row in cur.fetchall()]

    # KPIs
    cur.execute("SELECT COUNT(*) FROM propuestas")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*), COALESCE(SUM(monto_afianzado), 0) FROM propuestas WHERE cve_estatus_propuesta = 'A'")
    row = cur.fetchone()
    autorizadas, monto_autorizadas = row[0], row[1]

    cur.execute("SELECT COUNT(*), COALESCE(SUM(monto_afianzado), 0) FROM propuestas WHERE cve_estatus_propuesta = 'T'")
    row = cur.fetchone()
    en_tramite, monto_tramite = row[0], row[1]

    tasa_conversion = round((autorizadas / total * 100), 1) if total > 0 else 0

    return {
        "total": total,
        "autorizadas": autorizadas,
        "en_tramite": en_tramite,
        "monto_autorizadas": monto_autorizadas,
        "monto_tramite": monto_tramite,
        "tasa_conversion": tasa_conversion,
        "embudo_propuesta": embudo_propuesta,
        "por_estatus_fianza": por_estatus_fianza,
        "atoradas": atoradas,
    }


def dashboard_cartera(db, ejecutivo_filter=None):
    """Dashboard 3: Cartera por ejecutivo."""
    cur = db.cursor()
    hoy = date.today().isoformat()

    # Filtro opcional por ejecutivo
    where_ejecutivo = f"AND fi.ejecutivo_id = '{ejecutivo_filter}'" if ejecutivo_filter else ""

    # Fiados por ejecutivo con status
    cur.execute(f"""
        SELECT
            e.nombre as ejecutivo,
            e.id as ejecutivo_id,
            COUNT(DISTINCT fi.id) as num_fiados,
            SUM(fi.linea_afianzamiento) as linea_total,
            SUM(fi.linea_disponible) as linea_disponible,
            SUM(CASE WHEN fi.expediente_vigente_hasta < DATE('now') THEN 1 ELSE 0 END) as expedientes_vencidos,
            SUM(CASE WHEN fi.buro_vigente_hasta < DATE('now') THEN 1 ELSE 0 END) as buros_vencidos,
            SUM(CASE WHEN fi.dictamen_vigente_hasta < DATE('now') THEN 1 ELSE 0 END) as dictamenes_vencidos
        FROM ejecutivos e
        JOIN fiados fi ON fi.ejecutivo_id = e.id
        WHERE 1=1 {where_ejecutivo}
        GROUP BY e.id
        ORDER BY linea_total DESC
    """)
    por_ejecutivo = [dict(row) for row in cur.fetchall()]

    # Detalle de fiados
    cur.execute(f"""
        SELECT fi.nombre, fi.rfc, e.nombre as ejecutivo,
               fi.linea_afianzamiento, fi.linea_disponible,
               fi.expediente_vigente_hasta, fi.buro_vigente_hasta,
               fi.dictamen_vigente_hasta, fi.categoria_buro,
               ROUND((fi.linea_disponible / fi.linea_afianzamiento) * 100, 1) as pct_disponible
        FROM fiados fi
        JOIN ejecutivos e ON fi.ejecutivo_id = e.id
        WHERE 1=1 {where_ejecutivo}
        ORDER BY fi.linea_afianzamiento DESC
    """)
    fiados = [dict(row) for row in cur.fetchall()]

    # Alertas
    cur.execute(f"""
        SELECT fi.nombre, fi.expediente_vigente_hasta as fecha_venc, 'expediente' as tipo
        FROM fiados fi
        WHERE fi.expediente_vigente_hasta BETWEEN DATE('now') AND DATE('now', '+30 days')
        {where_ejecutivo.replace('AND', 'AND') if ejecutivo_filter else ''}
        UNION ALL
        SELECT fi.nombre, fi.buro_vigente_hasta as fecha_venc, 'buró' as tipo
        FROM fiados fi
        WHERE fi.buro_vigente_hasta BETWEEN DATE('now') AND DATE('now', '+30 days')
        {where_ejecutivo.replace('AND', 'AND') if ejecutivo_filter else ''}
        ORDER BY fecha_venc LIMIT 15
    """)
    alertas = [dict(row) for row in cur.fetchall()]

    return {
        "por_ejecutivo": por_ejecutivo,
        "fiados": fiados,
        "alertas": alertas,
        "ejecutivo_filter": ejecutivo_filter,
    }


def dashboard_cobranza(db):
    """Dashboard 4: Cobranza."""
    cur = db.cursor()

    # Antigüedad de saldos
    cur.execute("""
        SELECT
            CASE
                WHEN dias_vencido = 0 THEN '0 - Al día'
                WHEN dias_vencido <= 30 THEN '1-30'
                WHEN dias_vencido <= 60 THEN '31-60'
                WHEN dias_vencido <= 90 THEN '61-90'
                ELSE '90+'
            END as bucket,
            COUNT(*) as cnt,
            SUM(monto_prima) as monto
        FROM cobranza WHERE estatus = 'VENCIDO'
        GROUP BY bucket ORDER BY bucket
    """)
    antiguedad = [dict(row) for row in cur.fetchall()]

    # Top deudores
    cur.execute("""
        SELECT fi.nombre as fiado, COUNT(c.id) as recibos,
               SUM(c.monto_prima) as deuda, MAX(c.dias_vencido) as dias_max
        FROM cobranza c
        JOIN fianzas_vigor f ON c.fianza_id = f.id
        JOIN fiados fi ON f.fiado_id = fi.id
        WHERE c.estatus = 'VENCIDO'
        GROUP BY fi.id
        ORDER BY deuda DESC LIMIT 15
    """)
    top_deudores = [dict(row) for row in cur.fetchall()]

    # KPIs
    cur.execute("SELECT COALESCE(SUM(monto_prima), 0) FROM cobranza WHERE estatus = 'VENCIDO'")
    prima_vencida = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(monto_prima), 0) FROM cobranza WHERE estatus = 'PENDIENTE'")
    prima_pendiente = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(monto_pagado), 0) FROM cobranza WHERE estatus = 'PAGADO'")
    prima_pagada = cur.fetchone()[0]

    return {
        "prima_vencida": prima_vencida,
        "prima_pendiente": prima_pendiente,
        "prima_pagada": prima_pagada,
        "antiguedad": antiguedad,
        "top_deudores": top_deudores,
    }
