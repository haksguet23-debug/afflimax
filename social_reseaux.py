#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Affilimax - Generateur de Posts Reseaux Sociaux
================================================
Genere des posts uniques et engages pour chaque produit.
Plus de 170 posts prets a etre copies-colles.

Usage:
    python social_reseaux.py              # Affiche tous les posts
    python social_reseaux.py --count      # Compte les posts
    python social_reseaux.py --twitter    # Posts Twitter uniquement
    python social_reseaux.py --linkedin   # Posts LinkedIn uniquement
    python social_reseaux.py --facebook   # Posts Facebook uniquement
    python social_reseaux.py --email      # Emails marketing
    python social_reseaux.py --blog       # Articles blog
    python social_reseaux.py --random 3   # 3 posts aleatoires
"""

import json
import os
import random
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LIENS_FILE = os.path.join(BASE_DIR, "liens_affiliation.json")

SITE_URL = "https://affilmax.render.com"

def load_products():
    try:
        with open(LIENS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [p for p in data.get("produits", []) if p.get("actif")]
    except Exception:
        return []

def slugify(text):
    return text.lower().replace(" ", "-").replace("'", "").replace(":", "").replace(",", "")[:30]

PRODUITS = load_products()

# ==================== GENERATEURS DE POSTS ====================

def generer_tweets():
    """Genere des tweets uniques pour chaque produit (5 par produit = 150 tweets)."""
    tweets = []
    templates_court = [
        lambda p: f"🔥 {p['nom']} a {p['prix']}€ ! \n{p['note_moyenne']}/5 ★ par {p['avis_total']} clients\n👉 {SITE_URL}/go/{slugify(p['nom'])}?src=twitter\n#bonplan #Amazon",
        lambda p: f"🏆 {p['categorie']} : {p['nom']}\n{p['note_moyenne']}/5 ★ {p['avis_total']} avis\n💰 Commission: {p['commission_pct']}%\n👉 {SITE_URL}/go/{slugify(p['nom'])}?src=twitter",
        lambda p: f"🎯 TESTE ET APPROUVE : {p['nom']}\n{p['note_moyenne']}/5 ★ - {p['avis_total']} clients satisfaits\n{p['prix']}€ sur {p['plateforme']}\n👉 {SITE_URL}/go/{slugify(p['nom'])}?src=twitter",
        lambda p: f"💥 {p['nom']} en promo !\nMeilleur {p['categorie']} du moment\n{p['note_moyenne']}/5 ★ ({p['avis_total']} avis)\n👉 {SITE_URL}/go/{slugify(p['nom'])}?src=twitter",
        lambda p: f"📦 NOUVEAU : {p['nom']}\n{p['categorie']} | {p['note_moyenne']}/5 ★\n{p['prix']}€ - Comm: {p['commission_euro']}€\n👉 {SITE_URL}/go/{slugify(p['nom'])}?src=twitter\n#shopping"
    ]
    for p in PRODUITS:
        for tpl in templates_court:
            tweets.append(tpl(p))
    return tweets

def generer_linkedin():
    """Genere des posts LinkedIn professionnels (2 par produit = 60 posts)."""
    posts = []
    for p in PRODUITS:
        nom = p['nom']
        posts.append({
            "titre": f"Pourquoi recommander le {nom} ?",
            "contenu": f"""**{nom}** - {p['categorie']} | Note: {p['note_moyenne']}/5 ★

Apres analyse approfondie, voici les points forts de ce produit :

⭐ Note: {p['note_moyenne']}/5 ★ ({p['avis_total']} avis clients)
💰 Prix: {p['prix']}€ | Commission: {p['commission_euro']}€

**Caracteristiques cles :**
{p['caracteristiques'][0] if p.get('caracteristiques') else 'Qualite professionnelle'}
{p['caracteristiques'][1] if len(p.get('caracteristiques',[])) > 1 else 'Rapport qualite-prix'}
{p['caracteristiques'][2] if len(p.get('caracteristiques',[])) > 2 else 'Fiable et durable'}

👉 Decouvrir : {SITE_URL}/go/{slugify(nom)}?src=linkedin

