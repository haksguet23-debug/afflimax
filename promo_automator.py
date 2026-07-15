#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Affilimax - Promo Automator Intelligent
========================================
Orchestrateur de promotion automatique des produits.
Genere, planifie et publie du contenu sur les reseaux sociaux
de facon intelligente et periodique.

Fonctionnalites:
  - Rotation aleatoire des 30 produits
  - Planning intelligent (heures de pointe, jours meilleurs)
  - Generation de contenu unique pour chaque publication
  - Stats en temps reel des publications
  - Pas de spam : intervalle aleatoire de 1h a 6h entre les posts
  - Mode silencieux la nuit

Usage:
    python promo_automator.py              # Demarre l'automate
    python promo_automator.py --once        # Genere 1 post et s'arrete
    python promo_automator.py --stats       # Affiche les statistiques
    python promo_automator.py --force       # Force une publication maintenant
"""

import json
import os
import random
import sys
import threading
import time
from datetime import datetime, timedelta

# Verrouillage thread-safe pour les accès concurrents au calendrier
CALENDAR_LOCK = threading.Lock()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LIENS_FILE = os.path.join(BASE_DIR, "liens_affiliation.json")
CALENDAR_FILE = os.path.join(BASE_DIR, "promo_calendar.json")

# ==================== CONFIGURATION ====================

INTERVAL_MIN = 3600      # 1h minimum entre les posts
INTERVAL_MAX = 21600     # 6h maximum (par defaut 3-4h)
SILENT_START = 23        # 23h - mode nuit
SILENT_END = 7           # 7h - reprise le matin
MAX_HISTORY = 500        # Garder 500 entrees max

# Poids des plateformes (plus de Twitter car plus d'engagement)
PLATFORM_WEIGHTS = {
    "twitter": 45,
    "linkedin": 15,
    "facebook": 15,
    "instagram": 10,
    "telegram": 10,
    "email": 5
}

# Types de contenu generes par contenu
CONTENT_TYPES = ["tweet_promo", "tweet_astuce", "post_long", "email", "blog"]
CONTENT_WEIGHTS = [40, 25, 20, 10, 5]

# ==================== CHARGEMENT PRODUITS ====================

def load_products():
    try:
        with open(LIENS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [p for p in data.get("produits", []) if p.get("actif")]
    except Exception:
        return []

def get_product_by_slug(slug):
    produits = load_products()
    for p in produits:
        if p.get("slug") == slug:
            return p
    return None

def get_product_by_index(idx):
    produits = load_products()
    if 0 <= idx < len(produits):
        return produits[idx]
    return None

def slugify(text):
    return text.lower().replace(" ", "-").replace("'", "").replace(":", "").replace(",", "")[:30]

# ==================== GENERATEUR DE CONTENU EMBARQUE ====================

# --- ASTUCES/TIPS (petits tweets utiles) ---
ASTUCES = [
    "{nom} : nos 3 astuces pour en profiter au max !\n1. {astuce_1}\n2. {astuce_2}\n3. {astuce_3}\n\n{prix}€ sur Amazon\n👉 {url}",
    "💡 SAVIEZ-VOUS ? {fun_fact}\n\nLe {nom} est l'un de nos best-sellers avec {note}/5 ★\n{prix}€ → {url}",
    "📌 3 raisons d'acheter le {nom} aujourd'hui :\n✅ {raison_1}\n✅ {raison_2}\n✅ {raison_3}\n⭐ {note}/5 ★ ({avis} avis)\n👉 {url}",
    "🆕 Nouveaute dans notre selection : {nom}\n{desc_courte}\n{prix}€ | Note: {note}/5 ★\n🔗 {url}",
    "🎯 Vous cherchez un {categorie} ? On a teste pour vous : {nom}\n{note}/5 ★ par {avis} acheteurs\n{prix}€ → {url}",
    "🔊 TEST : {nom}\n{desc_courte}\n\nNotre avis : {note}/5 ★\nPrix: {prix}€\n👉 {url}",
    "📊 {nom} en chiffres :\n• Note: {note}/5 ★\n• Avis: {avis} clients\n• Prix: {prix}€\n• Commission: {comm_pct}%\n\n👉 {url}",
    "🔥 COUP DE COEUR : {nom}\n{note}/5 ★ - Le meilleur {categorie} du moment\n{prix}€ → {url}\n#bonplan",
]

# --- TEMPLATES POUR POSTS LONGS ---
LONG_POSTS_TEMPLATES = [
    {
        "titre": "Pourquoi acheter le {nom} ? Notre analyse complete",
        "contenu": """🎯 **{titre}**

