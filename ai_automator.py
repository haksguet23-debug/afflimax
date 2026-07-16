#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Affilimax - Automatisation IA Dual-Provider (Groq + Gemini)
===========================================================
Genere du contenu frais pour tous les reseaux sociaux + blog + emails
en utilisant 2 API gratuites en cascade :
  1. Groq (Llama 3.3 70B, ~30 req/min)
  2. Google Gemini (gemini-2.0-flash, ~15 req/min)
  3. Fallback statique (social_reseaux.py)

Cela DOUBLE le quota d'IA gratuit !

Utilisation:
    python ai_automator.py --tweets    # Genere 5 tweets sur un produit aleatoire
    python ai_automator.py --all       # Genere tout type de contenu
    python ai_automator.py --product "SSD Samsung"  # Pour un produit specifique

Integration dans le serveur:
    /api/ai/generate?type=tweets&count=5
    /api/ai/generate?type=linkedin&product=ssd-samsung-t7-shield
"""

import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
LIENS_FILE = BASE_DIR / "liens_affiliation.json"

# Import du generateur statique pour fallback
from social_reseaux import slugify, SITE_URL
from social_reseaux import generer_tweets as static_tweets
from social_reseaux import generer_linkedin as static_linkedin
from social_reseaux import generer_facebook as static_facebook
from social_reseaux import generer_blog as static_blog
from social_reseaux import generer_emails as static_emails

# ==================== CONFIGURATION ====================

# --- Provider 1: Groq (OpenAI-compatible, gratuit) ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = os.environ.get("AI_MODEL", "llama-3.3-70b-versatile")

# --- Provider 2: Google Gemini (gratuit) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

# --- Etat des providers ---
GROQ_ENABLED = False
GEMINI_ENABLED = False

# Initialiser Groq
groq_client = None
if bool(GROQ_API_KEY):
    try:
        from openai import OpenAI
        groq_client = OpenAI(
            base_url=GROQ_BASE_URL,
            api_key=GROQ_API_KEY
        )
        GROQ_ENABLED = True
        print(f"[IA] Groq connecte - modele: {GROQ_MODEL}")
    except ImportError:
        print("[IA] Module 'openai' non installe.")
else:
    print("[IA] GROQ_API_KEY absent.")

# Initialiser Gemini
gemini_model_obj = None
if bool(GEMINI_API_KEY):
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model_obj = genai.GenerativeModel(GEMINI_MODEL)
        GEMINI_ENABLED = True
        print(f"[IA] Gemini connecte - modele: {GEMINI_MODEL}")
    except ImportError:
        print("[IA] Module 'google-generativeai' non installe. pip install google-generativeai")
    except Exception as e:
        print(f"[IA] Gemini init erreur: {e}")
else:
    print("[IA] GEMINI_API_KEY/GOOGLE_API_KEY absent.")

# IA globale activee si au moins un provider est dispo
AI_ENABLED = GROQ_ENABLED or GEMINI_ENABLED

if not AI_ENABLED:
    print("[IA] Aucun provider IA disponible. Fallback statique (social_reseaux.py).")
else:
    providers = []
    if GROQ_ENABLED:
        providers.append("Groq")
    if GEMINI_ENABLED:
        providers.append("Gemini")
    print(f"[IA] Providers actifs: {', '.join(providers)} (cascade: Groq -> Gemini -> statique)")


# ==================== CHARGEMENT PRODUITS ====================

def load_products():
    """Charge les produits depuis liens_affiliation.json."""
    try:
        with open(LIENS_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            return [p for p in config.get("produits", []) if p.get("actif")]
    except Exception:
        return []


def get_random_product():
    """Retourne un produit aleatoire."""
    produits = load_products()
    return random.choice(produits) if produits else None


def find_product(query):
    """Trouve un produit par slug ou nom partiel."""
    produits = load_products()
    query = query.lower().replace("-", " ").replace("_", " ")
    for p in produits:
        if query in p.get("slug", "").lower() or query in p["nom"].lower():
            return p
    return random.choice(produits) if produits else None


# ==================== GENERATEUR IA (DUAL-PROVIDER) ====================

_last_provider = None  # Track which provider answered last

def _ask_groq(system_prompt, user_prompt, temperature=0.8, max_tokens=500):
    """Appelle Groq (OpenAI-compatible). Retourne None si indisponible."""
    global _last_provider
    if not GROQ_ENABLED or not groq_client:
        return None
    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        _last_provider = "groq"
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[IA Groq] Erreur: {e}")
        return None


def _ask_gemini(system_prompt, user_prompt, temperature=0.8, max_tokens=500):
    """Appelle Google Gemini. Retourne None si indisponible."""
    global _last_provider
    if not GEMINI_ENABLED or not gemini_model_obj:
        return None
    try:
        # Gemini: fusionner system+user en un seul prompt (le modele le gere bien)
        combined = f"[Instructions]\n{system_prompt}\n\n[Message]\n{user_prompt}"
        response = gemini_model_obj.generate_content(
            combined,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
        )
        _last_provider = "gemini"
        return response.text.strip()
    except Exception as e:
        print(f"[IA Gemini] Erreur: {e}")
        return None


def ask_ai(system_prompt, user_prompt, temperature=0.8, max_tokens=500):
    """Appelle les providers IA en cascade: Groq -> Gemini -> None.

    Si aucun provider ne repond, retourne None, ce qui declenche
    le fallback statique (social_reseaux.py) dans chaque generateur.
    """
    global _last_provider
    if not AI_ENABLED:
        return None

    # Provider 1: Groq (plus rapide, plus de quota)
    result = _ask_groq(system_prompt, user_prompt, temperature, max_tokens)
    if result is not None:
        return result

    # Provider 2: Gemini (fallback, gratuit)
    print("[IA] Groq rate-limite -> tentative Gemini...")
    result = _ask_gemini(system_prompt, user_prompt, temperature, max_tokens)
    if result is not None:
        return result

    # Les deux providers sont KO
    _last_provider = None  # Reset pour que get_active_provider() soit honnete
    print("[IA] Aucun provider dispo. Fallback statique.")
    return None


def get_active_provider():
    """Retourne le nom du dernier provider utilise, ou 'statique' si aucun."""
    return _last_provider or "statique"


# ==================== GENERATEURS DE CONTENU ====================

def generate_tweets(product=None, count=5):
    """Genere des tweets viraux pour un produit via IA."""
    if product is None:
        product = get_random_product()
    if not product:
        return []

    slug = slugify(product["nom"])
    short_url = f"{SITE_URL}/go/{slug}?src=twitter"

    # Prompt IA
    system_prompt = """Tu es un expert en marketing d'affiliation et copywriting sur Twitter/X.
