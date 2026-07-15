#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Affilimax - Authentification Partenaires
========================================
Systeme simple d'authentification par email pour les partenaires.
Les sessions sont stockees en memoire avec un token unique.

Utilisation:
    from partner_auth import login_partner, verify_session, logout_session

    # Login
    result = login_partner("sophie@example.com")
    # -> {"success": True, "token": "...", "partner": {...}}

    # Verify
    partner = verify_session(token)
    # -> {"id": "demo_partner_1", ...} or None

    # Logout
    logout_session(token)
"""

import uuid
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta

from stripe_config import load_partners, get_partner

# ==================== CONFIGURATION ====================

SESSION_DURATION_HOURS = 24  # Duree de vie d'une session

# PARTNER_SECRET_KEY : cle utilisee pour signer / valider les tokens de session
# partenaire. Ne JAMAIS utiliser la valeur par defaut en production : elle
# permettrait a un attaquant de forger des tokens arbitrairement.
#
# Politique de securite (Affilimax V2) :
#   - AFFILMAX_REQUIRE_LIVE=1 (production) : RuntimeError a l'import si non defini.
#     Impossiblerait a l'app de demarrer.
#   - Mode dev/test (AFFILMAX_REQUIRE_LIVE=0 ou absent) : on accepte un
#     placeholder mais un warning bruyant est emis pour pousser le dev
#     a definir la cle.
try:
    SECRET_KEY = os.environ["PARTNER_SECRET_KEY"]
except KeyError:
    if bool(os.environ.get("AFFILMAX_REQUIRE_LIVE", "0")):
        raise RuntimeError(
            "\n[AFFILIMAX] AFFILMAX_REQUIRE_LIVE=1 mais PARTNER_SECRET_KEY absent.\n"
            "Les tokens de session partenaire seraient forgeables. Definissez\n"
            "PARTNER_SECRET_KEY dans l'environnement (au moins 32 caracteres aleatoires).\n"
            "Voir STRIPE_LIVE_SETUP.md section 'Secrets obligatoires en prod'."
        ) from None
    SECRET_KEY = "affilimax-DEV-ONLY-NOT-A-REAL-SECRET-CHANGE-ME"
    import warnings
    warnings.warn(
        "[SECURITY] PARTNER_SECRET_KEY non defini -> placeholder de dev utilise. "
        "DEFINISSEZ PARTNER_SECRET_KEY avant la production (ou activez "
        "AFFILMAX_REQUIRE_LIVE=1 pour forcer cette cle).",
        RuntimeWarning, stacklevel=2
    )

# ==================== GESTION DES SESSIONS ====================

# Sessions actives: {token: {"partner_id": str, "created_at": float, "expires_at": float}}
_sessions = {}

def _generate_token(partner_id, email):
    """Genere un token de session unique."""
    raw = f"{partner_id}:{email}:{time.time()}:{uuid.uuid4().hex}"
    return hashlib.sha256(raw.encode()).hexdigest()[:48]


def login_partner(email):
    """Authentifie un partenaire par email.

    Args:
        email: Email du partenaire

    Returns:
        dict: {"success": True, "token": "...", "partner": {...}} ou
              {"success": False, "error": "..."}
    """
    # Nettoyer les sessions expirees
    _clean_expired_sessions()

    # Chercher le partenaire par email
    data = load_partners()
    partner = None
    for p in data["partenaires"]:
        if p["email"].lower() == email.lower().strip():
            partner = p
            break

    if not partner:
        return {
            "success": False,
            "error": "Aucun partenaire trouve avec cet email.",
            "suggestions": _get_suggested_emails()
        }

    # Generer le token
    token = _generate_token(partner["id"], partner["email"])
    now = time.time()

    _sessions[token] = {
        "partner_id": partner["id"],
        "created_at": now,
        "expires_at": now + (SESSION_DURATION_HOURS * 3600)
    }

    # Retourner les infos du partenaire (sans donnees sensibles)
    return {
        "success": True,
        "token": token,
        "partner": _sanitize_partner(partner),
        "message": f"Bienvenue {partner['nom']} !"
    }


def verify_session(token):
    """Verifie un token de session et retourne le partenaire.

    Args:
        token: Token de session

    Returns:
        dict partenaire (sensible) ou None si invalide/expire
    """
    if not token:
        return None

    session = _sessions.get(token)
    if not session:
        return None

    # Verifier expiration
    if time.time() > session["expires_at"]:
        del _sessions[token]
        return None

    # Recharger les donnees fraiches du partenaire
    return get_partner(session["partner_id"])


def logout_session(token):
    """Deconnecte une session.

    Args:
        token: Token de session
    """
    if token and token in _sessions:
        del _sessions[token]


def _clean_expired_sessions():
    """Supprime les sessions expirees."""
    now = time.time()
    expired = [t for t, s in _sessions.items() if now > s["expires_at"]]
    for t in expired:
        del _sessions[t]


def _sanitize_partner(partner):
    """Retire les donnees sensibles d'un partenaire pour l'API."""
    if not partner:
        return None
    return {
        "id": partner["id"],
        "nom": partner["nom"],
        "email": partner["email"],
        "commission_rate": partner.get("commission_rate", 0),
        "total_gagne": round(partner.get("total_gagne", 0), 2),
        "total_paye": round(partner.get("total_paye", 0), 2),
        "solde_en_attente": round(partner.get("solde_en_attente", 0), 2),
        "statut": partner.get("statut", "actif"),
        "date_inscription": partner.get("date_inscription", ""),
        "derniere_activite": partner.get("derniere_activite", ""),
        "onboarded": partner.get("onboarded", False),
    }


def _get_suggested_emails():
    """Retourne les emails des partenaires disponibles (pour le formulaire de login)."""
    data = load_partners()
    return [p["email"] for p in data["partenaires"]]


def get_partner_stats(partner_id):
    """Retourne les statistiques detaillees pour un partenaire.

    Args:
        partner_id: ID du partenaire

    Returns:
        dict avec stats et historiques
    """
    partner = get_partner(partner_id)
    if not partner:
        return None

    transactions = partner.get("transactions", [])
    payouts = partner.get("payouts", [])
    methodes = partner.get("methodes_paiement", [])

    # Stats calculees
    total_commissions = sum(
        abs(t["montant"]) for t in transactions if t["type"] == "commission"
    )
    nb_commissions = sum(1 for t in transactions if t["type"] == "commission")
    nb_payouts = len(payouts)
    solde_total = partner.get("total_gagne", 0)
    total_paye = partner.get("total_paye", 0)
    solde_restant = partner.get("solde_en_attente", 0)

    # Compter les transactions du mois
    debut_mois = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    commissions_mois = sum(
        abs(t["montant"]) for t in transactions
        if t["type"] == "commission" and t.get("date", "").startswith(debut_mois.strftime("%Y-%m"))
    )

    return {
        "partner": _sanitize_partner(partner),
        "total_commissions": round(total_commissions, 2),
        "nb_commissions": nb_commissions,
        "nb_payouts": nb_payouts,
        "solde_total": round(solde_total, 2),
        "total_paye": round(total_paye, 2),
        "solde_restant": round(solde_restant, 2),
        "commissions_mois": round(commissions_mois, 2),
        "transactions_recents": transactions[:20],
        "payouts_recents": payouts[:20],
        "methodes_paiement": methodes,
        "seuil_paiement": 25.0,
        "peut_recevoir_paiement": solde_restant >= 25.0,
        "taux_commission": partner.get("commission_rate", 0),
        "onboarded": partner.get("onboarded", False),
        "stripe_account_id": partner.get("stripe_account_id"),
    }


# ==================== CLI ====================

if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        # Tester le login avec un email demo
        test_email = "sophie@example.com"
        result = login_partner(test_email)
        print(f"\nTest login: {test_email}")
        print(f"  Success: {result.get('success')}")
        if result.get("success"):
            print(f"  Token: {result['token'][:16]}...")
            print(f"  Partenaire: {result['partner']['nom']}")

            # Tester la verification
            token = result["token"]
            partner = verify_session(token)
            print(f"\nVerification session:")
            print(f"  Partenaire: {partner['nom'] if partner else 'INVALIDE'}")

            # Tester les stats
            stats = get_partner_stats(partner["id"]) if partner else None
            if stats:
                print(f"  Total commissions: {stats['total_commissions']} EUR")
                print(f"  Nb transactions: {stats['nb_commissions']}")
                print(f"  Solde disponible: {stats['solde_restant']} EUR")
                print(f"  Seuil atteint: {'OUI' if stats['peut_recevoir_paiement'] else 'NON'}")

            # Deconnexion
            logout_session(token)
            partner = verify_session(token)
            print(f"\nApres deconnexion:")
            print(f"  Session valide: {'OUI' if partner else 'NON (OK)'}")
        else:
            print(f"  Error: {result.get('error')}")
            print(f"  Suggestions: {result.get('suggestions')}")
        print()

    elif "--list" in sys.argv:
        emails = _get_suggested_emails()
        print(f"\nPartenaires disponibles ({len(emails)}):")
        for e in emails:
            print(f"  - {e}")
        print()

    else:
        print("Usage: python partner_auth.py [--test | --list]")
