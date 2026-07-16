#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Affilimax - Email Sender (Resend API)
=====================================
Envoie de VRAIS emails marketing avec les liens Amazon tagues confortbure07-21.
Utilise l'API Resend (gratuit: 100 emails/jour, 3000/mois).

Utilisation:
    python email_sender.py --status          # Voir les stats d'envoi
    python email_sender.py --send "Bose"     # Envoyer pour un produit specifique
    python email_sender.py --send-all        # Envoyer a tous les partenaires
    python email_sender.py --schedule        # Scheduler auto (1 email/heure)

Integration serveur:
    GET  /api/email/status      -> stats d'envoi
    POST /api/email/send        -> envoyer 1 email {product, to}
    POST /api/email/send-all    -> envoyer a tous les partenaires

Configuration (variables d'environnement):
    RESEND_API_KEY       -> cle API Resend (format: re_...)
    RESEND_FROM_EMAIL    -> expediteur (defaut: newsletter@affilimax.com)
    RESEND_REPLY_TO      -> reply-to (defaut: vide)
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
SENT_FILE = BASE_DIR / "email_sent.json"
PARTNERS_FILE = BASE_DIR / "partners.json"

# ==================== CONFIGURATION ====================

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "Affilimax <newsletter@affilimax.com>")
RESEND_REPLY_TO = os.environ.get("RESEND_REPLY_TO", "")

EMAIL_ENABLED = bool(RESEND_API_KEY)
EMAIL_DAILY_LIMIT = int(os.environ.get("EMAIL_DAILY_LIMIT", "95"))  # Marge sur les 100/jour

# Lazy import: ai_automator n'est charge qu'au premier appel de send_marketing_email
_ai_imports = None

def _get_ai_funcs():
    """Retourne (find_product, generate_email) depuis ai_automator (lazy load)."""
    global _ai_imports
    if _ai_imports is None:
        from ai_automator import find_product, generate_email
        _ai_imports = (find_product, generate_email)
    return _ai_imports

if not EMAIL_ENABLED:
    print("[EMAIL] RESEND_API_KEY absent. Mode simulation uniquement (pas d'envoi reel).")
else:
    print(f"[EMAIL] Resend configure - {EMAIL_DAILY_LIMIT} emails/jour max")


# ==================== STOCKAGE ENVOIS ====================

def load_sent_data():
    """Charge l'historique des emails envoyes."""
    try:
        with open(SENT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "total_sent": 0,
            "today_sent": 0,
            "today_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "history": []
        }


