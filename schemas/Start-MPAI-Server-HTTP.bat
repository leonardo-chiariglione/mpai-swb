@echo off
setlocal

rem ===== Settings =====
set "SCHEMAS_ROOT=C:\Users\Leonardo\OneDrive - CEDEO\My Standards\mpai\schemas"
set "PORT=443"
set "CERT=devcert.pem"
set "KEY=devkey.pem"

rem ===== Ensure Node on PATH (in case the shell doesn't have it) =====
set "NODE_BIN=%ProgramFiles%\nodejs"
if exist "%NODE_BIN%\node.exe" set "PATH=%NODE_BIN%;%PATH%"

rem ===== Check folder and files =====
if not exist "%SCHEMAS_ROOT%" (
  echo [ERROR] Folder not found: "%SCHEMAS_ROOT%"
  pause
  exit /b 1
)
if not exist "%SCHEMAS_ROOT%\%CERT%" (
  echo [ERROR] Missing certificate file: "%SCHEMAS_ROOT%\%CERT%"
  echo Run mkcert first to generate devcert.pem/devkey.pem
  pause
  exit /b 1
)
if not exist "%SCHEMAS_ROOT%\%KEY%" (
  echo [ERROR] Missing key file: "%SCHEMAS_ROOT%\%KEY%"
  echo Run mkcert first to generate devcert.pem/devkey.pem
  pause
  exit /b 1
)

rem ===== Verify node/npx available =====
where node >nul 2>&1 || (
  echo [ERROR] Node.js not found in PATH.
  pause
  exit /b 1
)
if exist "%NODE_BIN%\npx.cmd" (
  set "NPX_EXE=%NODE_BIN%\npx.cmd"
) else (
  for /f "delims=" %%P in ('where npx 2^>nul') do set "NPX_EXE=%%P"
)
if not defined NPX_EXE (
  echo [ERROR] npx not found. Close and reopen your terminal after installing Node.js.
  pause
  exit /b 1
)

title MPAI Schema Server (HTTPS :%PORT%)
echo.
echo Serving local schemas over HTTPS from:
echo   "%SCHEMAS_ROOT%"
echo URL:
echo   https://schemas.mpai.community/
echo.
echo (Leave this window open. Press CTRL+C to stop.)
echo.

pushd "%SCHEMAS_ROOT%" >nul 2>&1
"%NPX_EXE%" http-server -p %PORT% -S -C "%CERT%" -K "%KEY%"
popd >nul 2>&1

echo.
echo [INFO] Server stopped.
pause
endlocal