#Affiliation #{p['categorie'].replace(' ','')} #Business #Marketing #AvisClient #Amazon""",
        })
        posts.append({
            "titre": f"Analyse : le marche des {p['categorie']}s en 2026",
            "contenu": f"""**Analyse du marche : {p['categorie']}s en 2026**

Le **{nom}** se positionne comme un leader dans sa categorie avec :

📊 Chiffres cles :
• Note: {p['note_moyenne']}/5 ★
• Avis clients: {p['avis_total']}
• Prix: {p['prix']}€
• Commission partenaire: {p['commission_euro']}€

Pourquoi c'est interessant pour les affiliateurs :
✅ Produit deja populaire (preuve sociale)
✅ Commission competitive
✅ Marque reconnue ({p['plateforme']})

👉 Lien vers le produit : {SITE_URL}/go/{slugify(nom)}?src=linkedin

#{p['categorie'].replace(' ','')} #Analyse #Affiliation #Business2026""",
        })
    return posts

def generer_facebook():
    """Genere des posts Facebook engages (1 par produit = 30 posts)."""
    posts = []
    for p in PRODUITS:
        nom = p['nom']
        posts.append(f"""📢 NOUVEAUTE DANS NOTRE SELECTION !

🔥 {nom}

{p['description'][:200]}

⭐ Note : {p['note_moyenne']}/5 ★ | 👥 {p['avis_total']} avis verifies
💰 Prix : {p['prix']}€ | Commission : {p['commission_euro']}€

Caracteristiques :
✅ {p['caracteristiques'][0] if p.get('caracteristiques') else 'Qualite pro'}
✅ {p['caracteristiques'][1] if len(p.get('caracteristiques',[])) > 1 else 'Prix competitif'}
✅ {p['caracteristiques'][2] if len(p.get('caracteristiques',[])) > 2 else 'Excellent rapport qualite-prix'}

🔗 Decouvrir : {SITE_URL}/go/{slugify(nom)}?src=facebook

#Affiliation #{p['categorie']} #Amazon #BonPlan #AvisClient""")
    return posts

def generer_emails():
    """Genere des templates d'emails marketing (2 par produit = 60 emails)."""
    emails = []
    prenoms = ["Amis", "Cher abonne", "Chers membres", "Bonjour"]
    for p in PRODUITS:
        nom = p['nom']
        prenom = random.choice(prenoms)
        emails.append({
            "objet": f"{nom} : {p['prix']}€ - Notre recommandation du jour",
            "corps": f"""{prenom},

Nous avons selectionne pour vous un produit qui sort du lot :

**{nom}**
{p['description'][:200]}

---
📊 En resume :
- Note : {p['note_moyenne']}/5 ★
- Avis : {p['avis_total']} clients
- Prix : {p['prix']}€
- Commission : {p['commission_euro']}€
- Plateforme : {p['plateforme']}

Ce que les clients en disent :
"Excellent rapport qualite-prix" - Note {p['note_moyenne']}/5

👉 Voir le produit : {SITE_URL}/go/{slugify(nom)}?src=email

L'equipe Affilimax

---
Pour vous desabonner : [lien de desabonnement]"""
        })
        emails.append({
            "objet": f"🔥 Offre speciale : {nom} a decouvrir",
            "corps": f"""{prenom},

Nous avons une offre qui pourrait vous interesser !

**{nom}** - {p['categorie']}

Pourquoi ce produit ?
{p['description'][:250]}

---
Caracteristiques :
• {p['caracteristiques'][0] if p.get('caracteristiques') else 'Qualite pro'}
• {p['caracteristiques'][1] if len(p.get('caracteristiques',[])) > 1 else 'Prix competitif'}
• {p['caracteristiques'][2] if len(p.get('caracteristiques',[])) > 2 else 'Rapport qualite-prix'}

Ne manquez pas cette opportunite !

👉 {SITE_URL}/go/{slugify(nom)}?src=email

Bien cordialement,
L'equipe Affilimax

---
Si vous ne souhaitez plus recevoir nos emails : [desabonnement]"""
        })
    return emails

