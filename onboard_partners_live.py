#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Affilimax - Migration Stripe Connect (LIVE)
============================================
Cree en masse des comptes Stripe Connect Express pour les partenaires
listes dans partners.json (mode LIVE uniquement).

Securite :
  - Refuse par defaut les partenaires avec email @example.com (demo)
  - Refuse de tourner si STRIPE_SECRET_KEY commence par sk_test_ (sans --allow-test)
  - Mode --dry-run par defaut pour visualiser avant de creer
  - Cree un backup partners.json.bak avant modification

Usage :
    # 1. Voir ce qui sera fait (par defaut)
    python onboard_partners_live.py

    # 2. Specifier un seul partenaire
    python onboard_partners_live.py --partner-id demo_partner_1

    # 3. Inclure les partenaires demo (avec @example.com)
    python onboard_partners_live.py --include-demo

    # 4. Forcer la creation (le mode dry-run doit etre desactive explicitement)
    python onboard_partners_live.py --apply

    # 5. Forcer en mode test Stripe (pour tester sans depenser d'argent)
    python onboard_partners_live.py --apply --allow-test
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
PARTNERS_FILE = BASE_DIR / "partners.json"

# Emails consideres comme demo (ne pas onboarder en LIVE par defaut)
DEMO_EMAIL_PATTERNS = ("@example.com", "@example.org", "@example.net", "@test.com", "@demo.local")

# ==================== HELPERS ====================

