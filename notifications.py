#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Affilimax - Systeme de Notifications Automatiques
==================================================
Envoie des notifications Telegram et/ou Slack quand :
- Un partenaire recoit un paiement
- Une commission est creditee
- Le seuil minimum de paiement est atteint

Configuration:
- Variables d'environnement : TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, SLACK_WEBHOOK_URL
- Ou fichier notifications_config.json

Utilisation:
    from notifications import notify_payout, notify_commission, notify_threshold
    notify_payout("Sophie Martin", 147.80, "completed")
"""

import html
import json
import os
import threading
from datetime import datetime
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = BASE_DIR / "notifications_config.json"

# ==================== CHARGEMENT CONFIG ====================

def load_config():
    """Charge la configuration des notifications."""
    config = {
        "telegram": {
            "enabled": False,
            "bot_token": os.environ.get("TELEGRAM_TOKEN", ""),
            "chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
            "notify_payout": True,
            "notify_commission": True,
            "notify_threshold": True,
            "notify_promo_post": True
        },
        "slack": {
            "enabled": False,
            "webhook_url": os.environ.get("SLACK_WEBHOOK_URL", ""),
            "notify_payout": True,
            "notify_commission": True,
            "notify_threshold": True,
            "notify_promo_post": True
        }
    }

    # Surcharger avec le fichier de config si existant
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                file_config = json.load(f)
                # Fusionner les configs
                for platform in ["telegram", "slack"]:
                    if platform in file_config:
                        for key, value in file_config[platform].items():
                            if key != "bot_token" or os.environ.get(f"TELEGRAM_TOKEN"):
                                config[platform][key] = value
        except:
            pass

    # Verifier si les tokens sont presents (environment > fichier)
    for env_key, config_key in [("TELEGRAM_TOKEN", "bot_token"), ("TELEGRAM_CHAT_ID", "chat_id"), ("SLACK_WEBHOOK_URL", "webhook_url")]:
        env_val = os.environ.get(env_key)
        if env_val:
            platform = "telegram" if env_key.startswith("TELEGRAM") else "slack"
            config[platform][config_key] = env_val

    # Activer les plateformes si les credentials sont presents
    if config["telegram"]["bot_token"] and config["telegram"]["chat_id"]:
        config["telegram"]["enabled"] = True
    if config["slack"]["webhook_url"]:
        config["slack"]["enabled"] = True

    return config


def save_config(config):
    """Sauvegarde la configuration des notifications."""
    # Ne pas sauvegarder les tokens en clair (sauf si pas dans env)
    save_data = {
        "telegram": {
            "enabled": config["telegram"]["enabled"],
            "bot_token": "" if os.environ.get("TELEGRAM_TOKEN") else config["telegram"]["bot_token"],
            "chat_id": config["telegram"]["chat_id"],
            "notify_payout": config["telegram"]["notify_payout"],
            "notify_commission": config["telegram"]["notify_commission"],
            "notify_threshold": config["telegram"]["notify_threshold"],
            "notify_promo_post": config["telegram"].get("notify_promo_post", True)
        },
        "slack": {
            "enabled": config["slack"]["enabled"],
            "webhook_url": "" if os.environ.get("SLACK_WEBHOOK_URL") else config["slack"]["webhook_url"],
            "notify_payout": config["slack"]["notify_payout"],
            "notify_commission": config["slack"]["notify_commission"],
            "notify_threshold": config["slack"]["notify_threshold"],
            "notify_promo_post": config["slack"].get("notify_promo_post", True)
        }
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)
    return config


# ==================== MOTEUR DE NOTIFICATION ====================

def _send_telegram(bot_token, chat_id, message, parse_mode="HTML"):
    """Envoie un message Telegram via l'API Bot."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print(f"  [NOTIF] Telegram: message envoye")
            return True
        else:
            print(f"  [NOTIF] Telegram: erreur {resp.status_code}: {resp.text[:100]}")
            return False
    except Exception as e:
        print(f"  [NOTIF] Telegram: erreur connexion: {e}")
        return False


def _send_slack(webhook_url, message, blocks=None):
    """Envoie un message Slack via Webhook."""
    payload = {"text": message}
    if blocks:
        payload["blocks"] = blocks
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code == 200:
            print(f"  [NOTIF] Slack: message envoye")
            return True
        else:
            print(f"  [NOTIF] Slack: erreur {resp.status_code}: {resp.text[:100]}")
            return False
    except Exception as e:
        print(f"  [NOTIF] Slack: erreur connexion: {e}")
        return False


# ==================== FONCTIONS DE NOTIFICATION ====================

