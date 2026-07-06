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

# ==================== CONFIGURATION ====================

PORT = int(os.environ.get("PORT", 8765))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATS_FILE = os.path.join(BASE_DIR, "stats.json")
LIENS_FILE = os.path.join(BASE_DIR, "liens_affiliation.json")
DATA_LOCK = threading.Lock()

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
            {"nom": "Balance Connectee", "plateforme": "Amazon", "clics": 0, "conversions": 0, "commissions": 0.0, "progression": 0}
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

def load_products():
    """Charge la liste des produits depuis liens_affiliation.json."""
    try:
        with open(LIENS_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            return config.get("produits", [])
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

        # API: Statistiques
        if path == "/api/stats":
            self.serve_json(load_data())
            return

        # API: Produits (liens d'affiliation reels)
        if path == "/api/produits":
            self.serve_json(load_products())
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

        # REDIRECTEUR DE CLICS: /go/<slug> -> enregistre clic + redirige Amazon
        if path.startswith("/go/") and len(path) > 4:
            slug = path[4:].strip().lower()
            self.handle_redirect(slug)
            return

        # PAGE /go : liste tous les liens de redirection disponibles
        if path in ("/go", "/go/"):
            self.serve_go_index()
            return

        # Fichiers statiques
        if path == "/" or path == "":
            self.path = "/index.html"

        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Lire le body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(body) if body else {}
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

        html = """<!DOCTYPE html>
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
            html += f"""
<div class="link-card">
    <div class="link-card__left">
        <div class="link-card__name">{idx}. {safe_name}</div>
        <div class="link-card__platform">{safe_platform} &middot; {p['prix']:.2f} EUR &middot; {p['commission_pct']}% comm</div>
    </div>
    <div class="link-card__url" id="url{idx}" title="{safe_url}">{safe_url}</div>
    <button class="copy-btn" id="btn{idx}" onclick="copyLink({idx})">Copier</button>
</div>"""

        html += """
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
        body = html.encode("utf-8")
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

    # Demarrer le serveur HTTP
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), AffilimaxHandler)
    if is_render:
        render_url = os.environ.get("RENDER_EXTERNAL_URL", f"https://affilimax.onrender.com")
        print(f" >>> Dashboard : {render_url}")
        print(f" >>> Pub        : {render_url}/pub.html")
        print(f" >>> Admin      : {render_url}/admin.html")
    else:
        print(f" >>> Dashboard : http://localhost:{PORT}")
        print(f" >>> Pub       : http://localhost:{PORT}/pub.html")
        print(f" >>> Admin     : http://localhost:{PORT}/admin.html")
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
