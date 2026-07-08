"""Chat conversacional con Claude Sonnet + function calling."""

import json
import os
import re
import sqlite3
from datetime import date

from app.services.db import get_db

# Sistema prompt con el glosario operativo
SYSTEM_PROMPT = """Eres el asistente de Orkesta Fianzas, especializado en análisis del negocio de fianzas para Senties Chauvet.

CONTEXTO DEL NEGOCIO:
- Senties es un broker top-5 de fianzas en México
- Trabajan con 6 afianzadoras: Chubb (principal), Aserta, Tokio Marine (por API) + Berkeley, Sofimex, Mapfre (por correo)
- Sus clientes principales tienen contratos con Pemex, IMSS, ISSSTE, Instituto Nacional de Cancerología, Tesorería de la Federación
- Manejan aprox 500 fianzas activas y 200 propuestas en proceso

GLOSARIO OPERATIVO (validado con Marlene Barrera):
- ESTATUS DE FIANZA:
  * T = Trámite (esperando documentación)
  * M = Por Autorizar (Senties debe gestionar con afianzadora)
  * N = Autorizada (lista para emisión)
  * P = Producción (activa, generando primas)
  * C = Cancelada (liberada, no consume línea)
  * O = Cancelada en oficina (por canal alternativo)
  * L = En Lote (procesamiento batch)
  * X = En Lote Expedida (batch completado, fianza viva)

- ESTADO (campo derivado, ¡clave!):
  * CANCELAR = fecha_cumplimiento ya pasó, hay que gestionar cancelación
  * RENOVAR = próxima a vencer, hay que gestionar renovación
  * NULL = activa sin acción pendiente

- REGLA DE NEGOCIO PRINCIPAL: fecha_cumplimiento < hoy → cancelable (libera línea)

Cuando el usuario pregunte algo, USA las funciones disponibles para obtener los datos reales. NUNCA inventes números.

FORMATO DE RESPUESTA (importante):
- Responde en español, en máximo 3-5 oraciones cuando el dato es simple, o con bullets cuando hay varios items.
- NUNCA uses tablas markdown (con |----|). El frontend no las renderiza.
- Para desglosar valores por categoría, usa bullets con guiones (- item: valor).
- Los montos siempre en MXN con formato $XXX,XXX.XX.
- Usa **negritas** para resaltar los números clave y nombres de entidades.
- Al final de cada respuesta, cita brevemente la fuente ("Datos: fianzas activas al día de hoy" por ejemplo).
- No uses ### para headers dentro de la respuesta, usa **negritas** para subtítulos si necesitas.
"""

# ============================================================
# TOOLS (function calling)
# ============================================================

TOOLS = [
    {
        "name": "consultar_kpis_globales",
        "description": "Retorna KPIs globales del broker: monto afianzado total, número de fianzas activas, propuestas en proceso, cancelables, renovables. Úsalo cuando el usuario pregunte sobre 'cómo va el negocio', 'estado general', 'resumen'.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "exposicion_por_beneficiario",
        "description": "Retorna la exposición total con un beneficiario específico. Usa keywords como PEMEX, IMSS, ISSSTE, Tesorería. Búsqueda parcial (case insensitive).",
        "input_schema": {
            "type": "object",
            "properties": {
                "beneficiario_query": {"type": "string", "description": "Nombre parcial del beneficiario a buscar (ej. 'pemex', 'imss')"}
            },
            "required": ["beneficiario_query"]
        }
    },
    {
        "name": "propuestas_atoradas",
        "description": "Retorna propuestas que llevan más de N días en el mismo estatus (por default N=5). Útil para identificar bloqueos.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dias_minimo": {"type": "integer", "description": "Umbral de días. Default 5", "default": 5}
            }
        }
    },
    {
        "name": "fianzas_por_vencer",
        "description": "Retorna fianzas cuya fecha de cumplimiento está dentro de los próximos N meses (default 1).",
        "input_schema": {
            "type": "object",
            "properties": {
                "meses": {"type": "integer", "description": "Ventana en meses. Default 1", "default": 1}
            }
        }
    },
    {
        "name": "top_fiados",
        "description": "Top N fiados ordenados por monto afianzado total.",
        "input_schema": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "Cuántos fiados retornar. Default 10", "default": 10}
            }
        }
    },
    {
        "name": "consultar_fiado",
        "description": "Retorna información completa de un fiado: línea de afianzamiento, disponible, expediente, buró, dictamen, y sus fianzas activas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fiado_query": {"type": "string", "description": "Nombre parcial o RFC del fiado a buscar"}
            },
            "required": ["fiado_query"]
        }
    },
    {
        "name": "resumen_cancelables",
        "description": "Retorna las fianzas marcadas como CANCELAR: cuántas son, monto total que liberaría de línea, y por fiado.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "distribucion_por_afianzadora",
        "description": "Distribución de fianzas activas por afianzadora (Chubb, Aserta, etc).",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "saldos_por_antiguedad",
        "description": "Retorna la distribución de saldos vencidos por antigüedad (1-30, 31-60, 61-90, 90+ días). Úsalo cuando el usuario pregunte por cobranza vencida, antigüedad de saldos, cartera vencida por rango, o específicamente 'vencido 90+ días' u otras franjas.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "top_deudores_cobranza",
        "description": "Retorna los top N fiados con mayor deuda vencida (prima no pagada), con recibos y días máximo de mora. Úsalo para 'top deudores', '¿quiénes me deben más?', 'cartera vencida por cliente'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "Cuántos deudores retornar. Default 10", "default": 10}
            }
        }
    },
]