Tu ecris des tweets percutants, viraux, qui donnent envie de cliquer.
Regles:
- Maximum 280 caracteres par tweet
- Inclure prix, note, et le lien fourni
- Ton energie, engageant, style francais naturel
- Varie les angles: bon plan, promo, temoignage, question, astuce
- 1-2 hashtags max: #BonPlan #Amazon
- JAMAIS de repetition entre les tweets"""

    user_prompt = f"""Cree {count} tweets uniques pour promouvoir ce produit:

Produit: {product['nom']}
Categorie: {product.get('categorie', 'High-Tech')}
Prix: {product['prix']} EUR
Note: {product['note_moyenne']}/5 ({product['avis_total']} avis)
Commission: {product['commission_euro']} EUR
Plateforme: {product.get('plateforme', 'Amazon')}
Caracteristiques: {', '.join(product.get('caracteristiques', [])[:3])}

Lien a inclure dans CHAQUE tweet: {short_url}

Format: un tweet par ligne, sans numerotation. Commence direct par le texte."""

    response = ask_ai(system_prompt, user_prompt, temperature=0.9, max_tokens=800)

    if response:
        tweets = [t.strip() for t in response.split("\n") if t.strip() and len(t.strip()) > 20]
        # Ajouter le lien si pas present
        tweets = [t if short_url in t else f"{t}\n{short_url}" for t in tweets]
        return tweets[:count]

    # Fallback: utiliser le generateur statique
    print("[IA] Fallback vers social_reseaux.py (tweets)")
    all_fallback = static_tweets()
    matching = [t for t in all_fallback if product['nom'].lower() in t.lower()]
    return matching[:count] if matching else all_fallback[:count]


def generate_linkedin(product=None):
    """Genere un post LinkedIn professionnel via IA."""
    if product is None:
        product = get_random_product()
    if not product:
        return None

    from social_reseaux import slugify, SITE_URL

    slug = slugify(product["nom"])
    short_url = f"{SITE_URL}/go/{slug}?src=linkedin"

    system_prompt = """Tu es un expert en marketing d'affiliation et business development.
