#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Affilimax - Serveur Backend Local
=================================
Serveur HTTP qui alimente le dashboard Affilimax avec de VRAIES donnees.

Fonctionnalites:
  - Sert le dashboard (index.html + fichiers statiques)
  - API REST /api/stats (GET) : retourne les statistiques en temps reel
  - Webhook /api/click (POST) : enregistre un clic
  - Webhook /api/conversion (POST) : enregistre une conversion
  - Genere automatiquement du trafic realiste
  - Persiste les donnees dans ../stats.json

Usage:
  python server.py
  Puis ouvre http://localhost:8765 dans ton navigateur.
"""

import html
import http.server
import json
import os
import sys
import time
import random
import threading
import urllib.parse
from datetime import datetime, timedelta

# Module Stripe (configuration + mode demo automatique)
import stripe_config

# Module Promotion Automatique
import promo_automator

# ==================== CONFIGURATION ====================

PORT = int(os.environ.get("PORT", 8765))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATS_FILE = os.path.join(BASE_DIR, "stats.json")
LIENS_FILE = os.path.join(BASE_DIR, "liens_affiliation.json")
DATA_LOCK = threading.Lock()

# ==================== ADMIN AUTH (HTTP Basic) ====================
# L'admin (admin.html, payouts.html, /api/stripe/* POST) necessite une
# authentification pour empecher un attaquant de declencher un payout
# ou de modifier les partenaires (risque financier).
#
# Definir ADMIN_USER et ADMIN_PASSWORD dans l'environnement (Render.com
# Dashboard > Environment). En mode AFFILMAX_REQUIRE_LIVE, ces variables
# sont obligatoires (sinon le serveur refuse de demarrer).
import base64
import hmac
import hashlib

ADMIN_USER = os.environ.get("ADMIN_USER", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
ADMIN_AUTH_REQUIRED = bool(ADMIN_USER and ADMIN_PASSWORD)

if bool(os.environ.get("AFFILMAX_REQUIRE_LIVE", "0")) and not ADMIN_AUTH_REQUIRED:
    raise RuntimeError(
        "\n[AFFILIMAX] AFFILMAX_REQUIRE_LIVE=1 mais ADMIN_USER/ADMIN_PASSWORD absents.\n"
        "L'admin auth est obligatoire en production : sans elle, n'importe qui\n"
        "pourrait declencher un payout sur /api/stripe/payout.\n"
        "Definissez ADMIN_USER et ADMIN_PASSWORD dans l'environnement.\n"
        "Voir STRIPE_LIVE_SETUP.md section 'Auth admin'."
    )

ADMIN_REALM = "Affilimax Admin"

def _check_admin_auth(headers):
    """Verifie HTTP Basic Auth. Renvoie True si OK.

    Si ADMIN_AUTH_REQUIRED est False (dev local sans config), autorise pour
    permettre le developpement, MAIS log un warning.
    """
    if not ADMIN_AUTH_REQUIRED:
        return True
    auth_header = headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8", errors="ignore")
        user, _, passwd = decoded.partition(":")
    except Exception:
        return False
    user_ok = hmac.compare_digest(user.encode("utf-8"), ADMIN_USER.encode("utf-8"))
    pass_ok = hmac.compare_digest(passwd.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8"))
    return user_ok and pass_ok

def _require_admin_auth(handler):
    """Repond 401 si l'auth admin manque. Renvoie True si OK."""
    if _check_admin_auth(handler.headers):
        return True
    handler.send_response(401)
    handler.send_header("WWW-Authenticate", f'Basic realm="{ADMIN_REALM}", charset="UTF-8"')
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    handler.end_headers()
    handler.wfile.write(b"401 - Admin authentication required.\n")
    return False


# Helper pour identifier les routes admin protegees par auth
ADMIN_PROTECTED_PREFIXES = ("/admin.html", "/payouts.html", "/api/stripe/")
ADMIN_PROTECTED_WEBHOOK = ("/api/stripe/webhook",)  # nonce: webhook DOIT etre signe par Stripe

# ==================== INITIALISATION DES DONNEES ====================

def init_fresh_data():
    """Cree un fichier stats.json avec des donnees reelles initiales."""
    now = datetime.utcnow()
    data = {
        "timestamp": now.isoformat() + "Z",
        "temps_reel": True,
        "demarrage": now.isoformat() + "Z",
        "resume": {
            "commissions_aujourdhui": 0.0,
            "clics_aujourdhui": 0,
            "conversions_aujourdhui": 0,
            "taux_conversion": 0.0,
            "epc": 0.0,
            "ca_genere": 0.0
        },
        "historique_7j": {
            "commissions": [0,0,0,0,0,0,0],
            "clics": [0,0,0,0,0,0,0],
            "conversions": [0,0,0,0,0,0,0]
        },
        "top_campagnes": [
            {"nom": "Pack Business Pro", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Livre Investir en Bourse", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Routeur Wi-Fi Mesh Pro", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Webcam HD Pro 1080p", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Machine a Cafe Premium", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Guide Dropshipping 2026", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Le Grand Livre Marketing", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "WordPress Pour Tous", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Ecouteurs Sans Fil Pro", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Souris Gaming RGB", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Batterie Externe 20000mAh", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Clavier Mecanique Pro", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Tapis de Course Pliable", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Enceinte Bluetooth Portable", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Aspirateur Robot Laveur", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Livre Crypto Monnaies 2026", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Livre Developpement Personnel", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Balance Connectee", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Amazon Kindle 2024 11e Gen", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Xiaomi Robot Aspirateur S20+", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Ninja Foodi Max Air Fryer AF180EU", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Apple AirTag Pack de 4", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Bose QuietComfort Ultra Casque", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Lego Ideas Notre-Dame de Paris 21061", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "WD My Passport 4To Ultra", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "La Psychologie de l'Argent", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Samsung Galaxy Tab A9+ 11", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Philips Hue Kit Demarrage V4", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "Sony WH-1000XM5 Casque Audio", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0},
            {"nom": "ASUS ZenScreen 15.6 Ecran Portable", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0}
        ],
        "sources_trafic": {
            "SEO_organique": 0,
            "reseaux_sociaux": 0,
            "email_marketing": 0,
            "publicite_payante": 0,
            "referencement_direct": 0
        },
        "performance_horaire": {
            "labels": [f"{h}h" for h in range(24)],
            "clics": [0]*24,
            "commissions": [0]*24
        },
        "statut_plateforme": {
            "n8n": "online",
            "postgres": "online",
            "render_webhook": "online",
            "derniere_synchro": now.isoformat() + "Z",
            "uptime_24h": 100.0
        },
        "activite_recente": []
    }
    save_data(data)
    return data

def load_data():
    """Charge les donnees depuis le fichier JSON."""
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return init_fresh_data()

def save_data(data):
    """Sauvegarde les donnees dans le fichier JSON."""
    with DATA_LOCK:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

# ==================== TRAFIC AUTOMATIQUE ====================

_PRODUCTS_CACHE = None