# ============================================================
# TOOL IMPLEMENTATIONS
# ============================================================

def _consultar_kpis_globales():
    db = get_db()
    cur = db.cursor()

    cur.execute("SELECT COUNT(*), COALESCE(SUM(monto), 0) FROM fianzas_vigor WHERE estatus_fianza IN ('P', 'N', 'X')")
    fianzas, monto = cur.fetchone()

    cur.execute("SELECT COUNT(*) FROM propuestas WHERE cve_estatus_propuesta = 'T'")
    prop_tramite = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*), COALESCE(SUM(monto), 0) FROM fianzas_vigor WHERE estado = 'CANCELAR'")
    cancelables_n, cancelables_monto = cur.fetchone()

    cur.execute("SELECT COUNT(*) FROM fianzas_vigor WHERE estado = 'RENOVAR'")
    renovables = cur.fetchone()[0]

    db.close()

    return {
        "fianzas_activas": fianzas,
        "monto_afianzado_total_mxn": monto,
        "propuestas_en_tramite": prop_tramite,
        "fianzas_a_cancelar": cancelables_n,
        "monto_liberable_al_cancelar_mxn": cancelables_monto,
        "fianzas_a_renovar_proximo_mes": renovables,
        "fuente": "Fianzas en vigor + Propuestas activas"
    }


def _exposicion_por_beneficiario(beneficiario_query):
    db = get_db()
    cur = db.cursor()
    query_lower = f"%{beneficiario_query.upper()}%"
    cur.execute("""
        SELECT b.nombre, COUNT(*) as fianzas, SUM(f.monto) as monto
        FROM fianzas_vigor f JOIN beneficiarios b ON f.beneficiario_id = b.id
        WHERE UPPER(b.nombre) LIKE ? AND f.estatus_fianza IN ('P', 'N', 'X')
        GROUP BY b.id ORDER BY monto DESC
    """, (query_lower,))
    resultados = [dict(r) for r in cur.fetchall()]

    monto_total = sum(r["monto"] for r in resultados)
    num_total = sum(r["fianzas"] for r in resultados)

    db.close()
    return {
        "beneficiarios_encontrados": resultados,
        "monto_total_mxn": monto_total,
        "total_fianzas": num_total,
        "fuente": f"Búsqueda: '{beneficiario_query}' en beneficiarios de fianzas activas"
    }