Tu ecris des posts LinkedIn professionnels, informatifs et engageants.
Style: analyse de produit, recommandation business, valeur ajoutee.
Inclus: emojis professionnels, structure claire, hashtags pertinents."""

    user_prompt = f"""Ecris un post LinkedIn professionnel pour recommander ce produit:

Nom: {product['nom']}
Categorie: {product.get('categorie', 'Tech')}
Prix: {product['prix']} EUR
Note: {product['note_moyenne']}/5 ({product['avis_total']} avis)
Commission partenaire: {product['commission_euro']} EUR
Caracteristiques cles:
- {product.get('caracteristiques', ['Qualite pro'])[0]}
- {product.get('caracteristiques', ['', 'Fiable'])[1] if len(product.get('caracteristiques', [])) > 1 else 'Excellent rapport qualite-prix'}

Lien a inclure: {short_url}
Hashtags a utiliser: #Affiliation #Business #Amazon #Recommandation"""

    response = ask_ai(system_prompt, user_prompt, temperature=0.7, max_tokens=600)

    if response:
        return {"titre": f"Decouvrez le {product['nom']}", "contenu": response, "lien": short_url}

    # Fallback
    print("[IA] Fallback vers social_reseaux.py (linkedin)")
    posts = static_linkedin()
    for p in posts:
        if product['nom'].lower() in p.get('contenu', '').lower():
            return p
    return posts[0] if posts else None


def generate_facebook(product=None):
    """Genere un post Facebook engageant via IA."""
    if product is None:
        product = get_random_product()
    if not product:
        return None

    slug = slugify(product["nom"])
    short_url = f"{SITE_URL}/go/{slug}?src=facebook"

    system_prompt = """Tu es un community manager expert. Tu ecris des posts Facebook engageants
qui generent des likes, commentaires et partages. Style chaleureux et conversationnel."""

    user_prompt = f"""Ecris un post Facebook engageant pour ce produit:

Produit: {product['nom']} - {product['prix']} EUR
Note: {product['note_moyenne']}/5 ({product['avis_total']} avis)
Description: {product.get('description', '')[:150]}

Lien: {short_url}

Le post doit:
- Commencer par une question ou une anecdote pour engager
- Decrire le benefice principal du produit
- Inclure le lien naturellement
- Terminer par un appel a l'action (taguer un ami, donner son avis...)"""

    response = ask_ai(system_prompt, user_prompt, temperature=0.8, max_tokens=500)

    if response:
        return {"titre": f"🔥 {product['nom']}", "contenu": response, "lien": short_url}

    # Fallback
    posts = static_facebook()
    for p in posts:
        if product['nom'].lower() in p.get('contenu', '').lower():
            return p
    return posts[0] if posts else None