Apres des heures d'analyse et des centaines d'avis clients, voici pourquoi le **{nom}** merite votre attention.

⭐ **Note moyenne : {note}/5 ★** ({avis} avis clients)
💰 **Au prix de {prix}€**

**Points forts :**
✅ {astuce_1}
✅ {astuce_2}
✅ {astuce_3}

**Ce qu'en disent les clients :**
"Achat verifie" - Note {note}/5 ★
{desc_courte}

🔗 Decouvrir le produit : {url}

#{categorie_slug} #Avis #BonPlan #Shopping"""
    },
    {
        "titre": "{nom} vs les autres : lequel choisir ?",
        "contenu": """🥊 **Comparatif : {nom} vs concurrence**

Le marche des {categorie}s est vaste, mais le **{nom}** se demarque par :

1️⃣ {astuce_1}
2️⃣ {astuce_2}
3️⃣ {astuce_3}

📊 **Note : {note}/5 ★** | {avis} avis clients
💰 **Prix : {prix}€**

Notre verdict : {nom} est le meilleur rapport qualite-prix de sa categorie !

👉 {url}

#{categorie_slug} #Comparatif #{plateforme} #AchatMalin"""
    }
]

# --- EMAIL MARKETING ---
EMAIL_TEMPLATES = [
    {
        "objet": "{nom} : l'offre du jour a {prix}€",
        "corps": """Bonjour {prenom},

Nous avons selectionne pour vous un produit d'exception :

**{nom}**
{desc_courte}

⭐ Note : {note}/5 ★ ({avis} avis)
💰 Prix : {prix}€
📦 Commission : {comm_pct}%

{cta_bouton}

L'equipe Affilimax
---
Pour vous desabonner : [lien]"""
    },
    {
        "objet": "🔥 Exclusivite : {nom} arrive sur Affilimax",
        "corps": """Salut {prenom},

Nouveaute sur Affilimax ! **{nom}** vient d'etre ajoute a notre catalogue.

{desc_courte}

⭐ {note}/5 ★ | 👥 {avis} clients recommanderaint ce {categorie}
💶 {prix}€

{cta_bouton}

A bientot,
L'equipe Affilimax"""
    }
]

FACTS = {
    "Tech": [
        "le Wi-Fi 6 est 4x plus rapide que le Wi-Fi 4",
        "un SSD moderne est 10x plus rapide qu'un disque dur traditionnel",
        "la 1ere souris d'ordinateur etait en bois",
        "le premier disque dur ne stockait que 5 Mo en 1956"
    ],
    "Audio": [
        "le casque audio a ete invente en 1910",
        "les ecouteurs sans fil utilisent la norme Bluetooth 5.3",
        "le bruit blanc peut aider a la concentration",
        "la musique classique booste la productivite de 15%"
    ],
    "default": [
        "ce type de produit existe depuis plus de 50 ans",
        "les clients satisfaits en recommandent 3 en moyenne",
        "le bouche-a-oreille reste le 1er moteur d'achat",
        "96% des clients lisent les avis avant d'acheter"
    ]
}

CTA_LIST = [
    "👉 Decouvrir sur Amazon : {url}",
    "🔗 Voir le produit : {url}",
    "💰 Verifier le prix : {url}",
    "⭐ Lire les avis : {url}",
    "🛒 Ajouter au panier : {url}"
]