def save_sent_data(data):
    """Sauvegarde l'historique des emails envoyes."""
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _reset_daily_if_needed(data):
    """Reinitialise le compteur journalier si changement de jour."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if data.get("today_date") != today:
        data["today_sent"] = 0
        data["today_date"] = today
    return data


def record_sent_email(to_email, product_name, subject, status="sent", error=None):
    """Enregistre un email envoye dans l'historique."""
    data = load_sent_data()
    data = _reset_daily_if_needed(data)

    data["total_sent"] += 1
    data["today_sent"] += 1

    data["history"].insert(0, {
        "to": to_email,
        "product": product_name,
        "subject": subject,
        "status": status,
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    # Garder les 500 derniers
    if len(data["history"]) > 500:
        data["history"] = data["history"][:500]

    save_sent_data(data)
    return data


# ==================== RECIPIENTS ====================

def load_recipients():
    """Charge la liste des destinataires depuis partners.json."""
    try:
        with open(PARTNERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        recipients = []
        for p in data.get("partenaires", []):
            email = p.get("email", "").strip()
            nom = p.get("nom", "").strip()
            if email and "@" in email:
                recipients.append({"email": email, "nom": nom, "id": p.get("id", "")})
        return recipients
    except Exception:
        return []


# ==================== ENVOI EMAIL ====================

def send_email(to_email, to_name, subject, html_content, text_content=None):
    """Envoie un email via l'API Resend.

    Args:
        to_email: Adresse du destinataire
        to_name: Nom du destinataire
        subject: Sujet de l'email
        html_content: Contenu HTML
        text_content: Version texte (optionnel)

    Returns:
        dict: {"success": bool, "message": str, "id": str}
    """
    if not EMAIL_ENABLED:
        return {
            "success": False,
            "message": "RESEND_API_KEY non configuree. Mode simulation.",
            "simulated": True
        }

    # Verifier le quota journalier
    sent_data = load_sent_data()
    sent_data = _reset_daily_if_needed(sent_data)
    if sent_data["today_sent"] >= EMAIL_DAILY_LIMIT:
        return {
            "success": False,
            "message": f"Quota journalier atteint ({EMAIL_DAILY_LIMIT} emails). Reessayez demain."
        }

    # Construire le destinataire avec nom si dispo
    if to_name:
        to = f"{to_name} <{to_email}>"
    else:
        to = to_email

    try:
        import resend
        resend.api_key = RESEND_API_KEY

        params = {
            "from": RESEND_FROM_EMAIL,
            "to": [to],
            "subject": subject,
            "html": html_content,
        }

        if text_content:
            params["text"] = text_content

        if RESEND_REPLY_TO:
            params["reply_to"] = RESEND_REPLY_TO

        result = resend.Emails.send(params)

        email_id = result.get("id", "unknown")
        return {
            "success": True,
            "message": f"Email envoye a {to_email}",
            "id": email_id,
            "resend_response": result
        }

    except ImportError:
        return {
            "success": False,
            "message": "Module 'resend' non installe. pip install resend"
        }
    except Exception as e:
        error_msg = str(e)[:300]
        print(f"[EMAIL] Erreur envoi a {to_email}: {error_msg}")
        return {
            "success": False,
            "message": error_msg
        }


def build_email_html(product, email_content, recipient_name):
    """Construit le HTML complet d'un email marketing a partir du contenu genere.

    Args:
        product: dict produit (nom, prix, etc.)
        email_content: dict {sujet, contenu, lien}
        recipient_name: nom du destinataire

    Returns:
        tuple: (subject, html_content, text_content)
    """
    nom = product.get("nom", "Ce produit")
    prix = product.get("prix", "")
    lien = email_content.get("lien", "#")
    sujet = email_content.get("sujet", f"🔥 Decouvrez {nom}")
    contenu = email_content.get("contenu", "")

    # Nettoyer le contenu (enlever artefacts IA)
    contenu = contenu.replace("Lien:", "").replace("CTA:", "")

    # Salutation personnalisee
    if recipient_name:
        salutation = f"Bonjour {recipient_name},"
    else:
        salutation = "Bonjour,"

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#0d0d2b;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0d0d2b;">
<tr><td align="center" style="padding:20px 0;">

<!-- HEADER -->
<table width="600" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#141432,#1a1a4e);border-radius:12px 12px 0 0;">
<tr><td style="padding:30px 40px;text-align:center;">
<h1 style="color:#f0a500;font-size:28px;margin:0;">🚀 Affilimax</h1>
<p style="color:#a0a0cc;font-size:14px;margin:8px 0 0;">Les meilleurs deals Amazon, selectionnes pour vous</p>
</td></tr></table>

<!-- BODY -->
<table width="600" cellpadding="0" cellspacing="0" style="background-color:#141432;">
<tr><td style="padding:30px 40px;">

<p style="color:#e0e0f0;font-size:16px;line-height:1.6;margin:0 0 16px;">{salutation}</p>

<div style="color:#e0e0f0;font-size:15px;line-height:1.7;">
{contenu.replace(chr(10), '<br>')}
</div>

<!-- CTA BUTTON -->
<table cellpadding="0" cellspacing="0" style="margin:24px 0;">
<tr><td align="center" style="background:linear-gradient(135deg,#f0a500,#e69500);border-radius:8px;">
<a href="{lien}" style="display:inline-block;padding:14px 48px;color:#0d0d2b;font-size:16px;font-weight:bold;text-decoration:none;">
👉 Voir le produit sur Amazon
</a>
</td></tr></table>

<p style="color:#8080aa;font-size:13px;line-height:1.5;margin:16px 0 0;">
Prix : <strong style="color:#f0a500;">{prix} EUR</strong> sur Amazon
</p>

</td></tr></table>

<!-- FOOTER -->
<table width="600" cellpadding="0" cellspacing="0" style="background-color:#0d0d2b;border-radius:0 0 12px 12px;">
<tr><td style="padding:20px 40px;text-align:center;">
<p style="color:#606090;font-size:12px;margin:0;">
Cet email vous est envoye par <strong>Affilimax</strong>.<br>
Les prix affiches sont indicatifs et peuvent varier.<br>
En tant que Partenaire Amazon, nous realisons un benefice sur les achats remplissant les conditions requises.
</p>
</td></tr></table>

</td></tr></table>
</body>
</html>"""

    # Version texte
    text = f"{salutation}\n\n{contenu}\n\n👉 Voir le produit : {lien}\nPrix : {prix} EUR\n\n--\nL'equipe Affilimax"

    return sujet, html, text


def send_marketing_email(to_email, to_name, product_name=None):
    """Envoie un email marketing complet pour un produit.

    Args:
        to_email: Adresse du destinataire
        to_name: Nom du destinataire
        product_name: Nom du produit (optionnel, aleatoire si absent)

    Returns:
        dict: resultat de l'envoi
    """
    find_product, generate_email = _get_ai_funcs()

    # Trouver le produit
    product = find_product(product_name) if product_name else None
    if not product:
        return {"success": False, "message": "Produit introuvable"}

    # Generer le contenu email
    email_content = generate_email(product)
    if not email_content:
        return {"success": False, "message": "Impossible de generer le contenu de l'email"}

    # Construire le HTML
    subject, html, text = build_email_html(product, email_content, to_name)

    # Envoyer
    result = send_email(to_email, to_name, subject, html, text_content=text)

    # Enregistrer dans l'historique
    status = "sent" if result.get("success") else "failed"
    error = result.get("message") if not result.get("success") else None
    record_sent_email(to_email, product.get("nom", ""), subject, status=status, error=error)

    return {
        **result,
        "product": product.get("nom"),
        "subject": subject,
        "recipient": to_email
    }


def send_all(limit=None):
    """Envoie un email a tous les partenaires.

    Args:
        limit: Nombre max d'emails a envoyer (respecte le quota journalier)

    Returns:
        dict: resume de l'envoi
    """
    recipients = load_recipients()
    sent_data = load_sent_data()
    sent_data = _reset_daily_if_needed(sent_data)

    remaining = EMAIL_DAILY_LIMIT - sent_data["today_sent"]
    if remaining <= 0:
        return {
            "success": False,
            "message": f"Quota journalier epuise ({EMAIL_DAILY_LIMIT}/{EMAIL_DAILY_LIMIT})",
            "sent": 0, "failed": 0, "remaining": 0
        }

    if limit is not None:
        remaining = min(remaining, limit)

    if not recipients:
        return {"success": False, "message": "Aucun destinataire trouve dans partners.json", "sent": 0, "failed": 0}

    sent_count = 0
    failed_count = 0
    details = []

    for r in recipients[:remaining]:
        result = send_marketing_email(
            to_email=r["email"],
            to_name=r["nom"],
            product_name=None  # produit aleatoire par destinataire
        )
        details.append({
            "email": r["email"],
            "success": result.get("success"),
            "product": result.get("product", ""),
            "message": result.get("message", "")
        })

        if result.get("success"):
            sent_count += 1
        else:
            failed_count += 1

        # Pause pour eviter de surcharger l'API
        if not EMAIL_ENABLED:
            time.sleep(0.5)
        else:
            time.sleep(2)

    return {
        "success": True,
        "sent": sent_count,
        "failed": failed_count,
        "total_recipients": len(recipients),
        "details": details
    }


# ==================== STATS ====================

def get_status():
    """Retourne le statut du module d'envoi d'emails."""
    sent_data = load_sent_data()
    sent_data = _reset_daily_if_needed(sent_data)

    recipients = load_recipients()

    return {
        "email_enabled": EMAIL_ENABLED,
        "api_key_configured": bool(RESEND_API_KEY),
        "total_sent": sent_data["total_sent"],
        "today_sent": sent_data["today_sent"],
        "daily_limit": EMAIL_DAILY_LIMIT,
        "remaining_today": max(0, EMAIL_DAILY_LIMIT - sent_data["today_sent"]),
        "recipients_count": len(recipients),
        "recipients": [{"email": r["email"], "nom": r["nom"]} for r in recipients],
        "last_sent": sent_data["history"][0] if sent_data["history"] else None
    }


# ==================== CLI ====================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Affilimax - Email Sender (Resend API)")
    parser.add_argument("--status", action="store_true", help="Voir les stats d'envoi")
    parser.add_argument("--send", type=str, help="Envoyer email pour un produit specifique (nom ou slug)")
    parser.add_argument("--send-all", action="store_true", help="Envoyer a tous les partenaires")
    parser.add_argument("--to", type=str, help="Email du destinataire (avec --send)")
    parser.add_argument("--limit", type=int, help="Limite d'envois (avec --send-all)")
    parser.add_argument("--schedule", action="store_true", help="Scheduler automatique")

    args = parser.parse_args()

    if args.status:
        print(json.dumps(get_status(), indent=2, ensure_ascii=False))
        sys.exit(0)

    if args.send:
        email = args.to or input("Destinataire (email) : ").strip()
        if not email or "@" not in email:
            print("Email invalide")
            sys.exit(1)
        name = email.split("@")[0].capitalize()
        result = send_marketing_email(to_email=email, to_name=name, product_name=args.send)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0)

    if args.send_all:
        print(f"Envoi a tous les partenaires (limite: {args.limit or 'auto'})...")
        result = send_all(limit=args.limit)
        print(json.dumps({
            "sent": result["sent"],
            "failed": result["failed"],
            "total_recipients": result["total_recipients"]
        }, indent=2, ensure_ascii=False))
        sys.exit(0)

    if args.schedule:
        print("[EMAIL] Scheduler demarre (1 email toutes les heures)")
        try:
            while True:
                status = get_status()
                if status["remaining_today"] <= 0:
                    print("[EMAIL] Quota atteint. Attente du lendemain...")
                    time.sleep(3600)
                    continue
                recips = load_recipients()
                if not recips:
                    print("[EMAIL] Aucun destinataire. Attente...")
                    time.sleep(3600)
                    continue
                result = send_marketing_email(
                    to_email=recips[0]["email"],
                    to_name=recips[0].get("nom", "")
                )
                print(f"[EMAIL] Envoye: {result.get('success')} - {result.get('message')}")
                time.sleep(3600)  # 1 heure
        except KeyboardInterrupt:
            print("\n[EMAIL] Scheduler arrete.")
        sys.exit(0)

    parser.print_help()
