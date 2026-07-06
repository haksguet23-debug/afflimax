@echo off
cd /d C:\affilimax
echo ===================================================
echo   AFFILIMAX - Demarrage du serveur
echo ===================================================
echo.
echo   Stats : ZERO simulation - 100%% reel
echo   Tag Amazon : confortbure07-21
echo.
echo   Dashboard  : http://localhost:8765
echo   Landing    : http://localhost:8765/pub.html
echo   Admin      : http://localhost:8765/admin.html
echo.
echo   STOP = Ctrl+C pour arreter
echo ===================================================
echo.
start "" http://localhost:8765
python server.py
