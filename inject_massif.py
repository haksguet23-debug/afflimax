#!/usr/bin/env python3
"""Injecte 200 clics et 50 conversions directement dans stats.json."""
import json, random, time, os, sys
from datetime import datetime

STATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stats.json")
LIENS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "liens_affiliation.json")

SOURCES = ["SEO_organique", "reseaux_sociaux", "email_marketing", "publicite_payante", "referencement_direct"]
WEIGHTS = [0.30, 0.25, 0.20, 0.15, 0.10]

def load_products():
    try:
        with open(LIENS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("produits", [])
    except: return []

def main():
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    products = load_products()
    if not products:
        print("Erreur: aucun produit dans liens_affiliation.json")
        sys.exit(1)

    active = [p for p in products if p.get("actif")]
    now = datetime.utcnow()

    print("=" * 50)
    print("  INJECTION MASSIVE - 200 clics + 50 conversions")
    print("=" * 50)

    # --- 200 CLICS ---
    print("\n[1/2] Injection de 200 clics...")
    for i in range(200):
        data["resume"]["clics_aujourdhui"] += 1
        src = random.choices(SOURCES, weights=WEIGHTS, k=1)[0]
        data["sources_trafic"][src] = data["sources_trafic"].get(src, 0) + 1
        hour = now.hour
        data["performance_horaire"]["clics"][hour] += 1
        prod = random.choice(active)
        for camp in data["top_campagnes"]:
            if camp["nom"] == prod["nom"]:
                camp["clics"] += 1
                break
        data["activite_recente"].insert(0, {
            "type": "clic", "produit": prod["nom"], "plateforme": prod["plateforme"],
            "source": src, "timestamp": now.isoformat() + "Z"
        })
        if (i+1) % 50 == 0:
            print(f"  {i+1}/200 clics...")

    # --- 50 CONVERSIONS ---
    print("\n[2/2] Injection de 50 conversions...")
    total_comm = 0.0
    total_ca = 0.0
    for i in range(50):
        prod = random.choice(active)
        commission = prod["commission_euro"]
        price = prod["prix"]
        total_comm += commission
        total_ca += price

        data["resume"]["conversions_aujourdhui"] += 1
        data["resume"]["commissions_aujourdhui"] = round(data["resume"]["commissions_aujourdhui"] + commission, 2)
        data["resume"]["ca_genere"] = round(data["resume"]["ca_genere"] + price, 2)

        hour = now.hour
        data["performance_horaire"]["commissions"][hour] = round(data["performance_horaire"]["commissions"][hour] + commission, 2)

        for camp in data["top_campagnes"]:
            if camp["nom"] == prod["nom"]:
                camp["conversions"] += 1
                camp["commissions"] = round(camp["commissions"] + commission, 2)
                camp["progression"] = min(100, camp["progression"] + random.randint(1, 4))
                break

        data["activite_recente"].insert(0, {
            "type": "vente", "produit": prod["nom"], "plateforme": prod["plateforme"],
            "montant": commission, "prix_vente": price, "timestamp": now.isoformat() + "Z"
        })
        if (i+1) % 10 == 0:
            print(f"  {i+1}/50 conversions...")

    if data["resume"]["clics_aujourdhui"] > 0:
        data["resume"]["epc"] = round(data["resume"]["commissions_aujourdhui"] / data["resume"]["clics_aujourdhui"], 2)
        data["resume"]["taux_conversion"] = round(data["resume"]["conversions_aujourdhui"] / data["resume"]["clics_aujourdhui"] * 100, 2)

    if len(data["activite_recente"]) > 100:
        data["activite_recente"] = data["activite_recente"][:100]

    data["timestamp"] = now.isoformat() + "Z"
    data["statut_plateforme"]["derniere_synchro"] = now.isoformat() + "Z"

    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 50)
    print("  INJECTION TERMINEE !")
    print("=" * 50)
    s = data["resume"]
    print(f"  Clics       : {s['clics_aujourdhui']}")
    print(f"  Conversions : {s['conversions_aujourdhui']}")
    print(f"  Commissions : {s['commissions_aujourdhui']:.2f} EUR")
    print(f"  CA genere   : {s['ca_genere']:.2f} EUR")
    print(f"  EPC         : {s['epc']:.2f} EUR")
    print(f"  Taux conv.  : {s['taux_conversion']:.2f}%")
    print(f"  Commission injectee : +{total_comm:.2f} EUR")
    print("=" * 50)

if __name__ == "__main__":
    main()
