"""
Runner del Reporte MEXMOT
==========================

Flujo:
  1. Carga el JSON extraido del API de Chubb (ok_fianzas_vigor_todas)
  2. Filtra las fianzas del fiado MEXMOT (NumeroFiado = 657687)
  3. Genera el Excel branded via senties_report_generator (source="api")
  4. Abre el Excel automaticamente

Espera esta estructura de proyecto:
    scripts/
      senties_report_generator.py
      demo_report_runner.py         <- este archivo
    data/
      chubb_fianzas_vigor.json      <- copia de ok_fianzas_vigor_(todas).json
    assets/
      senties_logo.png              <- opcional
    reportes/                        <- se crea al correr

Uso desde el bat:
    python scripts\\demo_report_runner.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path


# ============================================================
# CONFIGURACION DEL CLIENTE MEXMOT
# ============================================================
# Para cambiar de cliente, ajusta estas 3 constantes o parametriza el bat.
FIADO_NUMERO = "657687"
FIADO_NOMBRE = "MOTORES E INGENIERIA MEXMOT, S.A DE C.V."
CLIENTE_HEADER = f"{FIADO_NUMERO} - {FIADO_NOMBRE}"


def _print_banner(msg: str, color: str = "cyan"):
    """Print con banner simple (sin colors reales, solo estructura)."""
    print(msg)


def main():
    project_root = Path(__file__).parent.parent

    # Fuente unica del generator: C:\Users\manue\Documents\Senties & Chauvet\
    # (el demo NO tiene copia local; siempre lee de ahi)
    GENERATOR_DIR = Path(r"C:\Users\manue\Documents\Senties & Chauvet")
    sys.path.insert(0, str(GENERATOR_DIR))

    # ------------------------------------------------------------
    # 1. Importar generator (verificar dependencia)
    # ------------------------------------------------------------
    try:
        import pandas as pd
        from senties_report_generator import generar_reporte_vigor
    except ImportError as e:
        print(f"[ERROR] No se pudo importar dependencia: {e}")
        print(f"        Verifica:")
        print(f"          - {GENERATOR_DIR}\\senties_report_generator.py exista")
        print(f"          - pandas y xlsxwriter esten instalados")
        sys.exit(1)

    # ------------------------------------------------------------
    # 2. Paths
    # ------------------------------------------------------------
    json_path = project_root / "data" / "chubb_fianzas_vigor.json"
    logo_path = project_root / "assets" / "senties_logo.png"
    output_dir = project_root / "reportes"

    if not json_path.exists():
        print(f"[ERROR] No existe el JSON del API en:")
        print(f"        {json_path}")
        print(f"        Copia el archivo ok_fianzas_vigor_(todas).json de tu extraccion")
        print(f"        de Chubb y renombralo a chubb_fianzas_vigor.json en data\\")
        sys.exit(1)

    logo_arg = str(logo_path) if logo_path.exists() else None
    output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------
    # 3. Cargar JSON
    # ------------------------------------------------------------
    print()
    print("=" * 60)
    print("  REPORTE FIANZAS EN VIGOR - MEXMOT")
    print("  Orkesta / API de Chubb")
    print("=" * 60)
    print()

    t0 = time.time()
    print("[1/4] Cargando snapshot del API de Chubb...")

    with open(json_path, encoding="utf-8") as f:
        fianzas = json.load(f)

    # Soportar tanto lista pura como envelope {"Data": [...]}
    if isinstance(fianzas, dict) and "Data" in fianzas:
        fianzas = fianzas["Data"]

    if not isinstance(fianzas, list):
        print(f"[ERROR] JSON no es una lista de fianzas. Tipo recibido: {type(fianzas).__name__}")
        sys.exit(1)

    tiempo_carga = (time.time() - t0) * 1000
    print(f"      {len(fianzas):,} fianzas totales del broker ({tiempo_carga:.0f} ms)")

    # ------------------------------------------------------------
    # 4. Filtrar por fiado (MEXMOT)
    # ------------------------------------------------------------
    t1 = time.time()
    print(f"[2/4] Filtrando fianzas de {FIADO_NOMBRE[:40]}... (fiado {FIADO_NUMERO})")

    mexmot = [
        f for f in fianzas
        if str(f.get("NumeroFiado", "")).strip() == FIADO_NUMERO
    ]

    tiempo_filtro = (time.time() - t1) * 1000

    if not mexmot:
        print(f"[ERROR] No se encontraron fianzas de MEXMOT (fiado {FIADO_NUMERO})")
        print(f"        Verifica que el JSON de Chubb sea el correcto.")
        sys.exit(1)

    print(f"      {len(mexmot)} fianzas encontradas ({tiempo_filtro:.0f} ms)")

    # ------------------------------------------------------------
    # 5. Generar Excel branded
    # ------------------------------------------------------------
    t2 = time.time()
    print("[3/4] Generando reporte branded (Senties Chauvet)...")

    df = pd.DataFrame(mexmot)

    # Convertir fechas a datetime para que _row_from_api las procese bien
    for col in ("VigenciaDel", "VigenciaAl", "Cumplimiento", "FechaMovimiento"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    try:
        excel_bytes = generar_reporte_vigor(
            fianzas_df=df,
            logo_path=logo_arg,
            source="api",
        )
    except Exception as e:
        print(f"\n[ERROR] Fallo la generacion: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    tiempo_gen = (time.time() - t2) * 1000
    print(f"      Excel generado ({len(excel_bytes) / 1024:.1f} KB, {tiempo_gen:.0f} ms)")

    # ------------------------------------------------------------
    # 6. Guardar con timestamp
    # ------------------------------------------------------------
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_path = output_dir / f"Reporte_MEXMOT_{stamp}.xlsx"

    with open(output_path, "wb") as f:
        f.write(excel_bytes)

    tiempo_total = (time.time() - t0) * 1000
    print(f"[4/4] Guardado y abriendo Excel...")
    print()
    print(f"      Archivo: {output_path.name}")
    print(f"      Ruta:    {output_path}")
    print(f"      Total:   {tiempo_total:.0f} ms")
    if logo_arg is None:
        print(f"      (Logo Senties no detectado en assets\\senties_logo.png)")
    print()

    # ------------------------------------------------------------
    # 7. Abrir en Excel
    # ------------------------------------------------------------
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(output_path))
        elif sys.platform == "darwin":
            os.system(f'open "{output_path}"')
        else:
            os.system(f'xdg-open "{output_path}"')
    except Exception as e:
        print(f"[WARN] No se pudo abrir automaticamente: {e}")
        print(f"       Abrelo manualmente en: {output_path}")


if __name__ == "__main__":
    main()