def generate_blog(product=None):
    """Genere un article de blog SEO via IA."""
    if product is None:
        product = get_random_product()
    if not product:
        return None

    slug = slugify(product["nom"])
    product_url = f"{SITE_URL}/produit/{product.get('slug', slug)}"
    short_url = f"{SITE_URL}/go/{slug}?src=blog"

    system_prompt = """Tu es un redacteur SEO expert. Tu ecris des articles de blog optimises
pour le referencement, informatifs et utiles pour le lecteur. Style professionnel mais accessible."""

    user_prompt = f"""Ecris une introduction d'article blog (400-500 mots) pour ce produit:

Titre: {product['nom']} - Test complet et avis 2026
Produit: {product['nom']}
Prix: {product['prix']} EUR
Note: {product['note_moyenne']}/5 ({product['avis_total']} avis)
Categorie: {product.get('categorie', 'High-Tech')}
Caracteristiques: {', '.join(product.get('caracteristiques', [])[:4])}

Lien produit: {product_url}
Lien affiliation: {short_url}

Structure demandee:
1. Introduction accrocheuse (pourquoi ce produit est pertinent en 2026)
2. Presentation du produit
3. Les 3 points forts principaux
4. Conclusion avec lien d'achat

Optimise pour le mot-cle: \"{product['nom']} avis test prix\""""

    response = ask_ai(system_prompt, user_prompt, temperature=0.7, max_tokens=800)

    if response:
        return {
            "titre": f"{product['nom']} - Test complet et avis 2026",
            "contenu": response,
            "lien": short_url,
            "seo_keyword": f"{product['nom']} avis test prix"
        }

    # Fallback
    articles = static_blog()
    for a in articles:
        if product['nom'].lower() in a.get('contenu', '').lower():
            return a
    return articles[0] if articles else None


def generate_email(product=None):
    """Genere un email marketing via IA."""
    if product is None:
        product = get_random_product()
    if not product:
        return None

    slug = slugify(product["nom"])
    short_url = f"{SITE_URL}/go/{slug}?src=email"

    system_prompt = """Tu es un expert en email marketing. Tu ecris des emails qui convertissent.
Style: personnel, chaleureux, oriente benefices. FranCais naturel, pas trop formel."""

    user_prompt = f"""Ecris un email marketing pour promouvoir ce produit:

Produit: {product['nom']}
Prix: {product['prix']} EUR
Note: {product['note_moyenne']}/5 ({product['avis_total']} avis)
Benefice principal: {product.get('description', '')[:100]}
Pourquoi l'acheter: {product.get('caracteristiques', ['Excellent produit'])[0]}

Lien: {short_url}

Structure:
- Objet d'email accrocheur
- Salutation
- Corps (2-3 paragraphes)
- Call-to-action
- Signature "L'equipe Affilimax"

Separe chaque section par ---"""

    response = ask_ai(system_prompt, user_prompt, temperature=0.7, max_tokens=500)

    if response:
        parts = response.split("---")
        sujet = parts[0].strip() if len(parts) > 0 else f"Decouvrez le {product['nom']}"
        contenu = "\n".join(parts[1:]).strip() if len(parts) > 1 else response
        return {"sujet": sujet.replace("Objet:", "").strip(), "contenu": contenu, "lien": short_url}

    # Fallback
    emails = static_emails()
    for e in emails:
        if product['nom'].lower() in e.get('contenu', '').lower():
            return e
    return emails[0] if emails else None


# ==================== GENERATION PAR LOT ====================

def generate_all_content(product_name=None, count=3):
    """Genere un lot complet de contenu pour un produit."""
    product = find_product(product_name) if product_name else get_random_product()
    if not product:
        return {"error": "Aucun produit trouve"}

    result = {
        "produit": product["nom"],
        "prix": product["prix"],
        "commission": product["commission_euro"],
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "mode": f"IA ({get_active_provider().upper()})" if AI_ENABLED else "FALLBACK (statique)",
    }

    # Generer chaque type
    result["tweets"] = generate_tweets(product, count=count)
    result["linkedin"] = generate_linkedin(product)
    result["facebook"] = generate_facebook(product)
    result["blog"] = generate_blog(product)
    result["email"] = generate_email(product)

    return result


def generate_batch_for_all_platforms(count_per_product=3):
    """Genere du contenu pour TOUS les produits sur TOUTES les plateformes."""
    produits = load_products()
    all_results = []

    for i, p in enumerate(produits):
        print(f"[IA] Generation pour: {p['nom']} ({i+1}/{len(produits)})")
        result = generate_all_content(p['nom'], count=count_per_product)
        all_results.append(result)
        # Rate limiting adaptatif: pause entre chaque produit
        # Groq: ~30 RPM -> 2s pause. Gemini: ~15 RPM -> 4s pause.
        # Avec les 2, on alterne donc 3s est un bon compromis.
        if AI_ENABLED and i < len(produits) - 1:
            time.sleep(3)

    return all_results