def load_partners():
    with open(PARTNERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_partners(data):
    with open(PARTNERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def backup_partners():
    """Cree une copie de sauvegarde avant modification."""
    if not PARTNERS_FILE.exists():
        return None
    backup = PARTNERS_FILE.with_suffix(".json.bak")
    backup.write_text(PARTNERS_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    return backup

def is_demo_email(email):
    return any(email.lower().endswith(p) for p in DEMO_EMAIL_PATTERNS)

def get_partners_to_onboard(data, partner_id=None, include_demo=False):
    """Filtre les partenaires a onboarder."""
    partners = []
    for p in data.get("partenaires", []):
        if partner_id and p["id"] != partner_id:
            continue
        if p.get("stripe_account_id") and p.get("onboarded"):
            continue  # Deja fait et complete
        if not include_demo and is_demo_email(p.get("email", "")):
            continue
        partners.append(p)
    return partners

def print_section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)

# ==================== MAIN ====================

def main():
    parser = argparse.ArgumentParser(
        description="Affilimax - Onboarding Stripe Connect Express en lot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--apply", action="store_true",
                        help="Applique reellement les creations (defaut = dry-run)")
    parser.add_argument("--partner-id", type=str, default=None,
                        help="Onboarder uniquement ce partenaire (par ID)")
    parser.add_argument("--include-demo", action="store_true",
                        help="Inclure les partenaires avec @example.com (DEMO)")
    parser.add_argument("--allow-test", action="store_true",
                        help="Autoriser une cle API Stripe test (sk_test_...)")
    args = parser.parse_args()

    print_section("Affilimax - Migration Stripe Connect LIVE")
    mode = "APPLY" if args.apply else "DRY-RUN (aucune modification)"
    print(f"Mode     : {mode}")
    print(f"Fichier  : {PARTNERS_FILE.name}")

    # ==================== VERIFICATIONS PREALABLES ====================
    print_section("1. Verification de la configuration")

    # Verifier STRIPE_SECRET_KEY
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not stripe_key:
        print("  [ERREUR] STRIPE_SECRET_KEY non defini.")
        print("            -> Definir la variable d'environnement puis relancer.")
        print("            -> Render.com : Dashboard > Environment > Add Env Var")
        sys.exit(1)

    if stripe_key.startswith("sk_test_") and not args.allow_test:
        print("  [ATTENTION] STRIPE_SECRET_KEY commence par sk_test_ (MODE TEST)")
        print("               -> Pour creer de VRAIS comptes Connect, il faut sk_live_...")
        print("               -> Utilisez --allow-test pour tester sans depenser.")
        sys.exit(1)
    elif stripe_key.startswith("sk_live_"):
        print("  [OK]       STRIPE_SECRET_KEY : sk_live_... (MODE LIVE)")
    elif stripe_key.startswith("sk_test_"):
        print("  [INFO]     STRIPE_SECRET_KEY : sk_test_... (MODE TEST - --allow-test force)")
    else:
        print(f"  [WARN]     Format de cle Stripe non reconnu : {stripe_key[:12]}...")

    if not os.environ.get("STRIPE_WEBHOOK_SECRET"):
        print("  [WARN]     STRIPE_WEBHOOK_SECRET non defini (recommandé pour valider les webhooks)")

    # Importer stripe_config
    try:
        import stripe_config
        print(f"  [OK]       stripe_config charge : mode = {'LIVE' if not stripe_config.DEMO_MODE else 'DEMO'}")
        print(f"  [INFO]     Pays par defaut : {stripe_config.STRIPE_DEFAULT_COUNTRY}")
        print(f"  [INFO]     Devise par defaut : {stripe_config.STRIPE_DEFAULT_CURRENCY.upper()}")
        if stripe_config.DEMO_MODE:
            print("  [ERREUR] stripe_config est en mode DEMO meme avec STRIPE_SECRET_KEY defini.")
            print(f"            -> Verifier que la cle est bien lue (cle: {stripe_key[:12]}...)")
            sys.exit(1)
    except ImportError as e:
        print(f"  [ERREUR] Impossible d'importer stripe_config : {e}")
        sys.exit(1)

    # Verifier le sdk stripe
    if not stripe_config.stripe:
        print("  [ERREUR] Module 'stripe' Python non disponible.")
        print("            -> pip install stripe (devrait deja etre requis.txt)")
        sys.exit(1)

    # ==================== HEALTH CHECK ====================
    print_section("2. Test de connexion Stripe")
    health = stripe_config.stripe_health_check()
    if "error" in health:
        print(f"  [ERREUR] Connexion Stripe echouee : {health['error']}")
        sys.exit(1)
    print(f"  [OK]    Mode     : {health.get('mode')}")
    print(f"  [OK]    Balance  : {health.get('available', [])}")
    print(f"  [OK]    Livemode : {health.get('livemode')}")

    # ==================== LISTER LES PARTENAIRES ====================
    print_section("3. Analyse des partenaires")
    data = load_partners()
    all_partners = data.get("partenaires", [])
    print(f"  Total partenaires          : {len(all_partners)}")
    print(f"  Deja onboardes (live)      : {sum(1 for p in all_partners if p.get('onboarded'))}")
    print(f"  Jamais onboardes           : {sum(1 for p in all_partners if not p.get('stripe_account_id'))}")
    print(f"  Emails @example.com (demo) : {sum(1 for p in all_partners if is_demo_email(p.get('email', '')))}")

    targets = get_partners_to_onboard(data, partner_id=args.partner_id, include_demo=args.include_demo)

    if not targets:
        print()
        print("  [INFO] Aucun partenaire a onboarder avec les criteres actuels.")
        if not args.include_demo:
            print("         -> Utilisez --include-demo pour inclure les partenaires demo.")
        if not args.partner_id:
            print(f"         -> Tous les partenaires valides sont deja onboardes.")
        sys.exit(0)

    print()
    print(f"  Cibles a onboarder : {len(targets)}")
    for p in targets:
        status_label = "DEMO" if is_demo_email(p["email"]) else "REEL"
        onboarded = p.get("onboarded", False)
        has_acct = bool(p.get("stripe_account_id"))
        flags = []
        if onboarded: flags.append("onboarded")
        if has_acct: flags.append("has_acct")
        flag_str = f" [{','.join(flags)}]" if flags else ""
        print(f"    - {p['id']:<25} {p['nom']:<30} {p['email']:<35} [{status_label}]{flag_str}")

    if not args.apply:
        print()
        print("  [DRY-RUN] Aucune modification effectuee.")
        print("             Relancer avec --apply pour creer reellement les comptes Stripe Connect.")
        print()
        print("  Pour un seul partenaire : --partner-id <id> --apply")
        print("  Pour inclure les DEMO   : --include-demo --apply")
        sys.exit(0)

    # ==================== CONFIRMATION ====================
    if stripe_key.startswith("sk_live_"):
        print()
        print("  [CONFIRMATION REQUISE]")
        print(f"  Vous allez creer {len(targets)} comptes Stripe Connect EN MODE LIVE.")
        print(f"  Cela consommera du quota et necessitera que chaque partenaire complete le KYC.")
        confirm = input("  Tapez 'OUI' (en majuscules) pour confirmer : ")
        if confirm.strip() != "OUI":
            print("  [ANNULE] Operation annulee par l'utilisateur.")
            sys.exit(1)

    # ==================== BACKUP + CREATION ====================
    print_section("4. Creation des comptes Stripe Connect Express")

    backup_path = backup_partners()
    if backup_path:
        print(f"  [INFO] Backup cree : {backup_path.name}")

    results = []
    for p in targets:
        print()
        print(f"  Traitement de {p['id']} ({p['nom']}) ...")
        result = stripe_config.create_connect_account(
            partner_id=p["id"],
            email=p["email"],
            nom=p["nom"],
        )
        result["partner_id"] = p["id"]
        result["partner_nom"] = p["nom"]
        results.append(result)

        if result.get("success"):
            print(f"    [OK] Compte cree : {result['account_id']}")
            print(f"    [OK] URL onboarding : {result.get('onboarding_url', 'N/A')[:80]}...")
            # Mettre a jour le partenaire dans partners.json
            for pp in data["partenaires"]:
                if pp["id"] == p["id"]:
                    pp["stripe_account_id"] = result["account_id"]
                    pp["stripe_onboarding_country"] = result.get("country")
                    pp["stripe_onboarding_currency"] = result.get("currency")
                    pp["stripe_onboarding_date"] = None  # Pas encore complete, KYC a faire
                    pp["derniere_activite"] = datetime.utcnow().isoformat() + "Z"
                    break
        else:
            print(f"    [ERREUR] {result.get('error', 'Inconnue')}")

    save_partners(data)
    print()
    print(f"  [OK] partners.json mis a jour")

    # ==================== RAPPORT FINAL ====================
    print_section("RESUME")
    success_count = sum(1 for r in results if r.get("success"))
    error_count = len(results) - success_count
    print(f"  Comptes crees       : {success_count}")
    print(f"  Erreurs             : {error_count}")
    print()

    if success_count > 0:
        print("  ACTIONS REQUISES :")
        print("  -----------------")
        print("  1. Chaque partenaire doit completer le KYC Stripe en cliquant")
        print("     sur son lien d'onboarding (envoyez par email ou Slack).")
        print("  2. Si un partenaire abandonne, regenerer son lien :")
        print("       python onboard_partners_live.py --partner-id <id>")
        print("     OU via API : POST /api/stripe/regonboard/<id>")
        print("  3. Le webhook account.updated mettra automatiquement")
        print("     onboarded=True quand le KYC sera complete.")
        print()
        print("  URLS D'ONBOARDING :")
        for r in results:
            if r.get("success") and r.get("onboarding_url"):
                print(f"    {r['partner_id']:<25} {r['partner_nom']:<30} {r['onboarding_url']}")


if __name__ == "__main__":
    main()