def generer_blog():
    """Genere des intros d'articles blog (1 par produit = 30 articles)."""
    articles = []
    for p in PRODUITS:
        nom = p['nom']
        slug = slugify(nom)
        articles.append({
            "titre": f"{nom} : Test et Avis Complet ({datetime.now().year})",
            "meta_desc": f"Découvrez notre test complet du {nom}. Note: {p['note_moyenne']}/5 ★, {p['avis_total']} avis clients, prix: {p['prix']}€. Vaut-il le coup ?",
            "intro": f"""# {nom} : Test et Avis Complet

## Introduction

Vous cherchez un {p['categorie']} et vous avez entendu parler du **{nom}** ?
Dans cet article, nous allons vous donner notre avis honnete, analyser ses points forts et vous aider a decider s'il est fait pour vous.

## En bref

- **Prix** : {p['prix']}€
- **Note** : {p['note_moyenne']}/5 ★
- **Avis clients** : {p['avis_total']}
- **Plateforme** : {p['plateforme']}

## Pourquoi choisir le {nom} ?

{random.choice([p['caracteristiques'][0] if p.get('caracteristiques') else 'Qualite pro'])}.
{random.choice([p['caracteristiques'][1] if len(p.get('caracteristiques',[])) > 1 else 'Prix abordable'])}.
{random.choice([p['caracteristiques'][2] if len(p.get('caracteristiques',[])) > 2 else 'Fiable'])}

## Verdict

Le **{nom}** est un excellent choix pour quiconque cherche un {p['categorie']} de qualite.
Son rapport qualite-prix a {p['prix']}€ est difficile a battre !

{"> Note : " + str(p['note_moyenne']) + "/5 - " + ("Exceptionnel" if p['note_moyenne'] >= 4.5 else "Excellent" if p['note_moyenne'] >= 4 else "Tres bon") + " !"}

## Ou acheter ?

Le meilleur prix est sur Amazon : [{nom}]({SITE_URL}/go/{slug}?src=blog)

---
*Article redige par l'equipe Affilimax. Contient des liens d'affiliation.*"""
        })
    return articles


# ==================== MAIN ====================

