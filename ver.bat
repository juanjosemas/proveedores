@echo off
echo.
echo ============================================
echo   ABRIR PRESUPUESTOS - PROVEEDORES
echo   Servidor local para ver PDFs
echo ============================================
echo.
echo Iniciando servidor local en puerto 8765...
echo (Cierra esta ventana para detener el servidor)
echo.

start "" http://localhost:8765/proveedores.html
python -m http.server 8765 --directory "%~dp0"