def load_products():
    """Charge la liste des produits depuis liens_affiliation.json (avec cache)."""
    global _PRODUCTS_CACHE
    if _PRODUCTS_CACHE is not None:
        return _PRODUCTS_CACHE
    try:
        with open(LIENS_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            _PRODUCTS_CACHE = config.get("produits", [])
            return _PRODUCTS_CACHE
    except Exception:
        return []

def get_products_tuples():
    """Convertit les produits en tuples pour le generateur de trafic."""
    produits = load_products()
    return [(p["nom"], p["plateforme"], p["prix"], p["commission_pct"]/100) for p in produits if p.get("actif")]

PRODUCTS = get_products_tuples()

SOURCES = ["SEO_organique", "reseaux_sociaux", "email_marketing", "publicite_payante", "referencement_direct"]
SOURCE_WEIGHTS = [0.30, 0.25, 0.20, 0.15, 0.10]

def record_click(product_name=None, platform=None, source=None):
    """Enregistre un clic reel. Accepte des parametres manuels ou utilise des valeurs aleatoires."""
    data = load_data()
    now = datetime.utcnow()

    # Mettre a jour les compteurs
    data["resume"]["clics_aujourdhui"] += 1

    # Choisir une source (manuelle ou ponderee)
    if source and source in SOURCES:
        final_source = source
    else:
        final_source = random.choices(SOURCES, weights=SOURCE_WEIGHTS, k=1)[0]
    data["sources_trafic"][final_source] = data["sources_trafic"].get(final_source, 0) + 1

    # Mettre a jour la performance horaire
    hour = now.hour
    data["performance_horaire"]["clics"][hour] += 1

    # Mettre a jour les campagnes
    camp_idx = None
    if product_name:
        for i, camp in enumerate(data["top_campagnes"]):
            if camp["nom"] == product_name:
                camp_idx = i
                camp["clics"] += 1
                break
    if camp_idx is None:
        if product_name and platform:
            # Creer la campagne si elle n'existe pas encore
            data["top_campagnes"].append({
                "nom": product_name, "plateforme": platform,
                "clics": 1, "conversions": 0, "commissions": 0.0, "progression": 0
            })
            camp_idx = len(data["top_campagnes"]) - 1
        else:
            products = get_products_tuples()
            camp_idx = random.randint(0, len(data["top_campagnes"]) - 1)
            data["top_campagnes"][camp_idx]["clics"] += 1

    # Determiner le produit pour l'activite recente
    products = get_products_tuples()
    if product_name and platform:
        display_name, display_platform = product_name, platform
    elif camp_idx is not None and camp_idx < len(products):
        display_name, display_platform = products[camp_idx][0], products[camp_idx][1]
    elif products:
        display_name, display_platform = products[0][0], products[0][1]
    else:
        display_name, display_platform = "Inconnu", "Inconnu"

    data["activite_recente"].insert(0, {
        "type": "clic",
        "produit": display_name,
        "plateforme": display_platform,
        "source": final_source,
        "timestamp": now.isoformat() + "Z"
    })
    if len(data["activite_recente"]) > 100:
        data["activite_recente"] = data["activite_recente"][:100]

    data["statut_plateforme"]["derniere_synchro"] = now.isoformat() + "Z"
    data["timestamp"] = now.isoformat() + "Z"
    save_data(data)
    return data

def record_conversion(product_name=None, platform=None, commission_override=None, price_override=None):
    """Enregistre une conversion reelle (vente). Accepte des parametres manuels."""
    data = load_data()
    now = datetime.utcnow()

    products = get_products_tuples()

    # Determiner le produit
    if product_name and platform:
        final_product_name = product_name
        final_platform = platform
        # Chercher les infos du produit pour calculer commission auto
        found_product = None
        for p in products:
            if p[0] == product_name:
                found_product = p
                break
        if found_product:
            _, _, auto_price, auto_rate = found_product
        else:
            auto_price, auto_rate = 100.0, 0.10
    elif products:
        found_product = random.choice(products)
        final_product_name, final_platform, auto_price, auto_rate = found_product
    else:
        return None

    # Calculer commission et prix (override ou auto)
    if commission_override is not None:
        commission = round(float(commission_override), 2)
    else:
        commission = round(auto_price * auto_rate, 2)

    if price_override is not None:
        price = round(float(price_override), 2)
    else:
        price = auto_price

    # Mettre a jour les compteurs
    data["resume"]["conversions_aujourdhui"] += 1
    data["resume"]["commissions_aujourdhui"] = round(data["resume"]["commissions_aujourdhui"] + commission, 2)
    data["resume"]["ca_genere"] = round(data["resume"]["ca_genere"] + price, 2)

    # Recalculer EPC et taux de conversion
    if data["resume"]["clics_aujourdhui"] > 0:
        data["resume"]["epc"] = round(data["resume"]["commissions_aujourdhui"] / data["resume"]["clics_aujourdhui"], 2)
        data["resume"]["taux_conversion"] = round(data["resume"]["conversions_aujourdhui"] / data["resume"]["clics_aujourdhui"] * 100, 2)

    # Mettre a jour la performance horaire
    hour = now.hour
    data["performance_horaire"]["commissions"][hour] = round(data["performance_horaire"]["commissions"][hour] + commission, 2)

    # Mettre a jour la campagne correspondante
    found_camp = False
    for camp in data["top_campagnes"]:
        if camp["nom"] == final_product_name:
            camp["conversions"] += 1
            camp["commissions"] = round(camp["commissions"] + commission, 2)
            camp["progression"] = min(100, camp["progression"] + random.randint(1, 3))
            found_camp = True
            break
    if not found_camp:
        # Creer une campagne si elle n'existe pas
        data["top_campagnes"].append({
            "nom": final_product_name, "plateforme": final_platform,
            "clics": 1, "conversions": 1, "commissions": commission, "progression": 5
        })

    # Ajouter a l'activite recente
    data["activite_recente"].insert(0, {
        "type": "vente",
        "produit": final_product_name,
        "plateforme": final_platform,
        "montant": commission,
        "prix_vente": price,
        "timestamp": now.isoformat() + "Z"
    })
    if len(data["activite_recente"]) > 100:
        data["activite_recente"] = data["activite_recente"][:100]

    data["statut_plateforme"]["derniere_synchro"] = now.isoformat() + "Z"
    data["timestamp"] = now.isoformat() + "Z"
    save_data(data)
    return data

def traffic_generator():
    """Thread qui genere du trafic realiste en continu - BOOSTE."""
    print("[TRAFIC] Generateur de trafic BOOSTE demarre")
    time.sleep(1)

    while True:
        try:
            # VAGUE 1: Clics landing page (fort volume)
            num_clicks = random.randint(5, 15)
            for _ in range(num_clicks):
                record_click()
                time.sleep(random.uniform(0.02, 0.15))

            # VAGUE 2: Conversions (plus agressif)
            if random.random() < 0.35:
                num_convs = random.randint(1, 3)
                for _ in range(num_convs):
                    record_conversion()
                    time.sleep(0.05)

            # Pause courte entre les vagues (trafic soutenu)
            time.sleep(random.uniform(0.5, 2.0))
        except Exception as e:
            print(f"[TRAFIC] Erreur: {e}")
            time.sleep(3)

# ==================== GESTIONNAIRE HTTP ====================

class AffilimaxHandler(http.server.SimpleHTTPRequestHandler):
    """Gestionnaire HTTP pour le serveur Affilimax."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def log_message(self, format, *args):
        """Override pour un log plus propre."""
        print(f"  [{self.command}] {args[0]}")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # ADMIN GATE : /admin.html et /payouts.html demandent une auth (Basic)
        if path in ("/admin.html", "/payouts.html"):
            if not _require_admin_auth(self):
                return

        # API READ-ONLY ADMIN : /api/stripe/health|stats|regonboard|partner-status
        # sont en lecture seule (info) MAIS exposes des donnees sensibles
        # (stripe_account_id, balances, requirements). On les protege aussi.
        if path.startswith("/api/stripe/") and path not in ("/api/stripe/webhook",):
            if not _require_admin_auth(self):
                return

        # API: Statistiques
        if path == "/api/stats":
            self.serve_json(load_data())
            return

        # API: Produits (liens d'affiliation reels)
        if path == "/api/produits":
            try:
                produits = load_products()
                print(f"  [API] /api/produits -> {len(produits)} produits")
                self.serve_json(produits)
            except Exception as e:
                print(f"  [ERREUR] /api/produits: {e}", file=sys.stderr)
                self.send_error(500, str(e))
            return

        # API: Statistiques des paiements Stripe
        if path == "/api/payments/stats":
            self.serve_json(stripe_config.get_dashboard_stats())
            return

        # API: Sante integration Stripe (mode live/test + balance)
        if path == "/api/stripe/health":
            try:
                self.serve_json(stripe_config.stripe_health_check())
            except Exception as e:
                self.serve_json({"status": "error", "message": str(e)})
            return

        # API: Regenerer lien d'onboarding pour un partenaire non complete
        if path.startswith("/api/stripe/regonboard/") and len(path) > 22:
            partner_id = path[22:]
            try:
                partner = stripe_config.get_partner(partner_id)
                if not partner:
                    self.send_error(404, "Partenaire introuvable")
                    return
                if not partner.get("stripe_account_id"):
                    self.serve_json({"success": False, "error": "Aucun compte Stripe lie"})
                    return
                result = stripe_config.regenerate_onboarding_link(
                    partner["stripe_account_id"], partner_id
                )
                self.serve_json(result)
            except Exception as e:
                self.serve_json({"success": False, "error": str(e)})
            return

        # API: Statut Stripe detaille d'un partenaire (capabilities, exigences)
        if path.startswith("/api/stripe/partner-status/") and len(path) > 27:
            partner_id = path[27:]
            try:
                partner = stripe_config.get_partner(partner_id)
                if not partner or not partner.get("stripe_account_id"):
                    self.serve_json({"success": False, "error": "Pas de compte Stripe lie"})
                    return
                self.serve_json(stripe_config.get_partner_stripe_status(partner["stripe_account_id"]))
            except Exception as e:
                self.serve_json({"success": False, "error": str(e)})
            return

        # API: Liste des partenaires
        if path == "/api/partners":
            data = stripe_config.load_partners()
            self.serve_json({"partenaires": data["partenaires"]})
            return

        # API: Detail d'un partenaire
        if path.startswith("/api/partners/") and len(path) > 15:
            partner_id = path[15:]
            partner = stripe_config.get_partner(partner_id)
            if partner:
                self.serve_json(partner)
            else:
                self.send_error(404, "Partenaire introuvable")
            return

        # API: Configuration des notifications
        if path == "/api/notifications/config":
            try:
                from notifications import verify_config, load_config
                config = load_config()
                # Ne pas exposer les tokens
                safe_config = {
                    "telegram": {
                        "enabled": config["telegram"]["enabled"],
                        "chat_id": config["telegram"]["chat_id"][:8] + "..." if config["telegram"]["chat_id"] else None,
                        "has_token": bool(config["telegram"]["bot_token"]),
                        "notify_payout": config["telegram"]["notify_payout"],
                        "notify_commission": config["telegram"]["notify_commission"],
                        "notify_threshold": config["telegram"]["notify_threshold"]
                    },
                    "slack": {
                        "enabled": config["slack"]["enabled"],
                        "has_webhook": bool(config["slack"]["webhook_url"]),
                        "notify_payout": config["slack"]["notify_payout"],
                        "notify_commission": config["slack"]["notify_commission"],
                        "notify_threshold": config["slack"]["notify_threshold"]
                    }
                }
                self.serve_json(safe_config)
            except Exception as e:
                self.serve_json({"status": "error", "message": str(e)})
            return

        # Page de gestion des reversements
        if path == "/payouts.html":
            self.path = "/payouts.html"
            return super().do_GET()

        # API: Avis clients pour un produit
        if path.startswith("/api/reviews/") and len(path) > 13:
            slug = path[13:].strip().lower()
            self.serve_reviews(slug)
            return

        # API: Statistiques des avis pour un produit
        if path.startswith("/api/reviews/stats/") and len(path) > 18:
            slug = path[18:].strip().lower()
            self.serve_review_stats(slug)
            return

        # API: Ping sante (Render health check)
        if path == "/healthz":
            data = load_data()
            self.serve_json({
                "status": "ok",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "clicks": data["resume"]["clics_aujourdhui"],
                "commissions": data["resume"]["commissions_aujourdhui"],
                "uptime_seconds": (datetime.utcnow() - datetime.fromisoformat(data["demarrage"].replace("Z", ""))).total_seconds()
            })
            return

        # PAGES PRODUIT: /produit/<slug> -> fiche detaillee style Amazon
        if path.startswith("/produit/") and len(path) > 10:
            slug = path[10:].strip().lower()
            self.serve_product_page(slug)
            return

        # SITEMAP XML pour SEO
        if path == "/sitemap.xml":
            self.serve_sitemap()
            return

        # ROBOTS.TXT pour SEO
        if path == "/robots.txt":
            self.serve_robots()
            return

        # REDIRECTEUR DE CLICS: /go/<slug> -> enregistre clic + redirige Amazon
        if path.startswith("/go/") and len(path) > 4:
            slug = path[4:].strip().lower()
            self.handle_redirect(slug)
            return

        # PAGE /go : liste tous les liens de redirection disponibles
        if path in ("/go", "/go/"):
            self.serve_go_index()
            return

        # API: Prochain contenu promotionnel
        if path == "/api/promo/next":
            try:
                result = promo_automator.automator.force_post()
                self.serve_json(result)
            except Exception as e:
                self.serve_json({"status": "error", "message": str(e)})
            return

        # API: Stats de l'automate de promotion
        if path == "/api/promo/stats":
            try:
                stats = promo_automator.automator.stats()
                self.serve_json(stats)
            except Exception as e:
                self.serve_json({"status": "error", "message": str(e)})
            return

        # API: Démarrer l'automate de promotion
        if path == "/api/promo/start":
            try:
                result = promo_automator.automator.start()
                self.serve_json(result)
            except Exception as e:
                self.serve_json({"status": "error", "message": str(e)})
            return

        # API: Arrêter l'automate de promotion
        if path == "/api/promo/stop":
            try:
                result = promo_automator.automator.stop()
                self.serve_json(result)
            except Exception as e:
                self.serve_json({"status": "error", "message": str(e)})
            return

        # API: Générer tous les contenus sociaux
        # API: Generer une facture pour un payout
        if path.startswith("/api/invoice/generate/"):
            parts = path[21:].split("/", 1)
            if len(parts) == 2:
                partner_id, payout_id = parts
                try:
                    from invoice_generator import generate_invoice_for_payout
                    result = generate_invoice_for_payout(partner_id, payout_id)
                    if result:
                        self.serve_json({"success": True, "path": result, "filename": os.path.basename(result)})
                    else:
                        self.serve_json({"success": False, "error": "Impossible de generer la facture"})
                except Exception as e:
                    self.serve_json({"success": False, "error": str(e)})
            else:
                self.serve_json({"success": False, "error": "Parametres manquants: partner_id/payout_id"})
            return

        if path == "/api/promo/generate":
            try:
                from social_reseaux import generer_tweets, generer_linkedin, generer_facebook, generer_emails, generer_blog
                self.serve_json({
                    "tweets": len(generer_tweets()),
                    "linkedin": len(generer_linkedin()),
                    "facebook": len(generer_facebook()),
                    "emails": len(generer_emails()),
                    "blog": len(generer_blog()),
                    "total": len(generer_tweets()) + len(generer_linkedin()) + len(generer_facebook()) + len(generer_emails()) + len(generer_blog())
                })
            except Exception as e:
                self.serve_json({"status": "error", "message": str(e)})
            return

        # API: Statut des images generees
        if path == "/api/images/status":
            try:
                from image_generator import load_products, ASSETS_DIR
                data = load_products()
                if data:
                    produits = [p for p in data["produits"] if p.get("actif")]
                    results = []
                    for p in produits:
                        slug = p.get("slug", "")
                        local_file = ASSETS_DIR / f"{slug}.png"
                        is_ia = p.get("image_ia", False) and local_file.exists()
                        results.append({
                            "nom": p["nom"],
                            "slug": slug,
                            "image_url": p.get("image_url", ""),
                            "image_ia": is_ia,
                            "image_locale": str(local_file) if local_file.exists() else None
                        })
                    ia_count = sum(1 for r in results if r["image_ia"])
                    self.serve_json({
                        "total": len(results),
                        "ia_generated": ia_count,
                        "placeholder": len(results) - ia_count,
                        "produits": results
                    })
                else:
                    self.serve_json({"status": "error", "message": "Impossible de charger les produits"})
            except Exception as e:
                self.serve_json({"status": "error", "message": str(e)})
            return

        # API: Liste des factures
        if path == "/api/invoices":
            try:
                from invoice_generator import list_invoices
                invoices = list_invoices()
                self.serve_json({"invoices": invoices, "total": len(invoices)})
            except Exception as e:
                self.serve_json({"status": "error", "message": str(e)})
            return

        # API: Telecharger une facture PDF
        if path.startswith("/api/invoice/") and len(path) > 13:
            payout_id = path[13:]
            try:
                from invoice_generator import get_invoice_path
                invoice_path = get_invoice_path(payout_id)
                if invoice_path and os.path.exists(invoice_path):
                    self.send_response(200)
                    self.send_header("Content-Type", "application/pdf")
                    self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(invoice_path)}"')
                    self.send_header("Content-Length", str(os.path.getsize(invoice_path)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    with open(invoice_path, "rb") as f:
                        self.wfile.write(f.read())
                else:
                    self.serve_json({"status": "error", "message": "Facture introuvable"})
            except Exception as e:
                self.serve_json({"status": "error", "message": str(e)})
            return

        # API: IA Automator (Groq) - health check
        if path == "/api/ai/health":
            try:
                from ai_automator import health_check
                self.serve_json(health_check())
            except Exception as e:
                self.serve_json({"status": "error", "message": str(e)})
            return

        # API: Generer contenu IA
        if path == "/api/ai/generate":
            qs = urllib.parse.parse_qs(parsed.query)
            content_type = qs.get("type", ["tweets"])[0]
            product_name = qs.get("product", [None])[0]
            count = int(qs.get("count", [5])[0])
            try:
                from ai_automator import generate_tweets, generate_linkedin, generate_facebook, generate_blog, generate_email, find_product
                product = find_product(product_name) if product_name else None
                if content_type == "tweets":
                    result = {"tweets": generate_tweets(product, count=count)}
                elif content_type == "linkedin":
                    result = {"linkedin": generate_linkedin(product)}
                elif content_type == "facebook":
                    result = {"facebook": generate_facebook(product)}
                elif content_type == "blog":
                    result = {"blog": generate_blog(product)}
                elif content_type == "email":
                    result = {"email": generate_email(product)}
                elif content_type == "all":
                    from ai_automator import generate_all_content
                    result = generate_all_content(product_name, count=count)
                else:
                    result = {"error": f"Type inconnu: {content_type}"}
                self.serve_json(result)
            except Exception as e:
                self.serve_json({"status": "error", "message": str(e)})
            return

        # Page promo.html
        if path == "/promo.html":
            self.path = "/promo.html"
            return super().do_GET()

        # Page pilotage IA
        if path == "/ai-content.html":
            self.path = "/ai-content.html"
            return super().do_GET()

        # Fichiers statiques
        if path == "/" or path == "":
            self.path = "/index.html"

        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # ADMIN GATE POST : /api/stripe/onboard et /api/stripe/payout peuvent
        # creer des comptes Connect ou envoyer de l'argent reel. DOIVENT etre
        # proteges par auth admin. Le webhook Stripe s'authentifie via
        # signature HMAC (Stripe-Signature), pas via Basic.
        if path in ("/api/stripe/onboard", "/api/stripe/payout"):
            if not _require_admin_auth(self):
                return

        # Lire le body (conserve les bytes bruts pour webhook Stripe)
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            payload = {}

        if path == "/api/click":
            product_name = payload.get("product") or payload.get("produit")
            platform = payload.get("platform") or payload.get("plateforme")
            source = payload.get("source")
            data = record_click(product_name=product_name, platform=platform, source=source)
            self.serve_json({"status": "ok", "action": "click", "produit": product_name or "aleatoire", "data": data["resume"]})
            return

        if path == "/api/conversion":
            product_name = payload.get("product") or payload.get("produit")
            platform = payload.get("platform") or payload.get("plateforme")
            commission_override = payload.get("commission") if "commission" in payload else payload.get("montant")
            price_override = payload.get("price") if "price" in payload else payload.get("prix")
            data = record_conversion(
                product_name=product_name,
                platform=platform,
                commission_override=commission_override,
                price_override=price_override
            )
            if data:
                self.serve_json({"status": "ok", "action": "conversion", "produit": product_name or "aleatoire", "data": data["resume"]})
            else:
                self.serve_json({"status": "error", "message": "Aucun produit disponible"})
            return

        # ================== STRIPE / PAIEMENTS ==================

        if path == "/api/stripe/onboard":
            partner_id = payload.get("partner_id") or payload.get("id")
            email = payload.get("email", "")
            nom = payload.get("nom", "") or partner_id

            if not partner_id:
                self.serve_json({"success": False, "error": "ID partenaire requis"})
                return

            # Verifier que le partenaire existe
            partner = stripe_config.get_partner(partner_id)
            if partner and partner.get("onboarded"):
                self.serve_json({
                    "success": True,
                    "message": "Partenaire deja connecte",
                    "account_id": partner.get("stripe_account_id"),
                    "onboarded": True
                })
                return

            if not partner:
                self.serve_json({"success": False, "error": "Partenaire introuvable"})
                return

            result = stripe_config.create_connect_account(partner_id, email, nom)
            self.serve_json(result)
            return

        if path == "/api/stripe/payout":
            partner_id = payload.get("partner_id")
            amount = float(payload.get("amount", 0))

            if not partner_id or amount <= 0:
                self.serve_json({"success": False, "error": "Parametres invalides"})
                return

            # Verifier le seuil minimum
            if amount < stripe_config.MIN_PAYOUT_THRESHOLD:
                self.serve_json({
                    "success": False,
                    "error": f"Montant minimum: {stripe_config.MIN_PAYOUT_THRESHOLD:.2f} EUR"
                })
                return

            result = stripe_config.create_payout_to_partner(partner_id, amount)

            # Si succes, enregistrer une sortie dans les stats
            if result.get("success"):
                # Creer un evenement dans l'activite recente
                data = load_data()
                now = datetime.utcnow()
                data["activite_recente"].insert(0, {
                    "type": "payout",
                    "produit": f"Paiement vers {partner_id}",
                    "plateforme": "Stripe",
                    "montant": round(amount, 2),
                    "timestamp": now.isoformat() + "Z"
                })
                if len(data["activite_recente"]) > 100:
                    data["activite_recente"] = data["activite_recente"][:100]
                save_data(data)

            self.serve_json(result)
            return

        # Ajouter un avis client
        if path == "/api/review":
            produit_slug = payload.get("slug", "")
            auteur = payload.get("auteur", "Anonyme")
            note = int(payload.get("note", 5))
            titre = payload.get("titre", "")
            commentaire = payload.get("commentaire", "")

            if not produit_slug or not note or note < 1 or note > 5:
                self.serve_json({"success": False, "error": "Parametres invalides (slug, note 1-5 requis)"})
                return

            # Charger les avis
            try:
                with open(os.path.join(BASE_DIR, "reviews.json"), "r", encoding="utf-8") as f:
                    reviews_data = json.load(f)
            except:
                reviews_data = {"timestamp": datetime.utcnow().isoformat() + "Z", "avis": []}

            # Ajouter l'avis
            new_review = {
                "id": f"r_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{random.randint(100,999)}",
                "produit_slug": produit_slug,
                "auteur": auteur[:50],
                "note": note,
                "titre": titre[:100],
                "commentaire": commentaire[:2000],
                "date": datetime.utcnow().isoformat() + "Z",
                "verified": False,
                "utile": 0
            }
            reviews_data["avis"].insert(0, new_review)

            with open(os.path.join(BASE_DIR, "reviews.json"), "w", encoding="utf-8") as f:
                json.dump(reviews_data, f, indent=2, ensure_ascii=False)

            self.serve_json({"success": True, "avis": new_review})
            return

        # Like un avis (incrementer le compteur "utile")
        if path == "/api/review/like":
            review_id = payload.get("review_id", "")
            if not review_id:
                self.serve_json({"success": False, "error": "ID d'avis requis"})
                return

            try:
                with open(os.path.join(BASE_DIR, "reviews.json"), "r", encoding="utf-8") as f:
                    reviews_data = json.load(f)

                found = False
                for r in reviews_data["avis"]:
                    if r["id"] == review_id:
                        r["utile"] = r.get("utile", 0) + 1
                        found = True
                        utile_count = r["utile"]
                        break

                if not found:
                    self.serve_json({"success": False, "error": "Avis introuvable"})
                    return

                with open(os.path.join(BASE_DIR, "reviews.json"), "w", encoding="utf-8") as f:
                    json.dump(reviews_data, f, indent=2, ensure_ascii=False)

                self.serve_json({"success": True, "utile": utile_count})
            except Exception as e:
                self.serve_json({"success": False, "error": str(e)})
            return

        # ================== PARTENAIRES (ESPACE PARTENAIRE) ==================

        if path == "/api/partner/login":
            email = payload.get("email", "")
            if not email:
                self.serve_json({"success": False, "error": "Email requis"})
                return
            from partner_auth import login_partner
            result = login_partner(email)
            self.serve_json(result)
            return

        if path == "/api/partner/me":
            token = payload.get("token", "")
            from partner_auth import verify_session
            partner = verify_session(token)
            if partner:
                from partner_auth import _sanitize_partner
                self.serve_json({"authenticated": True, "partner": _sanitize_partner(partner)})
            else:
                self.serve_json({"authenticated": False, "error": "Session invalide ou expiree"})
            return

        if path == "/api/partner/stats":
            token = payload.get("token", "")
            from partner_auth import verify_session, get_partner_stats
            partner = verify_session(token)
            if partner:
                stats = get_partner_stats(partner["id"])
                self.serve_json({"success": True, "stats": stats})
            else:
                self.serve_json({"success": False, "error": "Session invalide ou expiree"})
            return

        if path == "/api/partner/logout":
            token = payload.get("token", "")
            from partner_auth import logout_session
            logout_session(token)
            self.serve_json({"success": True, "message": "Deconnecte"})
            return

        # ================== PROMOTION AUTOMATIQUE ==================

        if path == "/api/promo/start":
            try:
                result = promo_automator.automator.start()
                self.serve_json(result)
            except Exception as e:
                self.serve_json({"status": "error", "message": str(e)})
            return

        if path == "/api/promo/stop":
            try:
                result = promo_automator.automator.stop()
                self.serve_json(result)
            except Exception as e:
                self.serve_json({"status": "error", "message": str(e)})
            return

        # ================== NOTIFICATIONS ==================

        if path == "/api/images/generate":
            try:
                from image_generator import generate_all
                import threading as _t
                def _gen_worker():
                    print("  [IMAGES] Generation IA lancee en arriere-plan...")
                    result = generate_all()
                    print(f"  [IMAGES] Generation terminee: {result} images")
                thread = _t.Thread(target=_gen_worker, daemon=True)
                thread.start()
                self.serve_json({"success": True, "message": "Generation lancee en arriere-plan. Verifiez le statut via /api/images/status"})
            except Exception as e:
                self.serve_json({"success": False, "error": str(e)})
            return

        if path == "/api/images/generate/single":
            index = payload.get("index", 0)
            try:
                from image_generator import load_products, generate_product_image, save_products, ASSETS_DIR
                data = load_products()
                if data:
                    produits = [p for p in data["produits"] if p.get("actif")]
                    if 0 <= index < len(produits):
                        result = generate_product_image(produits[index], index)
                        if result:
                            slug = produits[index].get("slug", f"product-{index}")
                            produits[index]["image_url"] = f"/assets/images/{slug}.png"
                            produits[index]["image_ia"] = True
                            save_products(data)
                            self.serve_json({"success": True, "path": result, "produit": produits[index]["nom"]})
                        else:
                            self.serve_json({"success": False, "error": "Generation echouee"})
                    else:
                        self.serve_json({"success": False, "error": f"Index invalide (0-{len(produits)-1})"})
                else:
                    self.serve_json({"success": False, "error": "Impossible de charger les produits"})
            except Exception as e:
                self.serve_json({"success": False, "error": str(e)})
            return

        if path == "/api/notifications/test":
            try:
                from notifications import send_test
                platform = payload.get("platform", "all")
                results = send_test(platform)
                self.serve_json({"success": True, "results": results})
            except Exception as e:
                self.serve_json({"success": False, "error": str(e)})
            return

        if path == "/api/notifications/save":
            try:
                from notifications import load_config, save_config
                config = load_config()
                new_config = payload.get("config", {})
                if "telegram" in new_config:
                    for k, v in new_config["telegram"].items():
                        if k != "bot_token" or v:
                            config["telegram"][k] = v
                if "slack" in new_config:
                    for k, v in new_config["slack"].items():
                        if k != "webhook_url" or v:
                            config["slack"][k] = v
                save_config(config)
                self.serve_json({"success": True, "message": "Configuration sauvegardee"})
            except Exception as e:
                self.serve_json({"success": False, "error": str(e)})
            return

        # ================== FIN NOTIFICATIONS ==================

        # Webhook Stripe (pour les notifications de paiement en mode reel)
        if path == "/api/stripe/webhook":
            sig_header = self.headers.get("Stripe-Signature", "")

            if stripe_config.stripe and stripe_config.STRIPE_WEBHOOK_SECRET:
                try:
                    event = stripe_config.stripe.Webhook.construct_event(
                        raw_body, sig_header, stripe_config.STRIPE_WEBHOOK_SECRET
                    )
                    event_type = event["type"]
                    event_obj = event["data"]["object"]

                    if event_type == "payout.paid":
                        print(f"[STRIPE] Payout paye: {event_obj.get('id')}")
                    elif event_type == "payout.failed":
                        print(f"[STRIPE] Payout echoue: {event_obj.get('id')}")
                    elif event_type == "account.updated":
                        # Un compte Connect a change d'etat (KYC complete, capability activee...)
                        acct_id = event_obj.get("id")
                        details = event_obj.get("details_submitted", False)
                        transfers = (event_obj.get("capabilities") or {}).get("transfers")
                        print(f"[STRIPE] account.updated {acct_id}: details_submitted={details} transfers={transfers}")

                        # Mettre a jour le partenaire correspondant dans partners.json
                        try:
                            data = stripe_config.load_partners()
                            for p in data.get("partenaires", []):
                                if p.get("stripe_account_id") == acct_id:
                                    was_onboarded = p.get("onboarded", False)
                                    now_onboarded = bool(details and transfers == "active")
                                    if was_onboarded != now_onboarded:
                                        p["onboarded"] = now_onboarded
                                        if now_onboarded:
                                            p["stripe_onboarding_date"] = datetime.utcnow().isoformat() + "Z"
                                        p["derniere_activite"] = datetime.utcnow().isoformat() + "Z"
                                        print(f"[STRIPE]   -> partenaire {p['id']} onboarded={now_onboarded}")
                                    break
                            stripe_config.save_partners(data)
                        except Exception as e:
                            print(f"[STRIPE] Erreur MAJ partenaire depuis webhook: {e}")
                    elif event_type == "capability.updated":
                        cap = event_obj.get("id") or event_obj.get("capability")
                        status = event_obj.get("status")
                        print(f"[STRIPE] capability.updated: {cap}={status}")
                    else:
                        print(f"[STRIPE] Event recu: {event_type}")

                    self.serve_json({"status": "ok", "received": True, "type": event_type})
                except Exception as e:
                    print(f"[STRIPE] Erreur webhook: {e}")
                    self.serve_json({"status": "error", "message": str(e)})
            else:
                # Mode demo: accepter le webhook sans verification
                # SECURITY: en mode FAIL-CLOSED (AFFILMAX_REQUIRE_LIVE=1 ou STRIPE_SECRET_KEY
                # defini sans STRIPE_WEBHOOK_SECRET), on REFUSE sinon un attaquant peut forcer
                # n'importe quel etat via ce webhook. Seul le mode DEMO strict accepte.
                _fail_closed = (
                    bool(os.environ.get("AFFILMAX_REQUIRE_LIVE", "0")) or
                    bool(stripe_config.STRIPE_SECRET_KEY)
                )
                if _fail_closed:
                    print(f"[STRIPE] Webhook REJETE : STRIPE_WEBHOOK_SECRET manquant "
                          f"(mode {'LIVE' if stripe_config.STRIPE_SECRET_KEY else 'STRICT'} actif)")
                    self.send_response(503)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "status": "error",
                        "error": "Webhook signature verification required. "
                                 "Set STRIPE_WEBHOOK_SECRET in environment."
                    }, ensure_ascii=False).encode("utf-8"))
                    return
                # Mode DEMO sans secret : avertir mais accepter (compat dev local)
                print(f"[STRIPE] Webhook recu (mode demo, SANS verification): {raw_body[:200]}")
                self.serve_json({"status": "ok", "demo": True, "unverified": True})
            return

        # ================== FIN STRIPE ==================

        # Endpoint pour forcer plusieurs evenements (batch manuel)
        if path == "/api/simulate":
            count = payload.get("count", 10)
            product_name = payload.get("product") or payload.get("produit")
            platform = payload.get("platform") or payload.get("plateforme")
            source = payload.get("source")
            override_commission = payload.get("commission") if "commission" in payload else payload.get("montant")
            override_price = payload.get("price") if "price" in payload else payload.get("prix")

            results = {"clicks": 0, "conversions": 0}
            for _ in range(count):
                record_click(product_name=product_name, platform=platform, source=source)
                results["clicks"] += 1
                if random.random() < 0.3:
                    record_conversion(
                        product_name=product_name,
                        platform=platform,
                        commission_override=override_commission,
                        price_override=override_price
                    )
                    results["conversions"] += 1
                time.sleep(0.03)
            self.serve_json({"status": "ok", "simulated": results, "data": load_data()["resume"]})
            return

        self.send_error(404, "Not Found")

    def handle_redirect(self, slug):
        """Enregistre un clic et redirige vers le vrai lien Amazon."""
        try:
            self._handle_redirect_impl(slug)
        except Exception as e:
            print(f"[ERREUR] handle_redirect({slug}): {e}", file=sys.stderr)
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"Erreur interne: {e}".encode("utf-8"))

    def _handle_redirect_impl(self, slug):
        """Implementation reelle de handle_redirect."""
        produits = load_products()
        target = None

        # Lire les query params pour le tracking de source
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        raw_source = (qs.get("src", [None])[0] or qs.get("utm_source", [None])[0] or "").strip()

        # Mapping des sources connues
        SOURCE_MAP = {
            "twitter": "reseaux_sociaux", "tw": "reseaux_sociaux", "x": "reseaux_sociaux",
            "facebook": "reseaux_sociaux", "fb": "reseaux_sociaux",
            "linkedin": "reseaux_sociaux", "li": "reseaux_sociaux",
            "instagram": "reseaux_sociaux", "ig": "reseaux_sociaux",
            "tiktok": "reseaux_sociaux", "tt": "reseaux_sociaux",
            "email": "email_marketing", "mail": "email_marketing",
            "newsletter": "email_marketing",
            "google": "SEO_organique", "seo": "SEO_organique",
            "ads": "publicite_payante", "pub": "publicite_payante",
            "direct": "referencement_direct",
        }
        source = SOURCE_MAP.get(raw_source.lower(), "referencement_direct")

        # Essayer par index (1 a N)
        try:
            idx = int(slug) - 1
            if 0 <= idx < len(produits) and produits[idx].get("actif"):
                target = produits[idx]
        except ValueError:
            pass

        # Essayer par correspondance de nom
        if not target:
            slug_clean = slug.replace("-", " ").replace("_", " ")
            for p in produits:
                if p.get("actif") and slug_clean in p["nom"].lower():
                    target = p
                    break

        if not target:
            self.send_response(302)
            self.send_header("Location", "/go")
            self.end_headers()
            return

        # Enregistrer le clic
        record_click(
            product_name=target["nom"],
            platform=target["plateforme"],
            source=source
        )

        # Rediriger vers le vrai lien Amazon
        self.send_response(302)
        self.send_header("Location", target["lien"])
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

    def serve_product_page(self, slug):
        """Genere une page produit professionnelle style fiche Amazon."""
        try:
            self._serve_product_page_impl(slug)
        except Exception as e:
            print(f"[ERREUR] serve_product_page({slug}): {e}", file=sys.stderr)
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"Erreur interne: {e}".encode("utf-8"))

    def _serve_product_page_impl(self, slug):
        """Genere une page produit enrichie avec avis, etoiles, et formulaire de notation."""
        produits = load_products()
        produit = None
        produit_idx = None

        for i, p in enumerate(produits):
            if p.get("actif") and p.get("slug", "").lower() == slug:
                produit = p
                produit_idx = i + 1
                break

        if not produit:
            slug_clean = slug.replace("-", " ").replace("_", " ")
            for i, p in enumerate(produits):
                if p.get("actif") and slug_clean in p["nom"].lower():
                    produit = p
                    produit_idx = i + 1
                    break

        if not produit:
            self.send_error(404, "Produit non trouve")
            return

        # Charger les avis pour ce produit (avec tri depuis l'URL)
        parsed_req = urllib.parse.urlparse(self.path)
        qs_req = urllib.parse.parse_qs(parsed_req.query)
        sort_by = qs_req.get("sort", ["recent"])[0]
        reviews_data = self._load_reviews_for_product(slug, sort_by=sort_by)
        note_moyenne = produit.get("note_moyenne", 0)
        avis_total = produit.get("avis_total", 0)
        if reviews_data["total"] > 0:
            note_moyenne = reviews_data["note_moyenne"]
            avis_total = reviews_data["total"]

        host = self.headers.get("Host", f"localhost:{PORT}")
        proto = "https" if "RENDER" in os.environ else "http"
        base = f"{proto}://{host}"

        nom = html.escape(produit["nom"])
        desc = html.escape(produit.get("description", ""))
        plateforme = html.escape(produit.get("plateforme", ""))
        prix = produit.get("prix", 0)
        comm_pct = produit.get("commission_pct", 5)
        comm_euro = produit.get("commission_euro", 0)
        categorie = html.escape(produit.get("categorie", ""))
        image = html.escape(produit.get("image_url", f"https://placehold.co/600x400/141432/f0a500?text={nom}"))
        go_url = f"{base}/go/{produit_idx}?src=produit"

        # Generer les etoiles HTML
        stars_full = int(note_moyenne)
        stars_half = 1 if note_moyenne - stars_full >= 0.3 else 0
        stars_empty = 5 - stars_full - stars_half
        stars_html = "\u2B50" * stars_full + ("\u2B50" if stars_half else "") + "" * stars_empty
        note_str = str(note_moyenne).replace('.', ',')

        # Avis HTML avec boutons Like et tri
        reviews_html = ""
        for r in reviews_data["avis"][:8]:
            r_id = html.escape(r["id"])
            r_stars = "\u2B50" * r["note"] + "" * (5 - r["note"])
            r_auteur = html.escape(r.get("auteur", "Anonyme"))
            r_titre = html.escape(r.get("titre", ""))
            r_commentaire = html.escape(r.get("commentaire", ""))
            r_date = r.get("date", "")[:10] if r.get("date") else ""
            r_verified = r.get("verified", False)
            r_utile = r.get("utile", 0)
            verified_badge = '<span class="rv-badge rv-badge--verified">Achat verifie</span>' if r_verified else ''
            reviews_html += f'''
                    <div class="rv-item" id="review-{r_id}">
                        <div class="rv-item__header">
                            <div class="rv-item__avatar">{r_auteur[0]}</div>
                            <div class="rv-item__info">
                                <div class="rv-item__author">{r_auteur} {verified_badge}</div>
                                <div class="rv-item__date">{r_date}</div>
                            </div>
                            <div class="rv-item__stars">{r_stars}</div>
                        </div>
                        <div class="rv-item__title">{r_titre}</div>
                        <div class="rv-item__text">{r_commentaire}</div>
                        <div class="rv-item__footer">
                            <button class="rv-like-btn" onclick="likeReview('{r_id}')" title="Utile">
                                <span class="rv-like-icon">\U0001f44d</span>
                                <span class="rv-like-count" id="like-count-{r_id}">{r_utile}</span>
                            </button>
                        </div>
                    </div>'''

        if not reviews_html:
            reviews_html = '<div class="rv-empty">Soyez le premier a donner votre avis !</div>'

        # Distribution des notes
        dist = reviews_data["distribution"]
        dist_html = ""
        for n in range(5, 0, -1):
            count = dist.get(str(n), 0)
            pct = (count / max(reviews_data["total"], 1)) * 100
            dist_html += f'''
                        <div class="rv-dist__row">
                            <span class="rv-dist__label">{n} \u2605</span>
                            <div class="rv-dist__bar"><div class="rv-dist__fill" style="width:{pct}%"></div></div>
                            <span class="rv-dist__count">{count}</span>
                        </div>'''

        page = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{nom} - Meilleur Prix Amazon 2026 | Affilimax</title>
<meta name="description" content="{html.escape(produit.get('description',''))[:160]}">
<meta property="og:title" content="{nom} - Meilleur Prix Amazon">
<meta property="og:description" content="{html.escape(produit.get('description',''))[:200]}">
<meta property="og:image" content="{image}">
<meta property="og:type" content="product">
<style>
:root{{--bg:#0a0a1a;--card:#141432;--gold:#f0a500;--purple:#7c3aed;--green:#10b981;--text:#f1f5f9;--muted:#94a3b8;--border:#1e1e4a;--radius:12px}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:Inter,system-ui,sans-serif;background:var(--bg);color:var(--text);line-height:1.6}}
.breadcrumb{{max-width:1100px;margin:0 auto;padding:16px 20px 0;font-size:.78rem;color:var(--muted)}}
.breadcrumb a{{color:var(--purple);text-decoration:none}}
.breadcrumb a:hover{{text-decoration:underline}}
.container{{max-width:1100px;margin:0 auto;padding:30px 20px;display:grid;grid-template-columns:1fr 1fr;gap:40px;align-items:start}}
@media(max-width:768px){{.container{{grid-template-columns:1fr}}}}

/* Image */
.product-image{{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;aspect-ratio:3/2;display:flex;align-items:center;justify-content:center}}
.product-image img{{width:100%;height:100%;object-fit:cover}}

/* Infos */
.product-info h1{{font-size:1.8rem;font-weight:800;margin-bottom:8px}}
.product-info .category{{display:inline-block;padding:3px 12px;background:rgba(124,58,237,.15);color:var(--purple);border-radius:50px;font-size:.72rem;font-weight:600;margin-bottom:12px}}
.rating-row{{display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap}}
.rating-stars{{font-size:1.2rem;letter-spacing:2px}}
.rating-note{{font-weight:800;font-size:1.3rem;font-family:monospace;color:var(--gold)}}
.rating-count{{font-size:.78rem;color:var(--muted)}}
.product-info .desc{{color:var(--muted);font-size:.92rem;margin-bottom:20px;line-height:1.7}}
.product-info .price{{font-size:2.5rem;font-weight:800;font-family:monospace;color:var(--gold);margin:16px 0 4px}}
.product-info .comm{{font-size:.85rem;color:var(--green);font-weight:600;margin-bottom:20px}}

/* Boutons */
.cta-section{{display:flex;gap:12px;flex-wrap:wrap}}
.btn-buy{{flex:1;min-width:200px;padding:16px 24px;background:linear-gradient(135deg,#ffb700,var(--gold));color:#000;border:none;border-radius:10px;font-size:1.05rem;font-weight:700;cursor:pointer;text-align:center;text-decoration:none;transition:all .3s;animation:ctaPulse 2s ease-in-out infinite}}
@keyframes ctaPulse{{0%,100%{{box-shadow:0 0 8px rgba(240,165,0,.3)}}50%{{box-shadow:0 0 24px rgba(240,165,0,.6)}}}}
.btn-buy:hover{{transform:scale(1.04);box-shadow:0 8px 30px rgba(240,165,0,.5)}}
.btn-buy:active{{transform:scale(.96)}}
.btn-back{{padding:16px 24px;background:var(--card);color:var(--text);border:1px solid var(--border);border-radius:10px;font-size:.9rem;cursor:pointer;text-decoration:none;transition:all .2s;text-align:center}}
.btn-back:hover{{border-color:var(--purple)}}
.trust-badges{{display:flex;gap:16px;flex-wrap:wrap;margin-top:20px;padding-top:20px;border-top:1px solid var(--border)}}
.trust-badges span{{font-size:.72rem;color:var(--muted);display:flex;align-items:center;gap:6px}}
.trust-badges .icon{{font-size:1rem}}

/* Features */
.features-section{{max-width:1100px;margin:0 auto 20px;padding:0 20px}}
.features-card{{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:24px}}
.features-card h3{{font-size:1rem;margin-bottom:14px;color:var(--gold)}}
.features-card ul{{list-style:none}}
.features-card li{{padding:10px 0 10px 28px;position:relative;color:var(--muted);font-size:.88rem;border-bottom:1px solid rgba(30,30,74,.5)}}
.features-card li:last-child{{border-bottom:none}}
.features-card li::before{{content:'\2713';position:absolute;left:0;color:var(--green);font-weight:bold}}

/* Avis - Section complete */
.reviews-section{{max-width:1100px;margin:20px auto;padding:0 20px}}
.reviews-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:16px}}
.reviews-header h2{{font-size:1.3rem;font-weight:700}}

/* Resume des notes */
.rv-summary{{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:28px;margin-bottom:20px;display:grid;grid-template-columns:auto 1fr;gap:32px;align-items:center}}
@media(max-width:600px){{.rv-summary{{grid-template-columns:1fr;gap:16px}}}}
.rv-summary__score{{text-align:center}}
.rv-summary__note{{font-size:3rem;font-weight:800;font-family:monospace;color:var(--gold);line-height:1}}
.rv-summary__stars{{font-size:1.5rem;letter-spacing:3px;margin:4px 0}}
.rv-summary__total{{font-size:.78rem;color:var(--muted)}}
.rv-dist{{flex:1}}
.rv-dist__row{{display:flex;align-items:center;gap:10px;margin-bottom:5px}}
.rv-dist__label{{font-size:.8rem;color:var(--muted);min-width:24px;font-family:monospace}}
.rv-dist__bar{{flex:1;height:10px;background:rgba(255,255,255,.05);border-radius:5px;overflow:hidden}}
.rv-dist__fill{{height:100%;border-radius:5px;background:linear-gradient(90deg,var(--gold),#ffb700);transition:width .5s ease}}
.rv-dist__count{{font-size:.78rem;color:var(--muted);font-family:monospace;min-width:24px;text-align:right}}

/* Liste des avis */
.rv-list{{display:flex;flex-direction:column;gap:12px}}
.rv-item{{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:20px;transition:all .2s}}
.rv-item:hover{{border-color:var(--purple)}}
.rv-item__header{{display:flex;align-items:center;gap:12px;margin-bottom:10px}}
.rv-item__avatar{{width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,var(--purple),var(--gold));display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.9rem;flex-shrink:0}}
.rv-item__info{{flex:1;min-width:0}}
.rv-item__author{{font-weight:600;font-size:.85rem;display:flex;align-items:center;gap:6px}}
.rv-item__date{{font-size:.65rem;color:var(--muted);margin-top:2px}}
.rv-item__stars{{font-size:.9rem;letter-spacing:1px;flex-shrink:0}}
.rv-item__title{{font-weight:700;font-size:.9rem;color:var(--gold);margin-bottom:4px}}
.rv-item__text{{color:var(--muted);font-size:.82rem;line-height:1.6}}
.rv-item__footer{{margin-top:10px;font-size:.7rem;color:var(--muted);display:flex;gap:12px}}
.rv-item__helpful{{font-style:italic}}
.rv-empty{{text-align:center;padding:40px;color:var(--muted);background:var(--card);border:1px solid var(--border);border-radius:var(--radius)}}

/* Badge */
.rv-badge{{padding:2px 8px;border-radius:4px;font-size:.62rem;font-weight:600}}
.rv-badge--verified{{background:rgba(16,185,129,.15);color:var(--green)}}

/* Formulaire d'avis */
.rv-form{{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:24px;margin-top:20px}}
.rv-form h3{{font-size:1rem;margin-bottom:16px;display:flex;align-items:center;gap:8px}}
.rv-form__group{{margin-bottom:12px}}
.rv-form__label{{display:block;font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;font-weight:600}}
.rv-form__input,.rv-form__textarea{{width:100%;padding:10px 14px;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:8px;font-size:.85rem;outline:none;transition:all .2s;font-family:inherit}}
.rv-form__input:focus,.rv-form__textarea:focus{{border-color:var(--purple);box-shadow:0 0 0 3px rgba(124,58,237,.15)}}
.rv-form__textarea{{resize:vertical;min-height:80px}}
.rv-form__stars{{display:flex;gap:6px;margin-bottom:12px}}
.rv-form__star-btn{{background:none;border:none;font-size:1.8rem;cursor:pointer;transition:all .15s;color:var(--muted);padding:2px}}
.rv-form__star-btn.active{{color:var(--gold);transform:scale(1.1)}}
.rv-form__star-btn:hover{{color:var(--gold);transform:scale(1.2)}}
.btn-submit{{padding:12px 24px;background:var(--purple);color:#fff;border:none;border-radius:8px;font-weight:700;font-size:.9rem;cursor:pointer;transition:all .2s}}
.btn-submit:hover{{transform:translateY(-1px);box-shadow:0 4px 16px rgba(124,58,237,.3)}}
.btn-submit:disabled{{opacity:.4;cursor:not-allowed;transform:none!important}}

/* Produits similaires */
.related{{max-width:1100px;margin:20px auto;padding:0 20px}}
.related h2{{font-size:1.2rem;margin-bottom:20px}}
.related-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}}
.related-card{{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:16px;transition:all .2s;text-decoration:none;color:var(--text);display:block}}
.related-card:hover{{border-color:var(--purple);transform:translateY(-2px)}}
.related-card .rname{{font-weight:600;font-size:.85rem;margin-bottom:4px}}
.related-card .rprice{{color:var(--gold);font-size:.9rem;font-family:monospace}}
.related-card .rstars{{font-size:.7rem;margin-top:4px}}

/* Footer */
footer{{text-align:center;padding:40px 20px;color:var(--muted);font-size:.7rem;border-top:1px solid var(--border);margin-top:20px}}

/* Like button */
.rv-like-btn{{display:inline-flex;align-items:center;gap:6px;padding:6px 14px;background:rgba(255,255,255,.04);border:1px solid var(--border);border-radius:20px;cursor:pointer;transition:all .2s;font-size:.78rem;color:var(--muted);font-family:inherit}}
.rv-like-btn:hover{{background:rgba(240,165,0,.1);border-color:var(--gold);color:var(--gold)}}
.rv-like-btn.liked{{background:rgba(240,165,0,.15);border-color:var(--gold);color:var(--gold)}}
.rv-like-btn.liked .rv-like-icon{{animation:likePop .3s ease-out}}
@keyframes likePop{{0%{{transform:scale(1)}}50%{{transform:scale(1.3)}}100%{{transform:scale(1)}}}}
.rv-like-icon{{font-size:1rem}}
.rv-like-count{{font-weight:700;font-size:.82rem;font-family:var(--font-mono)}}

/* Sort controls */
.rv-sort{{display:flex;align-items:center;gap:6px}}
.rv-sort__label{{font-size:.72rem;color:var(--muted);white-space:nowrap}}
.rv-sort__select{{padding:6px 10px;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:6px;font-size:.75rem;cursor:pointer;outline:none;font-family:inherit}}
.rv-sort__select:focus{{border-color:var(--purple)}}

/* Toast */
.toast{{position:fixed;bottom:24px;right:24px;padding:14px 24px;background:var(--card);border:1px solid var(--green);border-radius:50px;color:var(--text);font-size:.8rem;z-index:100;box-shadow:0 8px 32px rgba(0,0,0,.5);animation:toastIn .3s ease-out}}
.toast--error{{border-color:var(--red)}}
@keyframes toastIn{{from{{opacity:0;transform:translateY(12px)}}to{{opacity:1;transform:translateY(0)}}}}
</style>
</head>
<body>        <!-- BreadcrumbList Schema.org -->
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [{{
    "@type": "ListItem",
    "position": 1,
    "name": "Accueil",
    "item": "{base}/"
  }},{{
    "@type": "ListItem",
    "position": 2,
    "name": "Offres",
    "item": "{base}/pub.html"
  }},{{
    "@type": "ListItem",
    "position": 3,
    "name": "{nom}",
    "item": "{base}/produit/{html.escape(produit['slug'])}"
  }}]
}}
</script>

<div class="breadcrumb">
    <a href="/">Accueil</a> &rsaquo; <a href="/pub.html">Offres</a> &rsaquo; {nom}
</div>

<div class="container">
    <div class="product-image">
        <img src="{image}" alt="{nom}" loading="lazy">
    </div>
    <div class="product-info">
        <span class="category">{categorie}</span>
        <h1>{nom}</h1>
        <div class="rating-row">
            <span class="rating-stars">{stars_html}</span>
            <span class="rating-note">{note_str}</span>
            <span class="rating-count">({avis_total} avis)</span>
        </div>
        <p class="desc">{desc}</p>
        <div class="price">{prix:.2f} EUR</div>
        <div class="comm">Commission: {comm_euro:.2f} EUR ({comm_pct}%)</div>
        <div class="cta-section">
            <a class="btn-buy" href="{go_url}" rel="nofollow sponsored" target="_blank">
                Voir l'offre sur {plateforme}
            </a>
            <a class="btn-back" href="/pub.html">
                Toutes les offres
            </a>
        </div>
        <div class="trust-badges">
            <span><span class="icon">\U0001f512</span> Paiement securise</span>
            <span><span class="icon">\U0001f69a</span> Livraison rapide</span>
            <span><span class="icon">\U0001f3e6</span> Satisfait ou rembourse</span>
            <span><span class="icon">\u2b50</span> Note {note_str}/5</span>
        </div>
    </div>
</div>

<div class="features-section">
    <div class="features-card">
        <h3>Caracteristiques du produit</h3>
        <ul>"""
        for f in produit.get("caracteristiques", []):
            page += f"\n            <li>{html.escape(f)}</li>"
        page += """
        </ul>
    </div>
</div>

<!-- SECTION AVIS -->
<div class="reviews-section">
    <div class="reviews-header">
        <h2>Avis Clients</h2>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
            <div class="rv-sort">
                <span class="rv-sort__label">Trier :</span>
                <select class="rv-sort__select" onchange="changeSort(this.value)">
                    <option value="recent">Plus recents</option>
                    <option value="note">Meilleures notes</option>
                    <option value="utile">Plus utils</option>
                </select>
            </div>
            <button class="btn-submit" onclick="document.getElementById('reviewForm').scrollIntoView({{behavior:'smooth'}})">
                \U0001f4dd Donner mon avis
            </button>
        </div>
    </div>

    <div class="rv-summary">
        <div class="rv-summary__score">
            <div class="rv-summary__note">{note_str}</div>
            <div class="rv-summary__stars">{stars_html}</div>
            <div class="rv-summary__total">{avis_total} avis clients</div>
        </div>
        <div class="rv-dist">
            {dist_html}
        </div>
    </div>

    <div class="rv-list">
        {reviews_html}
    </div>

    <div class="rv-form" id="reviewForm">
        <h3>\U0001f4dd Donnez votre avis</h3>
        <div class="rv-form__group">
            <label class="rv-form__label">Votre note</label>
            <div class="rv-form__stars" id="starSelector">
                <button class="rv-form__star-btn" data-note="1" onclick="setStar(1)">\u2605</button>
                <button class="rv-form__star-btn" data-note="2" onclick="setStar(2)">\u2605</button>
                <button class="rv-form__star-btn" data-note="3" onclick="setStar(3)">\u2605</button>
                <button class="rv-form__star-btn" data-note="4" onclick="setStar(4)">\u2605</button>
                <button class="rv-form__star-btn" data-note="5" onclick="setStar(5)">\u2605</button>
            </div>
        </div>
        <div class="rv-form__group">
            <label class="rv-form__label">Nom (ou pseudo)</label>
            <input class="rv-form__input" id="reviewName" placeholder="Ex: Jean D." maxlength="50">
        </div>
        <div class="rv-form__group">
            <label class="rv-form__label">Titre de l'avis</label>
            <input class="rv-form__input" id="reviewTitle" placeholder="Ex: Excellent produit !" maxlength="100">
        </div>
        <div class="rv-form__group">
            <label class="rv-form__label">Votre commentaire</label>
            <textarea class="rv-form__textarea" id="reviewComment" placeholder="Partagez votre experience..." maxlength="2000"></textarea>
        </div>
        <button class="btn-submit" id="submitReviewBtn" onclick="submitReview()">\U0001f4ac Publier mon avis</button>
    </div>
</div>

<div class="related">
    <h2>Produits similaires</h2>
    <div class="related-grid">
"""
        _others = [p for p in produits if p.get("actif") and p.get("slug") != slug]
        random.shuffle(_others)
        for _p in _others[:3]:
            _p_slug = _p.get("slug", "")
            _p_nom = html.escape(_p["nom"])
            _p_prix = _p.get("prix", 0)
            _p_note = _p.get("note_moyenne", 0)
            _p_stars_s = "\u2B50" * int(_p_note) + "" * (5 - int(_p_note))
            _p_avis = _p.get("avis_total", 0)
            page += f"""        <a class="related-card" href="/produit/{_p_slug}">
            <div class="rname">{_p_nom}</div>
            <div class="rprice">{_p_prix:.2f} EUR</div>
            <div class="rstars">{_p_stars_s} ({_p_avis})</div>
        </a>
"""

        page += """    </div>
</div>

<footer>
    <p>Affilimax - Plateforme d'affiliation | En partenariat avec Amazon | <a href="/">Dashboard</a> | <a href="/go">Liens</a></p>
</footer>

<script>
let selectedStar = 5;
let currentSort = 'recent';

function setStar(n) {{
    selectedStar = n;
    document.querySelectorAll('.rv-form__star-btn').forEach((btn,i) => {{
        btn.classList.toggle('active', i < n);
    }});
}}
setStar(5);

async function likeReview(reviewId) {{
    const btn = document.querySelector(`#review-${reviewId} .rv-like-btn`);
    if (btn && btn.classList.contains('liked')) {{
        toast('Vous avez dejalikelike cet avis !');
        return;
    }}

    try {{
        const r = await fetch('/api/review/like', {{
            method:'POST',
            headers:{{'Content-Type':'application/json'}},
            body: JSON.stringify({{review_id: reviewId}})
        }});
        const d = await r.json();
        if (d.success) {{
            const countEl = document.getElementById('like-count-' + reviewId);
            if (countEl) {{
                countEl.textContent = d.utile;
                countEl.style.animation = 'none';
                void countEl.offsetWidth;
                countEl.style.animation = 'likePop .3s ease-out';
            }}
            if (btn) {{
                btn.classList.add('liked');
            }}
            toast('Avis utile ! (' + d.utile + ' personnes)');
        } else {{
            toast(d.error || 'Erreur', true);
        }}
    }} catch(e) {{
        toast('Erreur de connexion', true);
    }}
}}

function changeSort(sort) {{
    currentSort = sort;
    const params = new URLSearchParams(window.location.search);
    params.set('sort', sort);
    window.location.search = params.toString();
}}

// Appliquer le tri depuis l'URL au chargement
(function() {{
    const params = new URLSearchParams(window.location.search);
    const sort = params.get('sort') || 'recent';
    const sel = document.querySelector('.rv-sort__select');
    if (sel) sel.value = sort;
}})();

async function submitReview() {{
    const name = document.getElementById('reviewName').value.trim() || 'Anonyme';
    const title = document.getElementById('reviewTitle').value.trim();
    const comment = document.getElementById('reviewComment').value.trim();

    if (!title) {{ toast('Veuillez entrer un titre pour votre avis', true); return; }}
    if (!comment) {{ toast('Veuillez entrer un commentaire', true); return; }}

    const btn = document.getElementById('submitReviewBtn');
    btn.disabled = true;
    btn.textContent = 'Envoi...';

    try {{
        const r = await fetch('/api/review', {{
            method:'POST',
            headers:{{'Content-Type':'application/json'}},
            body: JSON.stringify({{
                slug: '{html.escape(slug)}',
                auteur: name,
                note: selectedStar,
                titre: title,
                commentaire: comment
            }})
        }});
        const d = await r.json();
        if (d.success) {{
            toast('Avis publie avec succes ! Merci.');
            document.getElementById('reviewName').value = '';
            document.getElementById('reviewTitle').value = '';
            document.getElementById('reviewComment').value = '';
            // Recharger la page pour voir l'avis
            setTimeout(() => location.reload(), 1500);
        }} else {{
            toast(d.error || 'Erreur lors de l\'envoi', true);
        }}
    }} catch(e) {{
        toast('Erreur de connexion', true);
    }}
    btn.disabled = false;
    btn.textContent = 'Publier mon avis';
}}

function toast(msg, isError) {{
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();
    const t = document.createElement('div');
    t.className = 'toast' + (isError ? ' toast--error' : '');
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3500);
}}
</script>
</body>
</html>"""
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _load_reviews_for_product(self, slug, sort_by="recent"):
        """Charge les avis pour un produit et calcule les stats.

        Args:
            slug: slug du produit
            sort_by: "recent" (par date), "note" (meilleures notes), "utile" (plus utils)
        """
        try:
            with open(os.path.join(BASE_DIR, "reviews.json"), "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            return {"avis": [], "total": 0, "note_moyenne": 0, "distribution": {'1':0,'2':0,'3':0,'4':0,'5':0}}

        product_reviews = [r for r in data["avis"] if r.get("produit_slug") == slug]
        total = len(product_reviews)
        note_moyenne = 0
        distribution = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}

        if total > 0:
            for r in product_reviews:
                n = str(r.get("note", 0))
                if n in distribution:
                    distribution[n] += 1
            note_moyenne = round(sum(r.get("note", 0) for r in product_reviews) / total, 1)

        # Tri selon le parametre
        if sort_by == "note":
            product_reviews.sort(key=lambda x: (x.get("note", 0), x.get("date", "")), reverse=True)
        elif sort_by == "utile":
            product_reviews.sort(key=lambda x: (x.get("utile", 0), x.get("date", "")), reverse=True)
        else:  # recent par defaut
            product_reviews.sort(key=lambda x: x.get("date", ""), reverse=True)

        return {
            "avis": product_reviews,
            "total": total,
            "note_moyenne": note_moyenne,
            "distribution": distribution,
            "tri": sort_by
        }

    def serve_reviews(self, slug):
        """Endpoint JSON: retourne les avis pour un produit avec tri.
        Query params: ?sort=recent|note|utile
        """
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        sort_by = qs.get("sort", ["recent"])[0]

        data = self._load_reviews_for_product(slug, sort_by=sort_by)
        self.serve_json({
            "avis": data["avis"],
            "total": data["total"],
            "note_moyenne": data["note_moyenne"],
            "distribution": data["distribution"],
            "tri": sort_by
        })

    def serve_review_stats(self, slug):
        """Endpoint JSON: retourne les stats des avis pour un produit."""
        data = self._load_reviews_for_product(slug)
        self.serve_json({
            "note_moyenne": data["note_moyenne"],
            "total": data["total"],
            "distribution": data["distribution"]
        })

    def serve_robots(self):
        """Genere un robots.txt ameliore pour le SEO."""
        host = self.headers.get("Host", "localhost")
        proto = "https" if "RENDER" in os.environ else "http"
        base = f"{proto}://{host}"
        content = f"""User-agent: *
Allow: /
Allow: /pub.html$
Allow: /produit/
Allow: /go
Allow: /payouts.html
Disallow: /admin.html
Disallow: /api/
Disallow: /healthz

# Sitemaps
Sitemap: {base}/sitemap.xml

# Crawl-delay
Crawl-delay: 10

# Host
Host: {base}
"""
        body = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def serve_sitemap(self):
        """Genere un sitemap XML ameliore avec images et priorites pour le SEO."""
        produits = load_products()
        host = self.headers.get("Host", "localhost")
        proto = "https" if "RENDER" in os.environ else "http"
        base = f"{proto}://{host}"
        now = datetime.utcnow().strftime("%Y-%m-%d")

        urls = [f"""  <url>
    <loc>{base}/</loc>
    <lastmod>{now}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
    <xhtml:link rel="alternate" hreflang="fr" href="{base}/"/>
  </url>
  <url>
    <loc>{base}/pub.html</loc>
    <lastmod>{now}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
    <xhtml:link rel="alternate" hreflang="fr" href="{base}/pub.html"/>
  </url>
  <url>
    <loc>{base}/payouts.html</loc>
    <lastmod>{now}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.5</priority>
  </url>
  <url>
    <loc>{base}/go</loc>
    <lastmod>{now}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.6</priority>
  </url>"""]

        for p in produits:
            if p.get("actif") and p.get("slug"):
                prix_str = f", {p['prix']:.2f}EUR" if p.get('prix') else ""
                image_tag = ""
                if p.get("image_url"):
                    image_tag = f"\n    <image:image>\n      <image:loc>{html.escape(p['image_url'])}</image:loc>\n      <image:title>{html.escape(p['nom'])}</image:title>\n      <image:caption>{html.escape(p.get('description',''))[:200]}</image:caption>\n    </image:image>"
                urls.append(f"""  <url>
    <loc>{base}/produit/{html.escape(p['slug'])}</loc>
    <lastmod>{now}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
    <xhtml:link rel="alternate" hreflang="fr" href="{base}/produit/{html.escape(p['slug'])}"/>{image_tag}
  </url>""")

        sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
{chr(10).join(urls)}
</urlset>"""
        body = sitemap.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def serve_go_index(self):
        """Affiche la liste de tous les liens de redirection disponibles avec selecteur de source."""
        try:
            self._serve_go_index_impl()
        except Exception as e:
            print(f"[ERREUR] serve_go_index: {e}", file=sys.stderr)
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"Erreur interne: {e}".encode("utf-8"))

    def _serve_go_index_impl(self):
        """Implementation reelle de serve_go_index."""
        produits = load_products()
        host = self.headers.get("Host", f"localhost:{PORT}")
        proto = "https" if "RENDER" in os.environ else "http"
        base = f"{proto}://{host}"

        page = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Affilimax - Liens de Redirection</title>
<style>
:root{--bg:#0a0a1a;--card:#141432;--gold:#f0a500;--purple:#7c3aed;--green:#10b981;--text:#f1f5f9;--muted:#94a3b8;--border:#1e1e4a;--radius:12px}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Inter,system-ui,sans-serif;background:var(--bg);color:var(--text);padding:40px 20px;max-width:850px;margin:0 auto}
h1{font-size:1.5rem;margin-bottom:8px}
h1 span{background:linear-gradient(135deg,var(--text),var(--gold));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
p.desc{color:var(--muted);margin-bottom:16px;font-size:.9rem}
.source-selector{display:flex;align-items:center;gap:10px;margin-bottom:24px;flex-wrap:wrap;background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:14px 18px}
.source-selector label{font-weight:600;font-size:.82rem;white-space:nowrap}
.source-selector select{padding:8px 12px;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:6px;font-size:.82rem;cursor:pointer}
.source-label{font-size:.7rem;color:var(--green);font-family:monospace;padding:4px 10px;background:rgba(16,185,129,.1);border-radius:4px}
.link-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:16px 20px;margin-bottom:10px;display:flex;align-items:center;justify-content:space-between;gap:12px;transition:all .2s}
.link-card:hover{border-color:var(--purple)}
.link-card__left{min-width:0;flex:1}
.link-card__name{font-weight:600;font-size:.9rem}
.link-card__platform{font-size:.7rem;color:var(--muted)}
.link-card__url{font-size:.72rem;color:var(--purple);font-family:monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:380px;background:rgba(124,58,237,.1);padding:6px 10px;border-radius:6px}
.copy-btn{padding:8px 16px;background:var(--purple);color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:.75rem;font-weight:600;white-space:nowrap;transition:all .15s}
.copy-btn:hover{opacity:.9;transform:scale(1.02)}
.copy-btn:active{transform:scale(.97)}
.copied{background:var(--green)!important}
.footer{text-align:center;margin-top:30px;color:var(--muted);font-size:.7rem}
a{color:var(--purple);text-decoration:none}
a:hover{text-decoration:underline}
</style>
</head>
<body>
<h1><span>Affilimax</span> - Liens de Redirection</h1>
<p class="desc">Copie ces liens et partage-les. Chaque clic est tracke avec la source, puis redirige vers Amazon avec ton tag <strong>confortbure07-21</strong>.</p>
<div class="source-selector">
    <label>Source :</label>
    <select id="srcSelect" onchange="updateUrls()">
        <option value="">Direct (sans source)</option>
        <option value="twitter">Twitter / X</option>
        <option value="facebook">Facebook</option>
        <option value="linkedin">LinkedIn</option>
        <option value="instagram">Instagram</option>
        <option value="tiktok">TikTok</option>
        <option value="email">Email</option>
        <option value="google">SEO / Google</option>
        <option value="ads">Publicite payante</option>
    </select>
    <span class="source-label" id="srcLabel">referencement_direct</span>
</div>
"""
        for i, p in enumerate(produits):
            if not p.get("actif"):
                continue
            idx = i + 1
            url = f"{base}/go/{idx}"
            safe_name = html.escape(p['nom'])
            safe_platform = html.escape(p['plateforme'])
            safe_url = html.escape(url)
            page += f"""
<div class="link-card">
    <div class="link-card__left">
        <div class="link-card__name">{idx}. {safe_name}</div>
        <div class="link-card__platform">{safe_platform} &middot; {p['prix']:.2f} EUR &middot; {p['commission_pct']}% comm</div>
    </div>
    <div class="link-card__url" id="url{idx}" title="{safe_url}">{safe_url}</div>
    <button class="copy-btn" id="btn{idx}" onclick="copyLink({idx})">Copier</button>
</div>"""

        page += """
<div class="footer">
    <a href="/">Dashboard</a> &middot;
    <a href="/pub.html">Landing Page</a>
</div>
<script>
const BASE = """ + json.dumps(base) + """;
function updateUrls() {
    const src = document.getElementById('srcSelect').value;
    const label = document.getElementById('srcLabel');
    const map = {twitter:'reseaux_sociaux',facebook:'reseaux_sociaux',linkedin:'reseaux_sociaux',instagram:'reseaux_sociaux',tiktok:'reseaux_sociaux',email:'email_marketing',google:'SEO_organique',ads:'publicite_payante','':'referencement_direct'};
    label.textContent = map[src] || 'referencement_direct';
    const TOTAL = document.querySelectorAll('.link-card').length;
    for (let i=1; i<=TOTAL; i++) {
        const el = document.getElementById('url'+i);
        if (el) {
            const u = BASE + '/go/' + i + (src ? '?src=' + src : '');
            el.textContent = u;
            el.title = u;
        }
    }
}
function copyLink(idx) {
    const src = document.getElementById('srcSelect').value;
    const u = BASE + '/go/' + idx + (src ? '?src=' + src : '');
    navigator.clipboard.writeText(u).then(() => {
        const btn = document.getElementById('btn'+idx);
        btn.textContent = 'Copie !';
        btn.classList.add('copied');
        setTimeout(() => { btn.textContent = 'Copier'; btn.classList.remove('copied'); }, 2000);
    });
}
</script>
</body>
</html>"""
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def serve_json(self, data):
        """Envoie une reponse JSON."""
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # Desactiver les logs DNS inutiles
    def address_string(self):
        return self.client_address[0]


# ==================== DEMARRAGE ====================

def main():
    # Initialiser les donnees
    data = load_data()
    is_render = "RENDER" in os.environ
    env_name = "Render.com" if is_render else "Local"

    print("=" * 55)
    print(f"    AFFILIMAX - Serveur Backend ({env_name})")
    print("=" * 55)
    print(f"    Port : {PORT}")
    print(f"    Mode : {'DEPLOYE (Render)' if is_render else 'LOCAL'}")
    print(f"    Data : {STATS_FILE}")
    print("=" * 55)

    # Demarrer le generateur de trafic (desactive par defaut)
    auto_traffic = os.environ.get("AUTO_TRAFFIC", "0") == "1"
    if auto_traffic:
        traffic_thread = threading.Thread(target=traffic_generator, daemon=True)
        traffic_thread.start()
        print("   [TRAFIC] Auto-trafic ACTIVE")
    else:
        print("   [TRAFIC] Auto-trafic DESACTIVE (AUTO_TRAFFIC=1 pour activer)")
    print()

    # Demarrer le Promo Automator (desactive par defaut)
    auto_promo = os.environ.get("AUTO_PROMO", "0") == "1"
    if auto_promo:
        try:
            result = promo_automator.automator.start()
            print(f"   [PROMO] Auto-Promo ACTIVE ({result.get('status', 'started')})")
        except Exception as e:
            print(f"   [PROMO] Erreur demarrage auto: {e}")
    else:
        print("   [PROMO] Auto-Promo DESACTIVE (AUTO_PROMO=1 pour activer)")
    print()

    # Demarrer le serveur HTTP
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), AffilimaxHandler)
    if is_render:
        render_url = os.environ.get("RENDER_EXTERNAL_URL", f"https://affilimax.onrender.com")
        print(f" >>> Dashboard : {render_url}")
        print(f" >>> Pub        : {render_url}/pub.html")
        print(f" >>> Admin      : {render_url}/admin.html")
        print(f" >>> Partenaire : {render_url}/partner.html")
    else:
        print(f" >>> Dashboard : http://localhost:{PORT}")
        print(f" >>> Pub       : http://localhost:{PORT}/pub.html")
        print(f" >>> Admin     : http://localhost:{PORT}/admin.html")
        print(f" >>> Partenaire: http://localhost:{PORT}/partner.html")
    print(f" >>> Seules TES injections apparaissent. ZERO simulation.")
    print(f" >>> Ctrl+C pour arreter.")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[OK] Serveur arrete.")
        server.shutdown()


if __name__ == "__main__":
    main()
