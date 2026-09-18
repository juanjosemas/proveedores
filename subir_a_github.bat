@echo off
echo.
echo ============================================
echo   PROVEEDORES - Subir a GitHub
echo   juanjosemas.github.io/proveedores
echo ============================================
echo.

REM -- Paso 1: Verificar repositorio git --
echo [1/4] Verificando repositorio git...
git status >nul 2>&1
if %errorlevel% neq 0 (
    echo No es un repositorio git. Inicializando...
    git init
    git branch -M main
    echo OK: Repositorio inicializado.
) else (
    echo OK: Repositorio git detectado.
)
echo.

REM -- Paso 2: Configurar remote si no existe --
echo [2/4] Verificando conexion con GitHub...
git remote get-url origin >nul 2>&1
if %errorlevel% neq 0 (
    git remote add origin https://github.com/juanjosemas/proveedores.git
    echo OK: Conectado a GitHub.
) else (
    echo OK: Conectado a GitHub.
)
echo.

REM -- Paso 3: Anadir y commitear todos los archivos --
echo [3/4] Anadiendo archivos...
git add proveedores.html
git add actualizar.bat
git add subir_a_github.bat
git add generar_html.py
git add icons/
git add PROVEEDORES/
git add README.md
git add .gitignore
git commit -m "Actualizacion de presupuestos"
echo.

REM -- Paso 4: Subir a GitHub --
echo [4/4] Subiendo a GitHub...
git push -u origin main

if %errorlevel% neq 0 (
    echo.
    echo ERROR: No se pudo subir. Comprueba:
    echo   1. Que el repositorio "proveedores" existe en GitHub
    echo   2. Que tienes conexion a internet
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
