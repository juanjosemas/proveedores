@echo off
echo.
echo ============================================
echo   ACTUALIZAR PRESUPUESTOS - PROVEEDORES
echo   ECO STRUCT
echo ============================================
echo.

REM -- Paso 1: Generar el HTML --
echo [1/3] Regenerando visor HTML...
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

REM -- Paso 2: Verificar repositorio git --
echo [2/3] Verificando repositorio git...
git status >nul 2>&1
if %errorlevel% neq 0 (
    echo No es un repositorio git. Inicializando...
    git init
    git branch -M main
    git remote add origin https://github.com/juanjosemas/proveedores.git
)
echo OK: Repositorio git listo.
echo.

REM -- Paso 3: Anadir archivos y mostrar cambios --
echo [3/3] Preparando archivos para GitHub...
git add proveedores.html
git add icons/
git add PROVEEDORES/
git add README.md
git add .gitignore
git add generar_html.py
git add actualizar.bat
git add subir_a_github.bat

echo.
echo ============================================
echo   ARCHIVOS CAMBIADOS:
echo ============================================
git status --short
echo.

REM -- Preguntar si quiere subir --
set /p "SUBIR=Quieres subir estos cambios a GitHub? (S/N): "
if /i not "%SUBIR%"=="S" (
    echo.
    echo Cancelado. No se ha subido nada.
    echo.
    pause
    exit /b 0
)

REM -- Commitear (si no hay nada, git lo dira) --
echo.
echo Creando commit...
git commit -m "Actualizacion de presupuestos" 2>nul
if %errorlevel% neq 0 (
    echo.
    echo No hay cambios nuevos para commitear.
    echo.
    pause
    exit /b 0
)

REM -- Subir a GitHub --
echo Subiendo a GitHub...
git push -u origin main

if %errorlevel% neq 0 (
    echo.
    echo ERROR: No se pudo subir a GitHub. Comprueba tu conexion.
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   LISTO! Todo actualizado en GitHub.
echo   Visible en 1-2 minutos en:
echo   https://juanjosemas.github.io/proveedores/proveedores.html
echo ============================================
echo.
pause