# ==================== HEALTH CHECK ====================

def health_check():
    """Verifie si l'IA est operationnelle (sans consommer de quota)."""
    providers = []
    if GROQ_ENABLED:
        providers.append({"name": "groq", "model": GROQ_MODEL, "ready": True})
    else:
        providers.append({"name": "groq", "model": GROQ_MODEL, "ready": bool(GROQ_API_KEY)})
    if GEMINI_ENABLED:
        providers.append({"name": "gemini", "model": GEMINI_MODEL, "ready": True})
    else:
        providers.append({"name": "gemini", "model": GEMINI_MODEL, "ready": bool(GEMINI_API_KEY)})

    status = {
        "ai_enabled": AI_ENABLED,
        "active_provider": _last_provider or ("groq" if GROQ_ENABLED else "gemini" if GEMINI_ENABLED else "statique"),
        "providers": providers,
        "cascade_order": ["groq", "gemini", "statique"],
        "products_count": len(load_products()),
        "groq_enabled": GROQ_ENABLED,
        "gemini_enabled": GEMINI_ENABLED,
    }
    # Test leger: verifier que le fallback fonctionne
    if not AI_ENABLED:
        test_tweets = static_tweets()
        status["fallback_test"] = f"OK ({len(test_tweets)} tweets dispo)"
    else:
        status["api_ready"] = True
    return status


# ==================== CLI ====================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Affilimax - Automatisation IA (Groq)")
    parser.add_argument("--tweets", action="store_true", help="Generer des tweets")
    parser.add_argument("--linkedin", action="store_true", help="Generer un post LinkedIn")
    parser.add_argument("--facebook", action="store_true", help="Generer un post Facebook")
    parser.add_argument("--blog", action="store_true", help="Generer un article blog")
    parser.add_argument("--email", action="store_true", help="Generer un email marketing")
    parser.add_argument("--all", action="store_true", help="Generer tout pour un produit")
    parser.add_argument("--product", type=str, help="Nom ou slug du produit cible")
    parser.add_argument("--batch", action="store_true", help="Generer pour TOUS les produits")
    parser.add_argument("--health", action="store_true", help="Health check IA")
    parser.add_argument("--count", type=int, default=5, help="Nombre de tweets a generer")

    args = parser.parse_args()

    if args.health:
        print(json.dumps(health_check(), indent=2, ensure_ascii=False))
        sys.exit(0)

    if args.batch:
        print(f"Generation pour tous les produits...")
        results = generate_batch_for_all_platforms()
        print(f"\nGenere: {len(results)} produits traites")
        for r in results[:3]:
            print(f"  {r['produit']}: {len(r.get('tweets', []))} tweets, mode={r['mode']}")
        sys.exit(0)

    if args.all:
        result = generate_all_content(args.product)
        print(json.dumps({
            "produit": result["produit"],
            "mode": result["mode"],
            "tweets": result.get("tweets", [])[:3],
            "linkedin_titre": result.get("linkedin", {}).get("titre", ""),
            "blog_titre": result.get("blog", {}).get("titre", ""),
            "email_sujet": result.get("email", {}).get("sujet", ""),
        }, indent=2, ensure_ascii=False))
        sys.exit(0)

    if args.tweets:
        tweets = generate_tweets(find_product(args.product), count=args.count)
        for i, t in enumerate(tweets):
            print(f"\n--- Tweet {i+1} ---")
            print(t)

    if args.linkedin:
        post = generate_linkedin(find_product(args.product))
        if post:
            print(f"\n### {post['titre']}")
            print(post['contenu'])

    if args.facebook:
        post = generate_facebook(find_product(args.product))
        if post:
            print(f"\n### {post['titre']}")
            print(post['contenu'])

    if args.blog:
        article = generate_blog(find_product(args.product))
        if article:
            print(f"\n# {article['titre']}")
            print(article['contenu'][:500])

    if args.email:
        email = generate_email(find_product(args.product))
        if email:
            print(f"\nSujet: {email['sujet']}")
            print(email['contenu'][:400])