def notify_payout(partner_nom, montant, statut="completed", payout_id=None, mode="demo"):
    """Notifie qu'un partenaire a recu un paiement.
    
    Args:
        partner_nom: nom du partenaire
        montant: montant du paiement en EUR
        statut: completed, pending, failed
        payout_id: ID de transaction (optionnel)
        mode: demo ou live
    """
    config = load_config()
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    emoji = "✅" if statut == "completed" else "⏳" if statut == "pending" else "❌"
    mode_tag = "🔬 DEMO" if mode == "demo" else "🔴 LIVE"

    # Message Telegram
    tg_message = f"""<b>{emoji} Paiement Partenaire - {mode_tag}</b>

👤 <b>Partenaire :</b> {partner_nom}
💰 <b>Montant :</b> {montant:.2f} EUR
📊 <b>Statut :</b> {statut.upper()}
🆔 <b>Transaction :</b> {payout_id or 'N/A'}
🕐 <b>Date :</b> {timestamp}

━━━━━━━━━━━━━━━━━
🔗 <a href='http://localhost:8765/admin.html'>Voir dans le dashboard</a>"""

    # Message Slack (avec Block Kit)
    color = "#10b981" if statut == "completed" else "#f0a500" if statut == "pending" else "#ef4444"
    slack_message = f"{emoji} Paiement Partenaire - {mode_tag}"
    slack_blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{emoji} Paiement Partenaire* | {mode_tag}"}},
        {"type": "divider"},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*👤 Partenaire:*\n{partner_nom}"},
            {"type": "mrkdwn", "text": f"*💰 Montant:*\n{montant:.2f} EUR"},
            {"type": "mrkdwn", "text": f"*📊 Statut:*\n{statut.upper()}"},
            {"type": "mrkdwn", "text": f"*🆔 Transaction:*\n{payout_id or 'N/A'}"}
        ]},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"🕐 {timestamp} | <http://localhost:8765/admin.html|Dashboard>"}]}
    ]

    # Envoyer
    results = {}
    if config["telegram"]["enabled"] and config["telegram"]["notify_payout"]:
        results["telegram"] = _send_telegram(
            config["telegram"]["bot_token"],
            config["telegram"]["chat_id"],
            tg_message
        )
    if config["slack"]["enabled"] and config["slack"]["notify_payout"]:
        results["slack"] = _send_slack(
            config["slack"]["webhook_url"],
            slack_message,
            slack_blocks
        )

    return results


def notify_commission(partner_nom, montant, source="vente", total_solde=None):
    """Notifie qu'une commission a ete creditee a un partenaire."""
    config = load_config()
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    solde_msg = f"\n💰 <b>Solde total :</b> {total_solde:.2f} EUR" if total_solde else ""

    tg_message = f"""<b>💰 Commission creditée</b>

👤 <b>Partenaire :</b> {partner_nom}
💶 <b>Montant :</b> +{montant:.2f} EUR
📦 <b>Source :</b> {source}{solde_msg}
🕐 <b>Date :</b> {timestamp}

━━━━━━━━━━━━━━━━━
🔗 <a href='http://localhost:8765/admin.html'>Dashboard</a>"""

    slack_message = f"💰 Commission créditée à {partner_nom} : +{montant:.2f} EUR ({source})"
    slack_blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*💰 Commission créditée*"}},
        {"type": "divider"},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*👤 Partenaire:*\n{partner_nom}"},
            {"type": "mrkdwn", "text": f"*💶 Montant:*\n+{montant:.2f} EUR"},
            {"type": "mrkdwn", "text": f"*📦 Source:*\n{source}"}
        ]},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"🕐 {timestamp}"}]}
    ]

    results = {}
    if config["telegram"]["enabled"] and config["telegram"]["notify_commission"]:
        results["telegram"] = _send_telegram(config["telegram"]["bot_token"], config["telegram"]["chat_id"], tg_message)
    if config["slack"]["enabled"] and config["slack"]["notify_commission"]:
        results["slack"] = _send_slack(config["slack"]["webhook_url"], slack_message, slack_blocks)
    return results


def notify_threshold(partner_nom, montant, seuil):
    """Notifie qu'un partenaire a atteint le seuil de paiement."""
    config = load_config()
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")

    tg_message = f"""<b>🎯 Seuil de paiement atteint !</b>

👤 <b>Partenaire :</b> {partner_nom}
💰 <b>Solde :</b> {montant:.2f} EUR
🏁 <b>Seuil :</b> {seuil:.2f} EUR

👉 Le partenaire peut demander un reversement !
🔗 <a href='http://localhost:8765/admin.html'>Effectuer le paiement</a>"""

    slack_message = f"🎯 Seuil de paiement atteint ! {partner_nom} a {montant:.2f} EUR (seuil: {seuil:.2f} EUR)"
    slack_blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*🎯 Seuil de paiement atteint !*"}},
        {"type": "divider"},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*👤 Partenaire:*\n{partner_nom}"},
            {"type": "mrkdwn", "text": f"*💰 Solde:*\n{montant:.2f} EUR"},
            {"type": "mrkdwn", "text": f"*🏁 Seuil:*\n{seuil:.2f} EUR"}
        ]},
        {"type": "section", "text": {"type": "mrkdwn", "text": "👉 Le partenaire peut demander un reversement !"}}
    ]

    results = {}
    if config["telegram"]["enabled"] and config["telegram"]["notify_threshold"]:
        results["telegram"] = _send_telegram(config["telegram"]["bot_token"], config["telegram"]["chat_id"], tg_message)
    if config["slack"]["enabled"] and config["slack"]["notify_threshold"]:
        results["slack"] = _send_slack(config["slack"]["webhook_url"], slack_message, slack_blocks)
    return results