def generate_content_for_product(product, prenom="Ami"):
    """Genere un contenu unique pour ce produit."""
    slug = product.get("slug", "")
    nom = product.get("nom", "")
    prix = product.get("prix", 0)
    note = product.get("note_moyenne", 4.0)
    avis = product.get("avis_total", 0)
    comm_pct = product.get("commission_pct", 5)
    categorie = product.get("categorie", "General")
    plateforme = product.get("plateforme", "Amazon")
    desc = product.get("description", "Excellent produit.")
    desc_courte = desc[:100] + "..." if len(desc) > 100 else desc
    caracteristiques = product.get("caracteristiques", [])

    # Astuces a partir des caracteristiques
    astuces = []
    for c in caracteristiques[:3]:
        c_clean = c[:80] + "..." if len(c) > 80 else c
        astuces.append(c_clean)
    while len(astuces) < 3:
        astuces.append("Qualite professionnelle certifiee")

    fun_facts = FACTS.get(categorie, FACTS["default"])

    context = {
        "nom": nom,
        "slug": slug,
        "prix": prix,
        "note": note,
        "avis": avis,
        "comm_pct": comm_pct,
        "categorie": categorie,
        "categorie_slug": slugify(categorie),
        "plateforme": plateforme,
        "desc_courte": desc_courte,
        "astuce_1": astuces[0] if len(astuces) > 0 else "Qualite exceptionnelle",
        "astuce_2": astuces[1] if len(astuces) > 1 else "Rapport qualite-prix imbattable",
        "astuce_3": astuces[2] if len(astuces) > 2 else "Service client reactif",
        "raison_1": astuces[0] if len(astuces) > 0 else "Qualite exceptionnelle",
        "raison_2": astuces[1] if len(astuces) > 1 else "Rapport qualite-prix imbattable",
        "raison_3": astuces[2] if len(astuces) > 2 else "Service client reactif",
        "fun_fact": random.choice(fun_facts),
        "url": f"https://affilmax.render.com/go/{slug}?src=promo",
        "prenom": prenom,
        "cta_bouton": random.choice(CTA_LIST).format(url=f"https://affilmax.render.com/go/{slug}?src=email")
    }

    # Choisir le type de contenu
    content_type = random.choices(CONTENT_TYPES, weights=CONTENT_WEIGHTS, k=1)[0]

    if content_type == "tweet_promo":
        tpl = random.choice(ASTUCES)
        text = tpl.format(**context)
        return {"type": "twitter", "content": text, "titre": nom[:80]}

    elif content_type == "tweet_astuce":
        tpl = random.choice(ASTUCES)
        text = tpl.format(**context)
        return {"type": "twitter", "content": text, "titre": f"Astuce {nom}"[:80]}

    elif content_type == "post_long":
        tpl = random.choice(LONG_POSTS_TEMPLATES)
        titre = tpl["titre"].format(**context)
        contenu = tpl["contenu"].format(**context)
        return {"type": random.choice(["linkedin", "facebook"]), "content": contenu, "titre": titre}

    elif content_type == "email":
        tpl = random.choice(EMAIL_TEMPLATES)
        return {"type": "email", "objet": tpl["objet"].format(**context), "content": tpl["corps"].format(**context)}

    else:  # blog
        tpl = random.choice(LONG_POSTS_TEMPLATES)
        titre = tpl["titre"].format(**context)
        contenu = tpl["contenu"].format(**context)
        return {"type": "blog", "content": contenu, "titre": titre}


# ==================== CALENDRIER ====================

