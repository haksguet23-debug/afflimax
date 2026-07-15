#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Affilimax - Peuple l'historique 7 jours de stats.json
======================================================
Genere une serie de 7 valeurs realistes (commissions / clics / conversions)
pour les 7 derniers jours, en s'alignant sur les totaux du jour actuel.

Convention d'ordre dans historique_7j :
    index 0 = il y a 7 jours  (le plus ancien)
    index 1 = il y a 6 jours
    ...
    index 5 = hier
    index 6 = aujourd'hui    (correspond EXACTEMENT a resume.*)

Logique de generation :
    - Tendance de croissance non-lineaire (les progres sont de plus en plus rapides)
    - Bruit realiste +/- 18% sur chaque jour (sauf aujourd'hui = valeur exacte)
    - Seed base sur la date du jour : meme jour = meme valeurs reproductibles
    - Chaque valeur est coherente : conversions <= clics et commissions ~ EPC * clics

Usage :
    python peuple_historique_7j.py              # Peuple stats.json
    python peuple_historique_7j.py --preview   # Affiche sans ecrire
    python peuple_historique_7j.py --simulate   # Force meme si aujourd'hui = 0
    python peuple_historique_7j.py --seed 42    # Seed fixe pour tests
"""

import argparse
import json
import math
import random
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
STATS_FILE = BASE_DIR / "stats.json"

# ==================== PROFILS DE CROISSANCE ====================

# Ratios relatifs au jour actuel (commissions, clics, conversions)
# Courbe de croissance en S : lente au debut, rapide au milieu, stable en haut
TRENDS = [
    (0.040, 0.045, 0.030),   # J-7  - debut de campagne
    (0.075, 0.080, 0.070),   # J-6
    (0.130, 0.140, 0.140),   # J-5
    (0.220, 0.230, 0.250),   # J-4
    (0.360, 0.380, 0.420),   # J-3  - acceleration
    (0.580, 0.610, 0.660),   # J-2
    (0.820, 0.840, 0.880),   # J-1  - hier (fort trending)
]
NOISE_PCT = 0.18  # +/- 18% de bruit


# ==================== FONCTIONS UTILITAIRES ====================

def day_seed(date: datetime) -> int:
    """Seed reproductible base sur la date du jour (meme jour = meme valeurs)."""
    return date.year * 10000 + date.month * 100 + date.day


def apply_noise(value: float, noise_pct: float) -> float:
    """Applique un bruit uniforme proportionnel."""
    if value == 0:
        return 0
    factor = 1.0 + random.uniform(-noise_pct, noise_pct)
    return value * factor


def ensure_coherent(commissions: float, clics: int, conversions: int) -> tuple:
    """Verifie et corrige la coherence metier entre les 3 metriques.

    Regles :
        - conversions <= clics (taux de conversion <= 100%)
        - commissions >= somme des commissions par conversion
        - EPC = commissions / clics (toujours > 0 si les 2 > 0)
    """
    # 1. conversions ne peut pas depasser clics
    if clics > 0 and conversions > clics:
        conversions = clics
    # 2. conversions >= 0
    conversions = max(0, conversions)
    # 3. commissions >= 0
    commissions = max(0.0, commissions)

    # 4. Si on a des donnees, garantir une EPC minimale realiste (~0.50 EUR)
    if clics > 0 and commissions > 0:
        epc_min = clics * 0.50
        if commissions < epc_min:
            commissions = round(epc_min, 2)

    return commissions, clics, conversions


def generate_history(
    current_commissions: float,
    current_clics: int,
    current_conversions: int,
    seed: int = None
) -> dict:
    """Genere les 7 derniers jours d'historique.

    Args:
        current_commissions: commissions aujourd'hui (resume.commissions_aujourdhui)
        current_clics: clics aujourd'hui
        current_conversions: conversions aujourd'hui
        seed: seed aleatoire (defaut = aujourd'hui)

    Returns:
        dict avec 'commissions', 'clics', 'conversions' (7 valeurs chacun)
    """
    if seed is not None:
        random.seed(seed)
    else:
        random.seed(day_seed(datetime.utcnow()))

    commissions_7j = []
    clics_7j = []
    conversions_7j = []

    # J-7 a J-1 (avec bruit)
    for tr_c, tr_cl, tr_cv in TRENDS[:-1]:
        c_raw = apply_noise(current_commissions * tr_c, NOISE_PCT)
        cl_raw = apply_noise(current_clics * tr_cl, NOISE_PCT)
        cv_raw = apply_noise(current_conversions * tr_cv, NOISE_PCT)

        c, cl, cv = ensure_coherent(round(c_raw, 2), int(cl_raw), int(cv_raw))
        commissions_7j.append(c)
        clics_7j.append(cl)
        conversions_7j.append(cv)

    # Aujourd'hui (J-0) : valeur exacte (pas de bruit, doit matcher resume)
    commissions_7j.append(round(current_commissions, 2))
    clics_7j.append(int(current_clics))
    conversions_7j.append(int(current_conversions))

    # Coherence finale aujourd'hui aussi
    today_c, today_cl, today_cv = ensure_coherent(
        commissions_7j[-1], clics_7j[-1], conversions_7j[-1]
    )
    commissions_7j[-1] = today_c
    clics_7j[-1] = today_cl
    conversions_7j[-1] = today_cv

    return {
        "commissions": commissions_7j,
        "clics": clics_7j,
        "conversions": conversions_7j
    }


def format_preview(current: dict, history: dict) -> str:
    """Formate un apercu lisible de l'historique genere."""
    lines = []
    lines.append("")
    lines.append("=" * 68)
    lines.append("  APERCU de l'historique 7 jours genere (J-7 -> Aujourd'hui)")
    lines.append("=" * 68)
    lines.append(f"  {'Date':<12} {'Commissions':>12} {'Clics':>8} {'Conv.':>8} {'TX':>7} {'EPC':>7}")
    lines.append("-" * 68)

    today = datetime.utcnow()
    for i in range(7):
        days_ago = 6 - i  # index 0 (J-7) -> days_ago=6 ; index 6 (today) -> days_ago=0
        date_label = "Aujourd'hui" if days_ago == 0 else f"J-{days_ago}"
        c = history["commissions"][i]
        cl = history["clics"][i]
        cv = history["conversions"][i]
        tx = (cv / cl * 100) if cl > 0 else 0.0
        epc = (c / cl) if cl > 0 else 0.0
        lines.append(
            f"  {date_label:<12} {c:>10.2f}€ {cl:>8} {cv:>8} {tx:>6.2f}% {epc:>6.2f}€"
        )

    lines.append("-" * 68)
    lines.append(f"  TOTAL 7j : {sum(history['commissions']):>10.2f}€  "
                 f"Clics: {sum(history['clics']):>5}  "
                 f"Conv: {sum(history['conversions']):>4}")
    lines.append("=" * 68)
    lines.append(f"  Valeurs du jour actuel prises comme cible :")
    lines.append(f"    commissions  = {current['commissions']:.2f} EUR")
    lines.append(f"    clics        = {current['clics']}")
    lines.append(f"    conversions  = {current['conversions']}")
    lines.append("")
    return "\n".join(lines)


# ==================== MAIN ====================

def load_stats() -> dict:
    """Charge stats.json."""
    if not STATS_FILE.exists():
        print(f"[ERREUR] Fichier introuvable : {STATS_FILE}")
        print("   Lance d'abord server.py au moins une fois pour generer stats.json.")
        sys.exit(1)
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[ERREUR] stats.json corrompu : {e}")
        sys.exit(1)


def save_stats(data: dict) -> None:
    """Sauvegarde stats.json en preservant l'ordre des cles."""
    if "historique_7j" not in data:
        data["historique_7j"] = {
            "commissions": [0, 0, 0, 0, 0, 0, 0],
            "clics": [0, 0, 0, 0, 0, 0, 0],
            "conversions": [0, 0, 0, 0, 0, 0, 0]
        }
    data["historique_7j"]["commissions"] = data["historique_7j"].get("commissions", [0]*7)
    data["historique_7j"]["clics"] = data["historique_7j"].get("clics", [0]*7)
    data["historique_7j"]["conversions"] = data["historique_7j"].get("conversions", [0]*7)

    # Mettre a jour le timestamp
    data["timestamp"] = datetime.utcnow().isoformat() + "Z"

    # Backup avant ecriture
    backup = STATS_FILE.with_suffix(".json.bak")
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            backup.write_text(f.read(), encoding="utf-8")
    except Exception:
        pass  # backup optionnel

    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(
        description="Peuple l'historique 7 jours de stats.json avec des donnees realistes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python peuple_historique_7j.py              # Peuple stats.json (defaut)
  python peuple_historique_7j.py --preview   # Affiche sans modifier
  python peuple_historique_7j.py --simulate   # Force meme si aujourd'hui = 0
  python peuple_historique_7j.py --seed 42    # Seed fixe (pour les tests)
        """
    )
    parser.add_argument("--preview", action="store_true",
                        help="Affiche un apercu sans modifier stats.json")
    parser.add_argument("--simulate", action="store_true",
                        help="Force la generation meme si stats du jour sont a 0")
    parser.add_argument("--seed", type=int, default=None,
                        help="Seed fixe (sinon = date du jour)")
    args = parser.parse_args()

    print("Affilimax - Peuple l'historique 7 jours")
    print("=" * 68)

    # Charger stats
    data = load_stats()
    resume = data.get("resume", {})
    current = {
        "commissions": float(resume.get("commissions_aujourdhui", 0)),
        "clics": int(resume.get("clics_aujourdhui", 0)),
        "conversions": int(resume.get("conversions_aujourdhui", 0))
    }

    # Verifier qu'on a des donnees du jour
    total_today = current["commissions"] + current["clics"] + current["conversions"]

    if total_today == 0 and not args.simulate:
        print()
        print("[ERREUR] Les stats du jour sont a 0 (commissions=0, clics=0, conversions=0).")
        print("   Pour generer un historique credible, le script a besoin de valeurs")
        print("   cibles realistes pour aujourd'hui.")
        print()
        print("Options :")
        print("   1. Lance server.py (avec AUTO_TRAFFIC=1 ou via injections admin.html)")
        print("      pour avoir des donneesAujourd'hui non nulles, puis relance ce script.")
        print("   2. Utilise --simulate pour forcer avec des valeurs simulees (5758/2172/199).")
        print()
        sys.exit(1)

    if args.simulate and total_today == 0:
        print("[INFO] Mode --simulate : utilisation de valeurs simulees pour aujourd'hui")
        print("       (commissions=5758.99€, clics=2172, conversions=199)")
        current = {
            "commissions": 5758.99,
            "clics": 2172,
            "conversions": 199
        }

    # Generer
    history = generate_history(
        current["commissions"],
        current["clics"],
        current["conversions"],
        seed=args.seed
    )

    # Apercu
    print(format_preview(current, history))

    if args.preview:
        print("[PREVIEW] Aucune modification ecrite sur stats.json")
        return

    # Verifier que la valeur du jour correspond a resume
    last_c = history["commissions"][-1]
    last_cl = history["clics"][-1]
    last_cv = history["conversions"][-1]

    match_c = abs(last_c - current["commissions"]) < 0.01
    match_cl = last_cl == current["clics"]
    match_cv = last_cv == current["conversions"]

    if not (match_c and match_cl and match_cv):
        print("[ALERTE] La valeur 'aujourd\'hui' de l'historique ne correspond pas a resume.")
        print(f"  Attendu : commissions={current['commissions']:.2f} clics={current['clics']} conv={current['conversions']}")
        print(f"  Genere   : commissions={last_c:.2f} clics={last_cl} conv={last_cv}")
        if not args.simulate:
            print("  Annulation de l'ecriture pour eviter une incoherence.")
            sys.exit(2)

    # Ecrire
    data["historique_7j"] = history
    save_stats(data)

    print(f"[OK] Historique 7 jours ecrit dans {STATS_FILE.name}")
    print(f"     (backup cree : {STATS_FILE.name}.bak si possible)")
    print()


if __name__ == "__main__":
    main()
