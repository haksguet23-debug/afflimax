"""
Affilimax - Configuration Stripe Connect
========================================
Gère l'intégration Stripe pour les reversements de commissions aux partenaires.

Mode DEMO: Fonctionne sans clés Stripe réelles (simulation locale).
Mode LIVE: Active Stripe Connect quand STRIPE_SECRET_KEY est définie.
"""

import os
import json
import time
import uuid
from datetime import datetime, timedelta

# ==================== CONFIGURATION ====================

# Stripe API keys (optionnelles)
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# Mode demo si pas de clé Stripe
DEMO_MODE = not STRIPE_SECRET_KEY

# ==================== AFFILMAX_REQUIRE_LIVE ====================
# Si AFFILMAX_REQUIRE_LIVE=1, le mode DEMO est INTERDIT : on refuse de
# demarrer sans cle Stripe reelle. Utiliser en production pour empecher
# tout fallback silencieux vers le mode DEMO.
AFFILMAX_REQUIRE_LIVE = os.environ.get("AFFILMAX_REQUIRE_LIVE", "0") == "1"
if AFFILMAX_REQUIRE_LIVE and DEMO_MODE:
    raise RuntimeError(
        "\n[AFFILIMAX] AFFILMAX_REQUIRE_LIVE=1 mais STRIPE_SECRET_KEY absent.\n"
        "Mode DEMO INTERDIT en production. Definissez STRIPE_SECRET_KEY\n"
        "(sk_test_... ou sk_live_...) dans l'environnement avant de demarrer.\n"
        "Voir STRIPE_LIVE_SETUP.md section 'AFFILMAX_REQUIRE_LIVE'."
    )

# Fichier de stockage des partenaires
PARTNERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "partners.json")

# Taux de commission par défaut (%)
DEFAULT_COMMISSION_RATE = 12.5
# Seuil de paiement minimum (EUR)
MIN_PAYOUT_THRESHOLD = 25.0
# Délai de paiement (jours après la fin du mois)
PAYOUT_DELAY_DAYS = 30

# ==================== CONFIG STRIPE CONNECT (LIVE) ====================
# Defauts pour la creation de comptes Connect Express FR