def load_calendar():
    with CALENDAR_LOCK:
        try:
            with open(CALENDAR_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return init_calendar()

def init_calendar():
    cal = {
        "created_at": datetime.utcnow().isoformat() + "Z",
        "stats": {
            "total_posts": 0,
            "products_used": set(),
            "by_platform": {"twitter": 0, "linkedin": 0, "facebook": 0, "instagram": 0, "telegram": 0, "email": 0, "blog": 0},
            "by_day": {},
            "last_24h": 0
        },
        "history": [],
        "schedule": {
            "last_post_at": None,
            "next_post_at": None,
            "interval_seconds": None,
            "running": False,
            "started_at": None
        }
    }
    save_calendar(cal)
    return cal

def save_calendar(data):
    """Sauvegarde le calendrier (convertit les sets en listes pour JSON)."""
    clean = json.loads(json.dumps(data, default=lambda x: list(x) if isinstance(x, set) else x))
    with CALENDAR_LOCK:
        with open(CALENDAR_FILE, "w", encoding="utf-8") as f:
            json.dump(clean, f, indent=2, ensure_ascii=False)

def add_to_history(entry):
    """Ajoute une entree dans l'historique du calendrier."""
    cal = load_calendar()

    # Stats
    cal["stats"]["total_posts"] += 1
    platform = entry.get("platform", "twitter")
    cal["stats"]["by_platform"][platform] = cal["stats"]["by_platform"].get(platform, 0) + 1

    today = datetime.utcnow().strftime("%Y-%m-%d")
    cal["stats"]["by_day"][today] = cal["stats"]["by_day"].get(today, 0) + 1
    cal["stats"]["last_24h"] = sum(1 for h in cal["history"]
        if (datetime.utcnow() - datetime.fromisoformat(h.get("created_at", "").replace("Z", "+00:00"))).total_seconds() < 86400)

    # Historique
    cal["history"].insert(0, entry)
    if len(cal["history"]) > MAX_HISTORY:
        cal["history"] = cal["history"][:MAX_HISTORY]

    save_calendar(cal)
    return cal


# ==================== ORCHESTRATEUR ====================

class PromoAutomator:
    """Orchestrateur intelligent de publications."""

    def __init__(self):
        self.running = False
        self.thread = None
        self._stop_event = threading.Event()

    def stats(self):
        """Retourne les stats et l'etat courant."""
        cal = load_calendar()
        produits = load_products()
        now = datetime.utcnow()

        # Derniers posts
        last_10 = cal.get("history", [])[:10]

        # Nombre de produits jamais postes
        posted_slugs = set()
        for h in cal.get("history", []):
            posted_slugs.add(h.get("product_slug"))

        never_posted = [p for p in produits if p.get("slug") not in posted_slugs]

        # Prochain post
        sched = cal.get("schedule", {})
        next_at = sched.get("next_post_at")
        if next_at:
            next_dt = datetime.fromisoformat(next_at.replace("Z", "+00:00"))
            seconds_until = (next_dt - now).total_seconds()
        else:
            seconds_until = 0

        return {
            "running": self.running,
            "total_posts": cal["stats"]["total_posts"],
            "products_posted": len(posted_slugs),
            "total_products": len(produits),
            "never_posted": [p["nom"] for p in never_posted[:5]],
            "never_posted_count": len(never_posted),
            "by_platform": cal["stats"]["by_platform"],
            "last_24h": cal["stats"]["last_24h"],
            "last_posts": last_10,
            "next_post_in_seconds": int(seconds_until) if seconds_until > 0 else 0,
            "started_at": sched.get("started_at"),
            "history_count": len(cal.get("history", []))
        }

    def force_post(self):
        """Force la publication d'un post maintenant."""
        result = self._generate_and_publish()
        return result

    def start(self, daemon=True):
        """Demarre l'automate en arriere-plan."""
        if self.running:
            return {"status": "already_running"}

        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._run_loop, daemon=daemon)
        self.thread.start()

        # Mettre a jour le calendrier
        cal = load_calendar()
        cal["schedule"]["running"] = True
        cal["schedule"]["started_at"] = datetime.utcnow().isoformat() + "Z"
        save_calendar(cal)

        return {"status": "started", "message": "Automate de promotion lance"}

    def stop(self):
        """Arrete l'automate."""
        self.running = False
        self._stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)

        cal = load_calendar()
        cal["schedule"]["running"] = False
        save_calendar(cal)

        return {"status": "stopped", "message": "Automate de promotion arrete"}

    def _run_loop(self):
        """Boucle principale de l'automate."""
        while not self._stop_event.is_set():
            try:
                # Vehicule silencieux la nuit
                now_local = datetime.now()
                if SILENT_START <= now_local.hour or now_local.hour < SILENT_END:
                    # Mode nuit - attendre jusqu'au matin
                    seconds_until_morning = ((SILENT_END - now_local.hour) % 24) * 3600
                    print(f"[PROMO] Mode nuit jusqu'a {SILENT_END}h. Prochain check dans {seconds_until_morning//3600}h")
                    self._stop_event.wait(min(seconds_until_morning, 3600))
                    continue

                # Generer et publier
                self._generate_and_publish()

                # Intervalle aleatoire intelligent
                interval = random.randint(INTERVAL_MIN, INTERVAL_MAX)

                # Ajuster selon l'heure (plus frequent en jour)
                hour = now_local.hour
                if 10 <= hour <= 14 or 18 <= hour <= 21:
                    # Heures de pointe : intervalle reduit de 30%
                    interval = int(interval * 0.7)
                elif 7 <= hour <= 9 or 15 <= hour <= 17:
                    # Heures creuses : intervalle normal
                    pass
                else:
                    # Nuit/fin de nuit : intervalle augmente
                    interval = int(interval * 1.3)

                # Mettre a jour le calendrier
                cal = load_calendar()
                next_at = datetime.utcnow() + timedelta(seconds=interval)
                cal["schedule"]["last_post_at"] = datetime.utcnow().isoformat() + "Z"
                cal["schedule"]["next_post_at"] = next_at.isoformat() + "Z"
                cal["schedule"]["interval_seconds"] = interval
                save_calendar(cal)

                print(f"[PROMO] Prochain post dans {interval//3600}h{interval%3600//60}min")

                # Attendre (avec possibilite d'arret)
                self._stop_event.wait(interval)

            except Exception as e:
                print(f"[PROMO] Erreur: {e}")
                self._stop_event.wait(300)  # 5min avant retry

        print("[PROMO] Automate arrete.")

    def _generate_and_publish(self):
        """Genere un contenu et l'ajoute au calendrier."""
        produits = load_products()
        if not produits:
            print("[PROMO] Aucun produit disponible")
            return {"status": "error", "message": "Aucun produit"}

        cal = load_calendar()

        # Prioriser les produits jamais postes
        posted_slugs = set()
        for h in cal.get("history", []):
            posted_slugs.add(h.get("product_slug"))

        never_posted = [p for p in produits if p.get("slug") not in posted_slugs]
        if never_posted and random.random() < 0.7:
            # 70% de chance de prendre un produit jamais poste
            product = random.choice(never_posted)
        else:
            # Sinon, tous les produits ont ete postes, rotation normale
            # Eviter de repeter le meme produit dans les 5 derniers posts
            recent_slugs = set(h.get("product_slug") for h in cal.get("history", [])[:5])
            candidates = [p for p in produits if p.get("slug") not in recent_slugs]
            if not candidates:
                candidates = produits
            product = random.choice(candidates)

        # Choisir une plateforme avec poids
        platforms = list(PLATFORM_WEIGHTS.keys())
        weights = list(PLATFORM_WEIGHTS.values())
        platform = random.choices(platforms, weights=weights, k=1)[0]

        # Generer le contenu
        content = generate_content_for_product(product)
        # Forcer la plateforme choisie (sauf si c'est deja le bon type)
        if content["type"] not in ("twitter", "linkedin", "facebook", "instagram"):
            content["type"] = platform

        entry = {
            "product_slug": product.get("slug", ""),
            "product_name": product.get("nom", ""),
            "platform": content["type"],
            "titre": content.get("titre", ""),
            "content": content.get("content", ""),
            "objet": content.get("objet", ""),
            "created_at": datetime.utcnow().isoformat() + "Z",
            "price": product.get("prix", 0),
            "rating": product.get("note_moyenne", 0)
        }

        cal = add_to_history(entry)
        print(f"[PROMO] Publie: {product['nom'][:40]} sur {content['type']}")

        # Notification asynchrone (thread daemon, ne bloque pas la publication meme si Telegram/Slack timeout)
        try:
            import notifications as _notif_mod
            promo_url = f"https://affilmax.render.com/go/{product.get('slug', '')}?src={content['type']}"
            preview = content.get("content", "") or content.get("objet", "")
            threading.Thread(
                target=_notif_mod.notify_promo_post,
                args=(content["type"], product.get("nom", ""), preview[:200], promo_url),
                daemon=True
            ).start()
        except Exception as e:
            print(f"[PROMO] Notification non envoyee: {e}")

        return {"status": "published", "entry": entry}


