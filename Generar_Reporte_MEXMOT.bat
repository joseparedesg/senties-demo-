@echo off
REM ============================================================
REM  Generar Reporte MEXMOT - desde snapshot del API Chubb
REM  Doble-click desde la carpeta del proyecto.
REM ============================================================

chcp 65001 >nul
cd /d "%~dp0"

echo.

REM Verificar Python
where python >nul 2>nul
if errorlevel 1 goto :no_python

REM Verificar dependencias
python -c "import xlsxwriter, pandas, openpyxl" >nul 2>nul
if errorlevel 1 goto :install_deps

:check_json
if not exist "data\chubb_fianzas_vigor.json" goto :no_json

:run
python scripts\demo_report_runner.py
if errorlevel 1 goto :run_error

timeout /t 3 /nobreak >nul
exit /b 0

REM =====================================================================
REM  Manejadores de error
REM =====================================================================

:no_python
echo [ERROR] Python no esta instalado o no esta en el PATH.
echo         Instala Python 3.11+ desde https://www.python.org/downloads/
echo.
pause
exit /b 1

:install_deps
echo [SETUP] Instalando dependencias por primera vez...
python -m pip install xlsxwriter pandas openpyxl pillow --quiet
if errorlevel 1 goto :install_failed
echo [SETUP] Dependencias instaladas correctamente.
echo.
goto :check_json

:install_failed
echo [ERROR] No se pudieron instalar las dependencias.
echo         Corre manualmente:
echo             pip install xlsxwriter pandas openpyxl pillow
echo.
pause
exit /b 1

:no_json
echo [ERROR] No existe el archivo data\chubb_fianzas_vigor.json
echo.
echo   Copia el JSON del snapshot del API Chubb a esa ruta.
echo   El archivo original se llama ok_fianzas_vigor y termina en todas.json
echo   y esta en la carpeta chubb_extraction\20260629_200139\
echo.
pause
exit /b 1

:run_error
echo.
echo [ERROR] La generacion termino con error. Revisa el mensaje de arriba.
pause
exit /b 1