def notify_promo_post(platform, product_name, content_preview, url):
    """Notifie qu'un post promotionnel automatique a ete publie.

    Args:
        platform: plateforme de publication ("twitter", "linkedin", etc.)
        product_name: nom du produit promu
        content_preview: apercu du contenu (deja tronque par l'appelant)
        url: lien d'affiliation

    Returns:
        dict {"telegram": bool, "slack": bool}
    """
    config = load_config()
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")

    safe_preview = html.escape(content_preview)
    safe_product = html.escape(product_name)
    safe_url = html.escape(url, quote=True)

    tg_message = f"""<b>📢 Nouvelle Publication ({platform.title()})</b>

🛒 <b>Produit :</b> {safe_product}
📝 <b>Aperçu :</b> <i>"{safe_preview}"</i>
🕐 <b>Date :</b> {timestamp}

━━━━━━━━━━━━━━━━━
🔗 <a href='{safe_url}'>Lien Affilié</a>"""

    color = "#7c3aed"
    slack_message = f"📢 Nouvelle Publication ({platform.title()}) : {product_name}"
    slack_blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*📢 Nouvelle Publication ({platform.title()})*"}},
        {"type": "divider"},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*🛒 Produit:*\n{product_name}"},
            {"type": "mrkdwn", "text": f"*🔗 Lien:*\n<{url}|Voir le lien>"}
        ]},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*📝 Aperçu:*\n_{content_preview[:300]}_"}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"🕐 {timestamp} | Couleur marque: {color}"}]}
    ]

    results = {}
    if config["telegram"]["enabled"] and config["telegram"].get("notify_promo_post", True):
        if config["telegram"]["bot_token"] and config["telegram"]["chat_id"]:
            results["telegram"] = _send_telegram(
                config["telegram"]["bot_token"],
                config["telegram"]["chat_id"],
                tg_message
            )
        else:
            print("  [NOTIF] Telegram active mais sans token/chat_id")
            results["telegram"] = False
    if config["slack"]["enabled"] and config["slack"].get("notify_promo_post", True):
        if config["slack"]["webhook_url"]:
            results["slack"] = _send_slack(
                config["slack"]["webhook_url"],
                slack_message,
                slack_blocks
            )
        else:
            print("  [NOTIF] Slack active mais sans webhook")
            results["slack"] = False

    return results


def send_test(platform="all"):
    """Envoie une notification de test pour verifier la configuration."""
    config = load_config()
    results = {"telegram": False, "slack": False}

    test_msg = "🔔 *TEST NOTIFICATION*\n\n✅ Votre configuration de notifications Affilimax fonctionne correctement !\n\n📊 Vous recevrez des alertes pour :\n• Paiements aux partenaires\n• Commissions creditees\n• Seuils de paiement atteints\n\n─\nAffilimax - Notification automatique"

    if platform in ("all", "telegram"):
        if config["telegram"]["enabled"]:
            results["telegram"] = _send_telegram(
                config["telegram"]["bot_token"],
                config["telegram"]["chat_id"],
                test_msg.replace("*", "<b>").replace("\n", "<br/>")
            )
        else:
            print("  [NOTIF] Telegram non configure")

    if platform in ("all", "slack"):
        if config["slack"]["enabled"]:
            results["slack"] = _send_slack(
                config["slack"]["webhook_url"],
                test_msg,
                [{"type": "section", "text": {"type": "mrkdwn", "text": test_msg}}]
            )
        else:
            print("  [NOTIF] Slack non configure")

    return results


def verify_config():
    """Verifie la configuration et retourne l'etat."""
    config = load_config()
    return {
        "telegram": {
            "configured": bool(config["telegram"]["bot_token"] and config["telegram"]["chat_id"]),
            "enabled": config["telegram"]["enabled"],
            "chat_id": config["telegram"]["chat_id"][:8] + "..." if config["telegram"]["chat_id"] else None,
            "notify_payout": config["telegram"]["notify_payout"],
            "notify_commission": config["telegram"]["notify_commission"],
            "notify_threshold": config["telegram"]["notify_threshold"],
            "notify_promo_post": config["telegram"].get("notify_promo_post", True)
        },
        "slack": {
            "configured": bool(config["slack"]["webhook_url"]),
            "enabled": config["slack"]["enabled"],
            "webhook_url_preview": config["slack"]["webhook_url"][:25] + "..." if config["slack"]["webhook_url"] else None,
            "notify_payout": config["slack"]["notify_payout"],
            "notify_commission": config["slack"]["notify_commission"],
            "notify_threshold": config["slack"]["notify_threshold"],
            "notify_promo_post": config["slack"].get("notify_promo_post", True)
        }
    }