def _propuestas_atoradas(dias_minimo=5):
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT p.propuesta, fi.nombre as fiado, b.nombre as beneficiario,
               p.monto_afianzado, p.dias_en_estatus, p.desc_estatus_fianza, p.desc_movto_fianza
        FROM propuestas p
        JOIN fiados fi ON p.fiado_id = fi.id
        JOIN beneficiarios b ON p.beneficiario_id = b.id
        WHERE p.cve_estatus_propuesta = 'T' AND p.dias_en_estatus > ?
        ORDER BY p.dias_en_estatus DESC LIMIT 15
    """, (dias_minimo,))
    resultados = [dict(r) for r in cur.fetchall()]
    monto = sum(r["monto_afianzado"] for r in resultados)
    db.close()
    return {
        "propuestas_atoradas": resultados,
        "total_encontradas": len(resultados),
        "monto_total_bloqueado_mxn": monto,
        "fuente": f"Propuestas en trámite > {dias_minimo} días"
    }


def _fianzas_por_vencer(meses=1):
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT fi.nombre as fiado, b.nombre as beneficiario, f.monto, f.fecha_cumplimiento, f.producto
        FROM fianzas_vigor f
        JOIN fiados fi ON f.fiado_id = fi.id
        JOIN beneficiarios b ON f.beneficiario_id = b.id
        WHERE f.fecha_cumplimiento BETWEEN DATE('now') AND DATE('now', ?)
        AND f.estatus_fianza IN ('P', 'N', 'X')
        ORDER BY f.fecha_cumplimiento ASC LIMIT 20
    """, (f'+{meses} months',))
    resultados = [dict(r) for r in cur.fetchall()]
    monto = sum(r["monto"] for r in resultados)
    db.close()
    return {
        "fianzas_por_vencer": resultados,
        "total": len(resultados),
        "monto_total_mxn": monto,
        "fuente": f"Fianzas con fecha_cumplimiento en próximos {meses} mes(es)"
    }


def _top_fiados(n=10):
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT fi.nombre, fi.rfc, COUNT(*) as fianzas, SUM(f.monto) as monto,
               fi.linea_afianzamiento, fi.linea_disponible
        FROM fianzas_vigor f JOIN fiados fi ON f.fiado_id = fi.id
        WHERE f.estatus_fianza IN ('P', 'N', 'X')
        GROUP BY fi.id ORDER BY monto DESC LIMIT ?
    """, (n,))
    resultados = [dict(r) for r in cur.fetchall()]
    db.close()
    return {"top_fiados": resultados, "fuente": "Fianzas activas agrupadas por fiado"}


def _consultar_fiado(fiado_query):
    db = get_db()
    cur = db.cursor()
    query_lower = f"%{fiado_query.upper()}%"
    cur.execute("""
        SELECT fi.*, e.nombre as ejecutivo_nombre
        FROM fiados fi JOIN ejecutivos e ON fi.ejecutivo_id = e.id
        WHERE UPPER(fi.nombre) LIKE ? OR UPPER(fi.rfc) LIKE ?
        LIMIT 5
    """, (query_lower, query_lower))
    fiados = [dict(r) for r in cur.fetchall()]

    if not fiados:
        db.close()
        return {"encontrado": False, "mensaje": f"No se encontró fiado con '{fiado_query}'"}

    fiado = fiados[0]
    cur.execute("""
        SELECT b.nombre as beneficiario, f.monto, f.fecha_cumplimiento, f.producto, f.estatus_fianza_desc, f.estado
        FROM fianzas_vigor f JOIN beneficiarios b ON f.beneficiario_id = b.id
        WHERE f.fiado_id = ? AND f.estatus_fianza IN ('P', 'N', 'X')
        ORDER BY f.monto DESC LIMIT 10
    """, (fiado["id"],))
    fianzas = [dict(r) for r in cur.fetchall()]

    db.close()
    return {
        "encontrado": True,
        "fiado": fiado,
        "fianzas_activas_top10": fianzas,
        "fuente": f"Fiado {fiado['nombre']} (RFC {fiado['rfc']})"
    }


def _resumen_cancelables():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT COUNT(*), COALESCE(SUM(monto), 0) FROM fianzas_vigor WHERE estado = 'CANCELAR'")
    n, monto = cur.fetchone()

    cur.execute("""
        SELECT fi.nombre, COUNT(*) as cnt, SUM(f.monto) as monto
        FROM fianzas_vigor f JOIN fiados fi ON f.fiado_id = fi.id
        WHERE f.estado = 'CANCELAR' GROUP BY fi.id ORDER BY monto DESC LIMIT 10
    """)
    por_fiado = [dict(r) for r in cur.fetchall()]
    db.close()
    return {
        "total_cancelables": n,
        "monto_total_liberable_mxn": monto,
        "top_fiados_con_cancelables": por_fiado,
        "fuente": "Fianzas con estado = CANCELAR"
    }


def _distribucion_por_afianzadora():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT a.nombre, a.tipo_integracion, COUNT(*) as fianzas, SUM(f.monto) as monto
        FROM fianzas_vigor f JOIN afianzadoras a ON f.afianzadora_id = a.id
        WHERE f.estatus_fianza IN ('P', 'N', 'X')
        GROUP BY a.id ORDER BY monto DESC
    """)
    resultados = [dict(r) for r in cur.fetchall()]
    db.close()
    return {"distribucion": resultados, "fuente": "Fianzas activas por afianzadora"}