if __name__ == "__main__":
    all_tweets = generer_tweets()
    all_linkedin = generer_linkedin()
    all_facebook = generer_facebook()
    all_emails = generer_emails()
    all_blog = generer_blog()

    total = len(all_tweets) + len(all_linkedin) + len(all_facebook) + len(all_emails) + len(all_blog)

    if "--count" in sys.argv:
        print(f"📊 GENERATION DE CONTENUS :")
        print(f"  Twitter/X:     {len(all_tweets)} posts")
        print(f"  LinkedIn:      {len(all_linkedin)} posts")
        print(f"  Facebook:      {len(all_facebook)} posts")
        print(f"  Email:         {len(all_emails)} emails")
        print(f"  Blog:          {len(all_blog)} articles")
        print(f"  ─────────────────────")
        print(f"  TOTAL:         {total} contenus")
        sys.exit(0)

    if "--random" in sys.argv:
        count = int(sys.argv[sys.argv.index("--random") + 1]) if len(sys.argv) > sys.argv.index("--random") + 1 else 3
        all_content = []
        for t in all_tweets:
            all_content.append(("twitter", t))
        for p in all_linkedin:
            all_content.append(("linkedin", p))
        for p in all_facebook:
            all_content.append(("facebook", p))
        for e in all_emails:
            all_content.append(("email", e))
        for b in all_blog:
            all_content.append(("blog", b))
        sample = random.sample(all_content, min(count, len(all_content)))
        for plat, cont in sample:
            print(f"\n{'='*55}")
            print(f"  {plat.upper()} - POST ALEATOIRE")
            print('='*55)
            if isinstance(cont, dict):
                print(f"  TITRE: {cont.get('titre','')}")
                print(f"  CONTENU: {cont.get('contenu','')[:500]}")
            else:
                print(f"  {cont[:500]}")
        sys.exit(0)

    print(f"""
{'='*55}
    AFFILIMAX - {total} CONTENUS RESEAUX SOCIAUX
    Generes le {datetime.now().strftime('%d/%m/%Y %H:%M')}
{'='*55}
""")

    if "--twitter" in sys.argv:
        print(f"\n{'='*55}")
        print(f"  TWITTER/X - {len(all_tweets)} POSTS")
        print('='*55)
        for i, t in enumerate(all_tweets, 1):
            print(f"\n--- TWEET {i} ---")
            print(t)
        sys.exit(0)

    if "--linkedin" in sys.argv:
        print(f"\n{'='*55}")
        print(f"  LINKEDIN - {len(all_linkedin)} POSTS")
        print('='*55)
        for i, p in enumerate(all_linkedin, 1):
            print(f"\n--- LINKEDIN {i} ---")
            print(f"TITRE: {p['titre']}")
            print(p['contenu'])
        sys.exit(0)

    if "--facebook" in sys.argv:
        print(f"\n{'='*55}")
        print(f"  FACEBOOK - {len(all_facebook)} POSTS")
        print('='*55)
        for i, p in enumerate(all_facebook, 1):
            print(f"\n--- FACEBOOK {i} ---")
            print(p)
        sys.exit(0)

    if "--email" in sys.argv:
        print(f"\n{'='*55}")
        print(f"  EMAIL - {len(all_emails)} EMAILS")
        print('='*55)
        for i, e in enumerate(all_emails, 1):
            print(f"\n--- EMAIL {i} ---")
            print(f"OBJET: {e['objet']}")
            print(e['corps'])
        sys.exit(0)

    if "--blog" in sys.argv:
        print(f"\n{'='*55}")
        print(f"  BLOG - {len(all_blog)} ARTICLES")
        print('='*55)
        for i, b in enumerate(all_blog, 1):
            print(f"\n--- ARTICLE {i} ---")
            print(f"TITRE: {b['titre']}")
            print(f"META: {b['meta_desc']}")
            print(f"INTRO: {b['intro'][:500]}...")
        sys.exit(0)

    # Mode par defaut : tout afficher
    print(f"\n{'='*55}")
    print(f"  TWITTER/X - {len(all_tweets)} POSTS")
    print('='*55)
    for i, t in enumerate(all_tweets, 1):
        print(f"\n--- TWEET {i} ---")
        print(t)
        if i >= 10:
            print(f"\n... et {len(all_tweets) - 10} autres tweets. Utilisez --twitter pour tous les voir.")
            break

    print(f"\n{'='*55}")
    print(f"  LINKEDIN - {len(all_linkedin)} POSTS")
    print('='*55)
    for i, p in enumerate(all_linkedin, 1):
        print(f"\n--- LINKEDIN {i} ---")
        print(f"TITRE: {p['titre']}")
        print(p['contenu'])
        if i >= 4:
            print(f"\n... et {len(all_linkedin) - 4} autres posts. Utilisez --linkedin pour tous les voir.")
            break

    print(f"\n{'='*55}")
    print(f"  FACEBOOK - {len(all_facebook)} POSTS")
    print('='*55)
    for i, p in enumerate(all_facebook, 1):
        print(f"\n--- FACEBOOK {i} ---")
        print(p)
        if i >= 4:
            print(f"\n... et {len(all_facebook) - 4} autres posts. Utilisez --facebook pour tous.")
            break

    print(f"\n{'='*55}")
    print(f"  EMAIL - {len(all_emails)} EMAILS")
    print('='*55)
    for i, e in enumerate(all_emails, 1):
        print(f"\n--- EMAIL {i} ---")
        print(f"OBJET: {e['objet']}")
        print(e['corps'][:300] + "...")
        if i >= 4:
            print(f"\n... et {len(all_emails) - 4} autres emails. Utilisez --email pour tous.")
            break

    print(f"\n{'='*55}")
    print(f"  BLOG - {len(all_blog)} ARTICLES")
    print('='*55)
    for i, b in enumerate(all_blog, 1):
        print(f"\n--- ARTICLE {i} ---")
        print(f"TITRE: {b['titre']}")
        print(f"META: {b['meta_desc']}")
        print(f"INTRO: {b['intro'][:300]}...")
        if i >= 4:
            print(f"\n... et {len(all_blog) - 4} autres articles. Utilisez --blog pour tous.")
            break

    print(f"\n{'='*55}")
    print(f"  TOTAL: {total} contenus generes pour {len(PRODUITS)} produits")
    print(f"  Utilisez --count pour le denombrement")
    print(f"  Utilisez --random N pour N posts aleatoires")
    print('='*55)
