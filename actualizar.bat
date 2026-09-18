@echo off
echo.
echo ============================================
echo   ACTUALIZAR PRESUPUESTOS - PROVEEDORES
echo   ECO STRUCT
echo ============================================
echo.

REM -- Paso 1: Generar el HTML --
echo [1/2] Regenerando visor HTML...
python "%~dp0generar_html.py"

if errorlevel 1 (
    echo.
    echo Error al ejecutar. Tienes Python instalado?
    echo Descarga desde: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
echo.

REM -- Paso 2: Subir a GitHub --
echo [2/2] Subiendo a GitHub...
git add proveedores.html
git add icons/
git add PROVEEDORES/
git commit -m "Actualizacion de presupuestos" 2>nul
git push -u origin main

if %errorlevel% neq 0 (
    echo.
    echo No se pudo subir a GitHub. Ejecuta subir_a_github.bat manualmente.
    echo.
) else (
    echo.
    echo ============================================
    echo   TODO ACTUALIZADO!
    echo   https://juanjosemas.github.io/proveedores/proveedores.html
    echo ============================================
)
echo.
pause