# ==================== INSTANCE GLOBALE ====================

automator = PromoAutomator()


# ==================== CLI ====================

def print_stats():
    """Affiche les stats dans la console."""
    stats = automator.stats()
    print("=" * 55)
    print("    PROMO AUTOMATOR - STATISTIQUES")
    print("=" * 55)
    print(f"  Etat:            {'ACTIF' if stats['running'] else 'INACTIF'}")
    print(f"  Total posts:     {stats['total_posts']}")
    print(f"  Produits postes: {stats['products_posted']}/{stats['total_products']}")
    if stats['never_posted_count'] > 0:
        print(f"  Jamais postes:   {stats['never_posted_count']} (prioritaires)")
    print(f"  Posts 24h:       {stats['last_24h']}")
    print(f"  Prochain post:   dans {stats['next_post_in_seconds']//60}min" if stats['next_post_in_seconds'] > 0 else "  Prochain post:   immediatement")
    print(f"  Plateformes:")
    for p, c in sorted(stats['by_platform'].items(), key=lambda x: -x[1]):
        if c > 0:
            print(f"    - {p}: {c}")
    print()
    print(f"  5 derniers posts:")
    for p in stats['last_posts'][:5]:
        print(f"    [{p.get('platform','?')}] {p.get('product_name','?')[:50]}")
    print("=" * 55)


if __name__ == "__main__":
    if "--stats" in sys.argv:
        print_stats()
        sys.exit(0)

    if "--once" in sys.argv:
        result = automator.force_post()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0)

    if "--force" in sys.argv:
        result = automator.force_post()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print_stats()
        sys.exit(0)

    # Demarrer l'automate
    print("[PROMO] Demarrage de l'automate de promotion...")
    automator.start()
    print_stats()

    print("\n[PROMO] En cours... Ctrl+C pour arreter.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n[PROMO] Arret...")
        automator.stop()
        print("[PROMO] Automate arrete.")
