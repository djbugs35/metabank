@echo off
rem Installe metabank (Windows) : double-clic. Peut etre relance sans risque.
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
  echo Installation de uv ^(gestionnaire Python^)...
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

echo Dependances...
uv sync || goto :echec

echo Modules woob...
uv run woob config update || goto :echec

uv run woob config list 2>nul | findstr /c:"bnporc" >nul
if errorlevel 1 (
  set /p REPONSE="Declarer maintenant votre acces BNP (identifiant, mot de passe, site pp) ? [o/N] "
  if /i "%REPONSE%"=="o" uv run woob config add bnporc
) else (
  echo Acces BNP deja declare ^(backend bnporc^).
)

echo.
echo Pret. Premier inventaire : uv run python -m metabank inventaire --interactif
pause
exit /b 0

:echec
echo Echec : verifier la connexion internet.
pause
exit /b 1