STRIPE_DEFAULT_COUNTRY = os.environ.get("STRIPE_DEFAULT_COUNTRY", "FR")  # ISO 3166-1 alpha-2
STRIPE_DEFAULT_CURRENCY = os.environ.get("STRIPE_DEFAULT_CURRENCY", "eur").lower()
STRIPE_DEFAULT_BUSINESS_TYPE = os.environ.get("STRIPE_DEFAULT_BUSINESS_TYPE", "individual")  # individual|company
PLATFORM_FEE_PERCENT = float(os.environ.get("PLATFORM_FEE_PERCENT", "0"))  # 0 = pas de fee plateforme (virements directs)
STRIPE_BASE_URL = os.environ.get("AFFILMAX_BASE_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "http://localhost:8765"

# ==================== INIT STRIPE ====================

stripe = None
if not DEMO_MODE:
    try:
        import stripe as stripe_lib
        stripe = stripe_lib
        stripe.api_key = STRIPE_SECRET_KEY
        print(f"[STRIPE] Mode LIVE - Stripe Connect actif")
    except ImportError:
        print("[STRIPE] Module 'stripe' non installé. Mode DEMO activé.")
        DEMO_MODE = True

if DEMO_MODE:
    print("[STRIPE] Mode DEMO - Les paiements sont simulés")

# ==================== GESTION DES PARTENAIRES ====================

def load_partners():
    """Charge la liste des partenaires."""
    try:
        with open(PARTNERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return init_partners()

def init_partners():
    """Crée un fichier partenaires initial avec des données de démonstration."""
    now = datetime.utcnow().isoformat() + "Z"
    partners = {
        "timestamp": now,
        "partenaires": [
            {
                "id": "demo_partner_1",
                "nom": "Sophie Martin",
                "email": "sophie@example.com",
                "stripe_account_id": None,
                "onboarded": False,
                "commission_rate": 12.5,
                "total_gagne": 0.0,
                "total_paye": 0.0,
                "solde_en_attente": 0.0,
                "statut": "actif",
                "date_inscription": now,
                "derniere_activite": now,
                "methodes_paiement": [],
                "payouts": []
            },
            {
                "id": "demo_partner_2",
                "nom": "Thomas Dubois",
                "email": "thomas@example.com",
                "stripe_account_id": None,
                "onboarded": False,
                "commission_rate": 15.0,
                "total_gagne": 0.0,
                "total_paye": 0.0,
                "solde_en_attente": 0.0,
                "statut": "actif",
                "date_inscription": now,
                "derniere_activite": now,
                "methodes_paiement": [],
                "payouts": []
            },
            {
                "id": "demo_partner_3",
                "nom": "Emma Bernard",
                "email": "emma@example.com",
                "stripe_account_id": None,
                "onboarded": False,
                "commission_rate": 10.0,
                "total_gagne": 0.0,
                "total_paye": 0.0,
                "solde_en_attente": 0.0,
                "statut": "actif",
                "date_inscription": now,
                "derniere_activite": now,
                "methodes_paiement": [],
                "payouts": []
            }
        ]
    }
    save_partners(partners)
    return partners

def save_partners(data):
    """Sauvegarde les données partenaires."""
    with open(PARTNERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_partner(partner_id):
    """Récupère un partenaire par son ID."""
    data = load_partners()
    for p in data["partenaires"]:
        if p["id"] == partner_id:
            return p
    return None

def update_partner(partner_id, updates):
    """Met à jour un partenaire."""
    data = load_partners()
    for p in data["partenaires"]:
        if p["id"] == partner_id:
            p.update(updates)
            p["derniere_activite"] = datetime.utcnow().isoformat() + "Z"
            save_partners(data)
            return p
    return None

def add_commission_to_partner(partner_id, amount_eur, source="commission"):
    """Ajoute une commission au solde d'un partenaire."""
    data = load_partners()
    for p in data["partenaires"]:
        if p["id"] == partner_id:
            p["total_gagne"] = round(p["total_gagne"] + amount_eur, 2)
            p["solde_en_attente"] = round(p["solde_en_attente"] + amount_eur, 2)
            p["derniere_activite"] = datetime.utcnow().isoformat() + "Z"
            # Ajouter une transaction
            if "transactions" not in p:
                p["transactions"] = []
            p["transactions"].insert(0, {
                "id": f"tx_{uuid.uuid4().hex[:8]}",
                "type": "commission",
                "montant": round(amount_eur, 2),
                "source": source,
                "date": datetime.utcnow().isoformat() + "Z",
                "statut": "en_attente"
            })
            if len(p["transactions"]) > 100:
                p["transactions"] = p["transactions"][:100]
            save_partners(data)
            return p["solde_en_attente"]
    return None

# ==================== STRIPE CONNECT (MODE REEL) ====================

def create_connect_account(partner_id, email, nom, country=None, currency=None, business_type=None):
    """Crée un compte Stripe Connect pour un partenaire (mode réel uniquement).

    Args:
        partner_id: ID interne Affilimax du partenaire
        email: email du partenaire (utilise pour Stripe)
        nom: raison sociale / nom complet
        country: code pays ISO 3166-1 alpha-2 (defaut = STRIPE_DEFAULT_COUNTRY = FR)
        currency: code devise ISO 4217 minuscules (defaut = STRIPE_DEFAULT_CURRENCY = eur)
        business_type: "individual" ou "company" (defaut = STRIPE_DEFAULT_BUSINESS_TYPE)
    """
    if DEMO_MODE or not stripe:
        return create_demo_onboarding(partner_id, email, nom)

    country = (country or STRIPE_DEFAULT_COUNTRY).upper()
    currency = (currency or STRIPE_DEFAULT_CURRENCY).lower()
    business_type = business_type or STRIPE_DEFAULT_BUSINESS_TYPE

    try:
        account = stripe.Account.create(
            type="express",
            country=country,
            email=email,
            business_type=business_type,
            business_profile={
                "name": nom,
                "mcc": "5969",  # Direct Marketing - Other
                "url": STRIPE_BASE_URL,
            },
            capabilities={
                "transfers": {"requested": True},
            },
            metadata={
                "affilmax_partner_id": partner_id,
                "platform": "affilimax",
            },
        )
        # Generer le lien d'onboarding (URLs derives de STRIPE_BASE_URL)
        link = stripe.AccountLink.create(
            account=account.id,
            refresh_url=f"{STRIPE_BASE_URL}/admin.html?reauth={partner_id}",
            return_url=f"{STRIPE_BASE_URL}/admin.html?onboarded={partner_id}",
            type="account_onboarding",
        )
        return {
            "success": True,
            "account_id": account.id,
            "onboarding_url": link.url,
            "details_submitted": False,
            "country": country,
            "currency": currency,
            "business_type": business_type,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def regenerate_onboarding_link(stripe_account_id, partner_id):
    """Regenere un lien d'onboarding pour un compte existant (refresh apres abandon).

    Args:
        stripe_account_id: ID du compte Connect (acct_...)
        partner_id: ID interne Affilimax (pour les URLs retour)

    Returns:
        dict avec success + onboarding_url, ou success=False + error
    """
    if DEMO_MODE or not stripe:
        return {"success": False, "error": "Mode DEMO"}

    try:
        link = stripe.AccountLink.create(
            account=stripe_account_id,
            refresh_url=f"{STRIPE_BASE_URL}/admin.html?reauth={partner_id}",
            return_url=f"{STRIPE_BASE_URL}/admin.html?onboarded={partner_id}",
            type="account_onboarding",
        )
        return {"success": True, "onboarding_url": link.url}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_partner_stripe_status(stripe_account_id):
    """Recupere le statut actuel d'un compte Connect chez Stripe.

    Returns:
        dict avec: exists, details_submitted, charges_enabled, payouts_enabled,
                  transfers_capability, requirements_currently_due, country, default_currency
        ou {success: False, error: ...} si echec
    """
    if DEMO_MODE or not stripe:
        return {"exists": False, "mode": "demo", "message": "Pas de acces Stripe en mode DEMO"}

    try:
        acc = stripe.Account.retrieve(stripe_account_id)
        transfers_cap = acc.get("capabilities", {}).get("transfers", "inactive")
        reqs = acc.get("requirements", {}) or {}
        return {
            "success": True,
            "exists": True,
            "details_submitted": acc.details_submitted,
            "charges_enabled": acc.charges_enabled,
            "payouts_enabled": acc.payouts_enabled,
            "transfers_capability": transfers_cap,
            "transfers_active": transfers_cap == "active",
            "requirements_currently_due": reqs.get("currently_due", []),
            "requirements_past_due": reqs.get("past_due", []),
            "country": acc.get("country"),
            "default_currency": acc.get("default_currency"),
            "email": acc.get("email"),
            "business_profile_name": acc.get("business_profile", {}).get("name"),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def stripe_health_check():
    """Test rapide de la connexion Stripe (retourne balance + mode).

    Returns:
        dict avec mode ("demo"|"live"|"test"), available_balance, error
    """
    if not STRIPE_SECRET_KEY:
        return {"mode": "demo", "enabled": False, "message": "STRIPE_SECRET_KEY non defini"}
    if not stripe:
        return {"mode": "demo", "enabled": False, "message": "Module stripe non importe"}

    is_live = STRIPE_SECRET_KEY.startswith("sk_live_")
    is_test = STRIPE_SECRET_KEY.startswith("sk_test_")
    mode = "live" if is_live else ("test" if is_test else "unknown")

    try:
        balance = stripe.Balance.retrieve()
        return {
            "mode": mode,
            "enabled": True,
            "available": [
                {"currency": b.currency.upper(), "amount_eur": b.amount / 100}
                for b in balance.available
            ],
            "pending": [
                {"currency": b.currency.upper(), "amount_eur": b.amount / 100}
                for b in balance.pending
            ],
            "livemode": balance.livemode,
            "default_country": STRIPE_DEFAULT_COUNTRY,
            "default_currency": STRIPE_DEFAULT_CURRENCY.upper(),
        }
    except Exception as e:
        return {"mode": mode, "enabled": True, "error": str(e)}

def create_payout_to_partner(partner_id, amount_eur, idempotency_key=None):
    """Effectue un paiement vers un partenaire (mode réel).

    Args:
        partner_id: ID interne Affilimax
        amount_eur: montant en EUR (min 25.00)
        idempotency_key: cle d'idempotence pour eviter les doublons sur retry reseau.
            Si non fournie, generee automatiquement (partner_id + amount + minute).
    """
    if DEMO_MODE or not stripe:
        return create_demo_payout(partner_id, amount_eur)

    partner = get_partner(partner_id)
    if not partner:
        return {"success": False, "error": "Partenaire introuvable"}
    if not partner.get("stripe_account_id"):
        return {"success": False, "error": "Partenaire non connecté à Stripe"}
    if partner["solde_en_attente"] < amount_eur:
        return {"success": False, "error": "Solde insuffisant"}

    # Pre-check capability 'transfers' (evite de creer un transfer qui echoue)
    try:
        account = stripe.Account.retrieve(partner["stripe_account_id"])
        transfers_cap = account.get("capabilities", {}).get("transfers")
        if transfers_cap != "active":
            return {
                "success": False,
                "error": f"Capacité 'transfers' non active (statut: {transfers_cap})",
                "details_submitted": account.details_submitted,
                "requirements_currently_due": (account.get("requirements") or {}).get("currently_due", []),
                "needs_reonboarding": not account.details_submitted,
            }
    except Exception as e:
        return {"success": False, "error": f"Verification du compte impossible: {e}"}

    try:
        amount_cents = int(round(amount_eur * 100))
        # Idempotency key : partner + amount + minute (evite double paiement si retry)
        if not idempotency_key:
            minute_ts = int(datetime.utcnow().timestamp() // 60)
            idempotency_key = f"affilmax-payout-{partner_id}-{round(amount_eur, 2)}-{minute_ts}"

        transfer_params = {
            "amount": amount_cents,
            "currency": STRIPE_DEFAULT_CURRENCY,
            "destination": partner["stripe_account_id"],
            "description": f"Commission Affilimax - {partner['nom']}",
            "metadata": {
                "affilmax_partner_id": partner_id,
                "affilmax_amount_eur": str(round(amount_eur, 2)),
            },
        }
        transfer = stripe.Transfer.create(**transfer_params, idempotency_key=idempotency_key)
        # Notifier
        _notify_payout_completed(partner, amount_eur, transfer.status, transfer.id, "live")

        # Generer la facture PDF
        facture_path = None
        try:
            from invoice_generator import generate_invoice
            payout_record = {
                "id": transfer.id,
                "montant": round(amount_eur, 2),
                "devise": "EUR",
                "date_creation": datetime.utcnow().isoformat() + "Z",
                "statut": transfer.status,
                "mode": "live",
                "description": f"Reversement commissions - {partner['nom']}"
            }
            facture_path = generate_invoice(partner, payout_record)
            if facture_path:
                print(f"  [FACTURE] Facture generee: {facture_path}")
        except ImportError:
            pass
        except Exception as e:
            print(f"  [FACTURE] Erreur: {e}")

        return {
            "success": True,
            "transfer_id": transfer.id,
            "amount": amount_eur,
            "currency": STRIPE_DEFAULT_CURRENCY,
            "status": transfer.status,
            "idempotency_key": idempotency_key,
            "facture": facture_path
        }
    except stripe.error.IdempotencyError as e:
        # IdempotencyError : une requete identique est deja en cours ou traitee
        return {
            "success": False,
            "error": "Cette requete a deja ete traitee (idempotency)",
            "idempotency_key": idempotency_key,
            "details": str(e),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

# ==================== NOTIFICATIONS ====================

def _notify_payout_completed(partner, amount, statut, payout_id, mode):
    """Envoie les notifications apres un paiement."""
    try:
        from notifications import notify_payout, notify_threshold
        
        # Notifier le paiement
        notify_payout(
            partner_nom=partner["nom"],
            montant=amount,
            statut=statut,
            payout_id=payout_id,
            mode=mode
        )
        
        # Verifier le seuil pour le solde restant
        solde_restant = partner.get("solde_en_attente", 0) - amount
        if solde_restant >= MIN_PAYOUT_THRESHOLD:
            notify_threshold(
                partner_nom=partner["nom"],
                montant=solde_restant,
                seuil=MIN_PAYOUT_THRESHOLD
            )
    except ImportError:
        pass  # Module notifications non disponible
    except Exception as e:
        print(f"[NOTIF] Erreur notification: {e}")

# ==================== MODE DEMO ====================

def create_demo_onboarding(partner_id, email, nom):
    """Simule l'onboarding Stripe en mode demo."""
    demo_account_id = f"acct_demo_{uuid.uuid4().hex[:12]}"
    update_partner(partner_id, {
        "stripe_account_id": demo_account_id,
        "onboarded": True,
        "stripe_onboarding_date": datetime.utcnow().isoformat() + "Z"
    })
    return {
        "success": True,
        "account_id": demo_account_id,
        "onboarding_url": None,
        "details_submitted": True,
        "demo": True,
        "message": f"Partenaire {nom} connecté en mode DEMO (ID: {demo_account_id})"
    }

def create_demo_payout(partner_id, amount_eur):
    """Simule un paiement en mode demo."""
    partner = get_partner(partner_id)
    if not partner:
        return {"success": False, "error": "Partenaire introuvable"}
    if not partner.get("onboarded"):
        return {"success": False, "error": "Partenaire non connecté. Faites d'abord l'onboarding."}
    if partner["solde_en_attente"] < amount_eur:
        return {"success": False, "error": f"Solde insuffisant ({partner['solde_en_attente']:.2f} EUR disponible, {amount_eur:.2f} EUR demandé)"}
    if amount_eur < MIN_PAYOUT_THRESHOLD:
        return {"success": False, "error": f"Montant minimum de paiement: {MIN_PAYOUT_THRESHOLD:.2f} EUR"}

    payout_id = f"po_demo_{uuid.uuid4().hex[:12]}"

    # Mettre à jour les soldes du partenaire
    new_solde = round(partner["solde_en_attente"] - amount_eur, 2)
    new_total_paye = round(partner["total_paye"] + amount_eur, 2)

    payout_record = {
        "id": payout_id,
        "partner_id": partner_id,
        "montant": round(amount_eur, 2),
        "devise": "EUR",
        "date_creation": datetime.utcnow().isoformat() + "Z",
        "date_fin": (datetime.utcnow() + timedelta(days=3)).isoformat() + "Z",
        "statut": "completed",
        "mode": "demo",
        "description": f"Reversement commissions - {partner['nom']}"
    }

    update_partner(partner_id, {
        "solde_en_attente": new_solde,
        "total_paye": new_total_paye
    })

    # Ajouter le payout à l'historique
    data = load_partners()
    for p in data["partenaires"]:
        if p["id"] == partner_id:
            if "payouts" not in p:
                p["payouts"] = []
            p["payouts"].insert(0, payout_record)
            if len(p["payouts"]) > 100:
                p["payouts"] = p["payouts"][:100]
            # Ajouter une transaction
            if "transactions" not in p:
                p["transactions"] = []
            p["transactions"].insert(0, {
                "id": f"tx_{uuid.uuid4().hex[:8]}",
                "type": "payout",
                "montant": round(amount_eur, 2),
                "source": payout_id,
                "date": datetime.utcnow().isoformat() + "Z",
                "statut": "completed"
            })
            if len(p["transactions"]) > 100:
                p["transactions"] = p["transactions"][:100]
            break
    save_partners(data)

    # Notifier
    _notify_payout_completed(partner, amount_eur, "completed", payout_id, "demo")

    # Generer la facture PDF
    facture_path = None
    try:
        from invoice_generator import generate_invoice
        facture_path = generate_invoice(
            partner=partner,
            payout=payout_record,
            company=None  # utilise les valeurs par defaut
        )
        if facture_path:
            print(f"  [FACTURE] Facture generee: {facture_path}")
            # Ajouter le chemin de la facture au payout
            payout_record["facture"] = facture_path
    except ImportError:
        pass  # Module invoice_generator non disponible
    except Exception as e:
        print(f"  [FACTURE] Erreur generation facture: {e}")

    return {
        "success": True,
        "payout_id": payout_id,
        "amount": round(amount_eur, 2),
        "currency": "EUR",
        "status": "completed",
        "demo": True,
        "facture": facture_path,
        "message": f"Paiement de {amount_eur:.2f} EUR effectué vers {partner['nom']} (mode DEMO)"
    }

def get_dashboard_stats():
    """Retourne les statistiques globales des paiements."""
    data = load_partners()
    total_gagne = sum(p["total_gagne"] for p in data["partenaires"])
    total_paye = sum(p["total_paye"] for p in data["partenaires"])
    total_en_attente = sum(p["solde_en_attente"] for p in data["partenaires"])
    partenaires_actifs = sum(1 for p in data["partenaires"] if p.get("onboarded"))
    partenaires_total = len(data["partenaires"])

    # Compter les payouts récents
    all_payouts = []
    for p in data["partenaires"]:
        for po in p.get("payouts", []):
            all_payouts.append(po)
    all_payouts.sort(key=lambda x: x.get("date_creation", ""), reverse=True)

    return {
        "total_gagne": round(total_gagne, 2),
        "total_paye": round(total_paye, 2),
        "total_en_attente": round(total_en_attente, 2),
        "partenaires_actifs": partenaires_actifs,
        "partenaires_total": partenaires_total,
        "payouts_recents": all_payouts[:20],
        "demo_mode": DEMO_MODE,
        "stripe_publishable_key": STRIPE_PUBLISHABLE_KEY or None
    }