def _saldos_por_antiguedad():
    """Distribución de recibos vencidos por antigüedad (para el módulo Cobranza)."""
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT
            CASE
                WHEN dias_vencido <= 30 THEN '1-30 días'
                WHEN dias_vencido <= 60 THEN '31-60 días'
                WHEN dias_vencido <= 90 THEN '61-90 días'
                ELSE '90+ días'
            END as bucket,
            COUNT(*) as recibos,
            SUM(monto_prima) as monto_mxn
        FROM cobranza
        WHERE estatus = 'VENCIDO'
        GROUP BY bucket
        ORDER BY MIN(dias_vencido)
    """)
    buckets = [dict(r) for r in cur.fetchall()]
    total_monto = sum(b["monto_mxn"] for b in buckets)
    total_recibos = sum(b["recibos"] for b in buckets)
    db.close()
    return {
        "distribucion_por_antiguedad": buckets,
        "total_vencido_mxn": total_monto,
        "total_recibos_vencidos": total_recibos,
        "fuente": "Recibos de cobranza con estatus VENCIDO"
    }


def _top_deudores_cobranza(n=10):
    """Top N fiados con mayor deuda vencida acumulada."""
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT fi.nombre as fiado, fi.rfc,
               COUNT(c.id) as recibos_vencidos,
               SUM(c.monto_prima) as deuda_mxn,
               MAX(c.dias_vencido) as dias_max_mora
        FROM cobranza c
        JOIN fianzas_vigor f ON c.fianza_id = f.id
        JOIN fiados fi ON f.fiado_id = fi.id
        WHERE c.estatus = 'VENCIDO'
        GROUP BY fi.id
        ORDER BY deuda_mxn DESC
        LIMIT ?
    """, (n,))
    deudores = [dict(r) for r in cur.fetchall()]
    total = sum(d["deuda_mxn"] for d in deudores)
    db.close()
    return {
        "top_deudores": deudores,
        "deuda_total_top_mxn": total,
        "fuente": "Cobranza vencida agrupada por fiado"
    }


TOOL_FUNCTIONS = {
    "consultar_kpis_globales": _consultar_kpis_globales,
    "exposicion_por_beneficiario": _exposicion_por_beneficiario,
    "propuestas_atoradas": _propuestas_atoradas,
    "fianzas_por_vencer": _fianzas_por_vencer,
    "top_fiados": _top_fiados,
    "consultar_fiado": _consultar_fiado,
    "resumen_cancelables": _resumen_cancelables,
    "distribucion_por_afianzadora": _distribucion_por_afianzadora,
    "saldos_por_antiguedad": _saldos_por_antiguedad,
    "top_deudores_cobranza": _top_deudores_cobranza,
}


# Prompts contextuales por módulo (Nivel 2 — Claude sabe qué módulo estás viendo)
MODULE_PROMPTS = {
    "salud": "\n\nCONTEXTO ACTUAL: El usuario está viendo el dashboard de Salud de la Cartera (visión global del negocio). Enfoca las respuestas en KPIs consolidados, exposición por beneficiario, distribución por afianzadora y top fiados. Si preguntan por cobranza específica o pipeline, responde igual pero sugiere abrir el módulo respectivo al final.",
    "pipeline": "\n\nCONTEXTO ACTUAL: El usuario está viendo el dashboard de Pipeline de propuestas. Enfoca las respuestas en propuestas atoradas, tasa de conversión, embudo por estatus y monto en trámite. Usa las funciones propuestas_atoradas y consultar_kpis_globales prioritariamente.",
    "cartera": "\n\nCONTEXTO ACTUAL: El usuario está viendo el dashboard de Cartera por ejecutivo (la vista que Marlene Barrera pidió específicamente). Enfoca las respuestas en líneas de crédito, expedientes/buró/dictamen vencidos, y consultas específicas por fiado. Usa consultar_fiado y top_fiados prioritariamente.",
    "cobranza": "\n\nCONTEXTO ACTUAL: El usuario está viendo el dashboard de Cobranza. Enfoca las respuestas en antigüedad de saldos, top deudores, prima vencida vs cobrada. Usa las funciones saldos_por_antiguedad y top_deudores_cobranza prioritariamente para preguntas sobre saldos vencidos, deudores o antigüedad. Si te preguntan por otros temas responde igual pero sugiere abrir el módulo respectivo.",
    "global": "",
}


