#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Affilimax - UptimeRobot Setup Assistant
=======================================
Configure la surveillance 24/7 de ton site Affilimax avec UptimeRobot (gratuit).

UptimeRobot Free Tier:
  - 50 monitors
  - Checks toutes les 5 minutes
  - Notifications Email, Slack, Telegram, Discord, SMS
  - Keyword monitoring (verifie que le site renvoie bien du contenu)

Utilisation:
    python uptimerobot_setup.py              # Guide interactif
    python uptimerobot_setup.py --url URL    # Setup rapide avec une URL
    python uptimerobot_setup.py --status     # Verifier les monitors existants
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()

# ==================== GUIDE SETUP ====================

def print_header():
    print("""
╔══════════════════════════════════════════════════════╗
║         🔍 AFFILIMAX — UPTIMEROBOT SETUP            ║
║     Surveillance 24/7 gratuite de ton site          ║
╚══════════════════════════════════════════════════════╝
""")

def get_site_url():
    """Detecte ou demande l'URL du site."""
    # Render deploye ?
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "")
    if render_url:
        return render_url

    # Local
    port = os.environ.get("PORT", "8765")
    return f"http://localhost:{port}"


def generate_setup_guide(site_url):
    """Genere le guide de setup UptimeRobot complet."""

    healthz_url = f"{site_url.rstrip('/')}/healthz"
    keyword_url = f"{healthz_url}?keyword=Affilimax"

    guide = f"""
╔══════════════════════════════════════════════════════╗
║          📋 GUIDE DE CONFIGURATION                  ║
╚══════════════════════════════════════════════════════╝

🌐 Ton site : {site_url}
🏥 Health endpoint : {healthz_url}

──────────────────────────────────────────────────────
  ÉTAPE 1 : Créer un compte UptimeRobot (GRATUIT)
──────────────────────────────────────────────────────
  1. Va sur https://uptimerobot.com
  2. Clique "Start Monitoring" → "Sign Up Free"
  3. Inscris-toi avec ton email ou Google

──────────────────────────────────────────────────────
  ÉTAPE 2 : Ajouter un monitor HTTP (obligatoire)
──────────────────────────────────────────────────────
  1. Dashboard UptimeRobot → "Add New Monitor"
  2. Type : HTTP(s)
  3. Friendly Name : Affilimax - Home
  4. URL : {site_url}
  5. Monitoring Interval : 5 minutes
  6. Clic "Create Monitor"

──────────────────────────────────────────────────────
  ÉTAPE 3 : Ajouter un monitor KEYWORD (recommandé)
──────────────────────────────────────────────────────
  Ce monitor verifie que le site renvoie VRAIMENT
  du contenu (pas juste un 200 OK sur une page erreur)

  1. "Add New Monitor" → Type : HTTP(s)
  2. Friendly Name : Affilimax - Health Check
  3. URL : {keyword_url}
  4. Advanced → Keyword : Affilimax
  5. Keyword Type : "Exists" (le mot doit etre present)
  6. Monitoring Interval : 5 minutes
  7. Clic "Create Monitor"

──────────────────────────────────────────────────────
  ÉTAPE 4 : Configurer les alertes
──────────────────────────────────────────────────────
  1. Menu "Alert Contacts" (colonne de gauche)
  2. Ajoute : Email, Slack, Telegram, Discord, SMS
  3. Assigne ces contacts a tes monitors

──────────────────────────────────────────────────────
  ÉTAPE 5 (OPTIONNEL) : Page de statut publique
──────────────────────────────────────────────────────
  1. Menu "Status Pages"
  2. Cree une page publique : status.affilimax.uptimerobot.com
  3. Partage le lien a tes partenaires

──────────────────────────────────────────────────────
  ✅ RÉSUMÉ DES URLS À SURVEILLER
──────────────────────────────────────────────────────
  Monitor 1 (HTTP)  : {site_url}
  Monitor 2 (KEYWORD): {keyword_url}
  Monitor 3 (API)   : {site_url}/api/stats

──────────────────────────────────────────────────────
  🔔 Bonus : Webhook UptimeRobot → Telegram/Slack
──────────────────────────────────────────────────────
  Quand ton site tombe, UptimeRobot peut appeler
  un webhook pour te notifier instantanement.

  Dans UptimeRobot > Alert Contacts > Add Webhook :
  - URL : ton webhook Slack/Discord/Telegram
  - Coche "Notify when monitor goes DOWN"
  - Coche "Notify when monitor goes UP"

──────────────────────────────────────────────────────
"""

    print(guide)


def test_health_endpoint(url):
    """Teste l'endpoint /healthz pour verifier qu'il repond correctement."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Affilimax-UptimeRobot-Setup"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
            status = resp.status
            print(f"  ✅ {url}")
            print(f"     Status HTTP : {status}")
            print(f"     Service    : {body.get('service', 'N/A')}")
            print(f"     Uptime     : {body.get('uptime_hours', 0)} heures")
            print(f"     Produits   : {body.get('checks', {}).get('products_count', 0)}")
            if body.get("checks", {}).get("ai"):
                ai = body["checks"]["ai"]
                print(f"     IA Groq    : {'✅' if ai.get('groq') else '❌'}")
                print(f"     IA Gemini  : {'✅' if ai.get('gemini') else '❌'}")
            return True
    except Exception as e:
        print(f"  ❌ {url}")
        print(f"     Erreur : {e}")
        return False


# ==================== CLI ====================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Affilimax - UptimeRobot Setup Assistant")
    parser.add_argument("--url", type=str, help="URL du site a surveiller")
    parser.add_argument("--status", action="store_true", help="Tester l'endpoint /healthz")
    args = parser.parse_args()

    print_header()

    site_url = args.url or get_site_url()
    healthz_url = f"{site_url.rstrip('/')}/healthz"

    if args.status:
        print(f"🔍 Test de l'endpoint health...\n")
        ok = test_health_endpoint(healthz_url)
        ok2 = test_health_endpoint(f"{healthz_url}?keyword=Affilimax")
        print()
        if ok and ok2:
            print("✅ Tout est OK ! Ton site est pret pour UptimeRobot.")
        else:
            print("⚠️  Verifie que le serveur tourne et reessaie.")
        sys.exit(0)

    # Guide complet
    print(f"🔍 Test rapide du health endpoint...\n")
    test_health_endpoint(healthz_url)
    test_health_endpoint(f"{healthz_url}?keyword=Affilimax")
    print()

    generate_setup_guide(site_url)

    print("💡 Prochaine etape : va sur https://uptimerobot.com")
    print("   et suis le guide ci-dessus (5 minutes max).")
    print()
    print("   Une fois configure, UptimeRobot surveillera ton site")
    print("   24/7 et t'enverra une alerte des qu'il tombe.")
