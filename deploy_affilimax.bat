
@echo off
echo =============================================
echo   AFFILIMAX - SCRIPT DE DEPLOIEMENT RENDER
echo =============================================
echo.
echo Etape 1: Authentifier GitHub CLI
echo   gh auth login
echo.
echo Etape 2: Creer le repo et pusher
echo   cd C:/affilimax
echo   gh repo create affilimax --public --source=. --remote=origin --push
echo.
echo Etape 3: Aller sur Render.com
echo   https://dashboard.render.com
echo   New Web Service - Connecter GitHub - Selectionner affilimax
echo.
echo Etape 4: Ajouter ces variables d'environnement sur Render:
echo.
echo   ADMIN_USER      = admin
echo   ADMIN_PASSWORD  = 1d367f73204194dd8216cb8029e8afb9
echo   PARTNER_SECRET_KEY = 57272542b18811ffeb3324598858cf90b0b8399f235dba5bf7b683fb9ae64510
echo   AFFILMAX_REQUIRE_LIVE = 0
echo.
echo Etape 5: Mettre a jour SITE_URL dans social_reseaux.py
echo   Remplacer https://affilmax.render.com par ton URL Render
echo.
echo =============================================
echo   CREDENTIALS (A CONSERVER PRECIEUSEMENT)
echo =============================================
echo   Admin login   : admin / 1d367f73204194dd8216cb8029e8afb9
echo   Partner key   : 57272542b18811ffeb3324598858cf90b0b8399f235dba5bf7b683fb9ae64510
echo =============================================
pause
