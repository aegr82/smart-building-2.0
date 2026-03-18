@echo off
setlocal enabledelayedexpansion

REM Script para crear y configurar entornos virtuales de Python
REM Uso: setup_env.bat nombre_del_entorno

REM Verificar que se proporcionó un nombre
if "%~1"=="" (
    set "ENV_NAME=.venv"
) else (
	set ENV_NAME=%~1
)

echo ============================================
echo Creando entorno virtual: %ENV_NAME%
echo ============================================

REM Crear el entorno virtual
python -m venv %ENV_NAME%

if errorlevel 1 (
    echo Error: No se pudo crear el entorno virtual
    echo Verifica que Python este instalado correctamente
    exit /b 1
)

echo.
echo Entorno creado exitosamente
echo.

REM Activar el entorno
echo Activando entorno virtual...
call %ENV_NAME%\Scripts\activate.bat

if errorlevel 1 (
    echo Error: No se pudo activar el entorno virtual
    exit /b 1
)

echo.
echo ============================================
echo Actualizando pip...
echo ============================================
echo.

REM Actualizar pip
python -m pip install --upgrade pip

echo.
echo ============================================
echo Verificando requirements.txt...
echo ============================================
echo.

REM Verificar si existe requirements.txt
if exist requirements.txt (
    echo Archivo requirements.txt encontrado
    echo Instalando dependencias...
    echo.
    pip install -r requirements.txt
    
    if errorlevel 1 (
        echo.
        echo Advertencia: Hubo errores al instalar algunas dependencias
    ) else (
        echo.
        echo Dependencias instaladas exitosamente
    )
) else (
    echo No se encontro requirements.txt en la carpeta actual
    echo Puedes crear uno y ejecutar: pip install -r requirements.txt
)

echo.
echo ============================================
echo Configuracion completada
echo ============================================
echo.
echo Entorno virtual: %ENV_NAME%
echo Estado: ACTIVADO
echo.
echo Paquetes instalados:
pip list
echo.
echo Para desactivar el entorno, ejecuta: deactivate
echo.

REM Mantener el entorno activado (no cerrar la ventana)
cmd /k