# ============================================================
# CHAT — usa Claude si hay API key, si no usa fallback local
# ============================================================

def ask(question: str, module_context: str = "global") -> str:
    """Endpoint principal del chat.

    module_context: 'salud', 'pipeline', 'cartera', 'cobranza' o 'global'
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if api_key:
        try:
            return _ask_claude(question, api_key, module_context)
        except Exception as e:
            print(f"[chat] Error con Claude API, usando fallback local: {type(e).__name__}: {e}")
            return _ask_fallback(question)
    else:
        return _ask_fallback(question)


def _ask_claude(question: str, api_key: str, module_context: str = "global") -> str:
    """Chat con Claude Sonnet real vía HTTP directo (evita issues del SDK en Python 3.14)."""
    import urllib.request
    import urllib.error

    # Sistema prompt con contexto del módulo activo
    system_prompt = SYSTEM_PROMPT + MODULE_PROMPTS.get(module_context, "")

    messages = [{"role": "user", "content": question}]

    # Loop de function calling
    for _ in range(5):  # máximo 5 rondas de tools
        payload = json.dumps({
            "model": "claude-sonnet-4-5",
            "max_tokens": 2048,
            "system": system_prompt,
            "tools": TOOLS,
            "messages": messages
        }, default=str).encode("utf-8")

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {e.code} from Anthropic: {body[:300]}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error to Anthropic: {e}")

        stop_reason = data.get("stop_reason")
        content_blocks = data.get("content", [])

        if stop_reason == "tool_use":
            # Extraer tool calls
            tool_results = []
            for block in content_blocks:
                if block.get("type") == "tool_use":
                    tool_name = block.get("name")
                    tool_input = block.get("input", {})
                    if tool_name in TOOL_FUNCTIONS:
                        try:
                            result = TOOL_FUNCTIONS[tool_name](**tool_input)
                        except Exception as tool_err:
                            result = {"error": f"tool execution failed: {type(tool_err).__name__}: {tool_err}"}
                    else:
                        result = {"error": f"tool not found: {tool_name}"}
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.get("id"),
                        "content": json.dumps(result, default=str, ensure_ascii=False)
                    })

            messages.append({"role": "assistant", "content": content_blocks})
            messages.append({"role": "user", "content": tool_results})
            continue

        # Terminó — extraer texto final
        for block in content_blocks:
            if block.get("type") == "text":
                return block.get("text", "")

    return "No pude completar la respuesta después de varias rondas de análisis."


def _ask_fallback(question: str) -> str:
    """Fallback simple sin Claude (para cuando no hay API key)."""
    q = question.lower()

    if "pemex" in q or "imss" in q or "issste" in q or "tesorería" in q or "tesoreria" in q:
        # Extraer keyword
        for kw in ["pemex", "imss", "issste", "tesorería", "tesoreria", "cancerología", "cancerologia"]:
            if kw in q:
                result = _exposicion_por_beneficiario(kw)
                monto = result["monto_total_mxn"]
                num = result["total_fianzas"]
                if num == 0:
                    return f"No encontré fianzas con beneficiarios que incluyan '{kw}'."
                items = "\n".join([f"  • {r['nombre']}: {r['fianzas']} fianzas, ${r['monto']:,.2f} MXN" for r in result["beneficiarios_encontrados"][:5]])
                return f"**Exposición con beneficiarios que incluyen '{kw}':**\n\nTotal: {num} fianzas por ${monto:,.2f} MXN\n\nDesglose:\n{items}\n\n_Fuente: {result['fuente']}_"

    if "atorada" in q or "atascadas" in q or "atoradas" in q or "bloqueo" in q or "trámite" in q:
        result = _propuestas_atoradas(5)
        if result["total_encontradas"] == 0:
            return "No hay propuestas atoradas más de 5 días. Todo está fluyendo bien."
        items = "\n".join([f"  • Propuesta {r['propuesta']} — {r['fiado'][:40]} → {r['beneficiario'][:35]}: ${r['monto_afianzado']:,.2f} ({r['dias_en_estatus']} días en {r['desc_estatus_fianza']})" for r in result["propuestas_atoradas"][:10]])
        return f"**Propuestas atoradas (>5 días en trámite):**\n\n{result['total_encontradas']} propuestas por ${result['monto_total_bloqueado_mxn']:,.2f} MXN\n\nTop 10:\n{items}\n\n_Fuente: {result['fuente']}_"

    # Cobranza — DEBE ir antes de "cancelar" para evitar colisión con "cancelación de recibos"
    if "vencido" in q or "vencida" in q or "vencidos" in q or "vencidas" in q or "antigüedad" in q or "antiguedad" in q or "mora" in q or "90+" in q or "60+" in q or "30+" in q:
        result = _saldos_por_antiguedad()
        if result["total_recibos_vencidos"] == 0:
            return "No hay saldos vencidos en cobranza. Todo al corriente."
        items = "\n".join([f"  • {b['bucket']}: {b['recibos']} recibos, ${b['monto_mxn']:,.2f}" for b in result["distribucion_por_antiguedad"]])
        return f"**Antigüedad de saldos vencidos:**\n\n{result['total_recibos_vencidos']} recibos por ${result['total_vencido_mxn']:,.2f} MXN\n\nDesglose:\n{items}\n\n_Fuente: {result['fuente']}_"

    if "deudor" in q or "deudores" in q or "me deben" in q or "cartera vencida" in q:
        result = _top_deudores_cobranza(10)
        if not result["top_deudores"]:
            return "No hay deudores con saldos vencidos."
        items = "\n".join([f"  {i+1}. **{r['fiado'][:50]}** ({r['rfc']}): {r['recibos_vencidos']} recibos, ${r['deuda_mxn']:,.2f} MXN — hasta {r['dias_max_mora']} días de mora" for i, r in enumerate(result["top_deudores"])])
        return f"**Top 10 deudores por prima vencida:**\n\nDeuda acumulada: ${result['deuda_total_top_mxn']:,.2f} MXN\n\n{items}\n\n_Fuente: {result['fuente']}_"

    if "cancelar" in q or "cancelables" in q or "liberar" in q:
        result = _resumen_cancelables()
        items = "\n".join([f"  • {r['nombre'][:50]}: {r['cnt']} fianzas, ${r['monto']:,.2f}" for r in result["top_fiados_con_cancelables"][:5]])
        return f"**Fianzas a cancelar:**\n\n{result['total_cancelables']} fianzas con estado CANCELAR\nMonto liberable de línea: ${result['monto_total_liberable_mxn']:,.2f} MXN\n\nTop 5 fiados:\n{items}\n\n_Fuente: {result['fuente']}_"

    if "top" in q and ("fiado" in q or "cliente" in q):
        result = _top_fiados(10)
        items = "\n".join([f"  {i+1}. {r['nombre'][:50]}: {r['fianzas']} fianzas, ${r['monto']:,.2f} (línea: ${r['linea_afianzamiento']:,.0f})" for i, r in enumerate(result["top_fiados"])])
        return f"**Top 10 fiados por monto afianzado:**\n\n{items}\n\n_Fuente: {result['fuente']}_"

    if "afianzadora" in q or "distribución" in q or "distribucion" in q:
        result = _distribucion_por_afianzadora()
        items = "\n".join([f"  • {r['nombre']} ({r['tipo_integracion']}): {r['fianzas']} fianzas, ${r['monto']:,.2f}" for r in result["distribucion"]])
        return f"**Distribución por afianzadora:**\n\n{items}\n\n_Fuente: {result['fuente']}_"

    # Default: KPIs globales
    result = _consultar_kpis_globales()
    return f"""**Resumen general del negocio:**

- Fianzas activas: {result['fianzas_activas']}
- Monto afianzado total: ${result['monto_afianzado_total_mxn']:,.2f} MXN
- Propuestas en trámite: {result['propuestas_en_tramite']}
- Fianzas a cancelar: {result['fianzas_a_cancelar']} (libera ${result['monto_liberable_al_cancelar_mxn']:,.2f} de línea)
- Fianzas a renovar próximo mes: {result['fianzas_a_renovar_proximo_mes']}

_Fuente: {result['fuente']}_

*Puedes preguntarme cosas como:*
- "¿Cuál es mi exposición con Pemex?"
- "¿Qué propuestas están atoradas?"
- "Top 10 fiados por monto"
- "Distribución por afianzadora"
- "Antigüedad de saldos vencidos"
- "Top deudores de cobranza"
- "¿Cuántas fianzas necesito cancelar?"
"""
