#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Affilimax - Auto-Publication Twitter/X
======================================
Poste automatiquement les tweets du fichier contenu_twitter.txt
via l'API Twitter v2. 

Utilisation:
    python twitter_poster.py --test      # Poste 1 tweet test
    python twitter_poster.py --post 5    # Poste les 5 prochains tweets
    python twitter_poster.py --schedule  # Lance le scheduler automatique
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
TWEETS_FILE = BASE_DIR / "contenu_twitter.txt"
POSTED_FILE = BASE_DIR / "twitter_posted.json"

# ==================== CONFIG ====================

TWITTER_ENABLED = bool(os.environ.get("TWITTER_API_KEY", ""))

try:
    import tweepy
    TWEEPY_AVAILABLE = True
except ImportError:
    TWEEPY_AVAILABLE = False
    print("[TWITTER] tweepy non installe. pip install tweepy")

INTERVAL_SECONDS = int(os.environ.get("TWITTER_INTERVAL", "300"))  # 5 min entre posts
MAX_PER_SESSION = int(os.environ.get("TWITTER_MAX_SESSION", "10"))


def get_client():
    """Initialise le client Twitter API v2."""
    if not TWITTER_ENABLED or not TWEEPY_AVAILABLE:
        return None
    try:
        client = tweepy.Client(
            consumer_key=os.environ["TWITTER_API_KEY"],
            consumer_secret=os.environ["TWITTER_API_SECRET"],
            access_token=os.environ["TWITTER_ACCESS_TOKEN"],
            access_token_secret=os.environ["TWITTER_ACCESS_SECRET"],
        )
        return client
    except Exception as e:
        print(f"[TWITTER] Erreur init: {e}")
        return None


# ==================== GESTION FICHIER ====================

def load_tweets():
    """Charge tous les tweets depuis le fichier."""
    if not TWEETS_FILE.exists():
        return []
    with open(TWEETS_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    # Extraire les tweets (entre --- Tweet N ---)
    tweets = []
    blocks = content.split("--- Tweet")
    for block in blocks[1:]:  # Skip header
        lines = block.strip().split("\n")
        # Ignorer la premiere ligne (numero)
        text_lines = [l for l in lines[1:] if l.strip() and not l.startswith("===")]
        text = "\n".join(text_lines).strip()
        if text and len(text) > 10:
            tweets.append(text)
    return tweets


def load_posted():
    """Charge la liste des tweets deja postes."""
    if not POSTED_FILE.exists():
        return {"posted": [], "last_post_at": None, "total_posted": 0}
    with open(POSTED_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_posted(data):
    """Sauvegarde l'historique des tweets postes."""
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def mark_posted(tweet_text, tweet_id=None):
    """Marque un tweet comme poste."""
    data = load_posted()
    data["posted"].append({
        "text": tweet_text[:100],
        "tweet_id": tweet_id,
        "posted_at": datetime.utcnow().isoformat() + "Z"
    })
    data["last_post_at"] = datetime.utcnow().isoformat() + "Z"
    data["total_posted"] = len(data["posted"])
    save_posted(data)


# ==================== PUBLICATION ====================

def post_tweet(client, text):
    """Poste un tweet via l'API v2. Retourne l'ID du tweet ou None."""
    if not client:
        return None
    try:
        # Tronquer intelligemment en preservant les URLs
        if len(text) > 280:
            # Garder les URLs intactes, couper le texte avant
            words = text.split()
            result = []
            length = 0
            for w in words:
                if length + len(w) + 1 <= 277:
                    result.append(w)
                    length += len(w) + 1
                else:
                    break
            text = " ".join(result) + "..."
        response = client.create_tweet(text=text)
        return response.data["id"]
    except Exception as e:
        print(f"[TWITTER] Erreur post: {e}")
        return None


def post_next_tweets(count=1, client=None):
    """Poste les {count} prochains tweets non postes. Retourne le resultat."""
    if client is None:
        client = get_client()
    
    all_tweets = load_tweets()
    posted_data = load_posted()
    posted_texts = {p["text"] for p in posted_data["posted"]}
    
    # Filtrer les tweets non postes
    pending = [t for t in all_tweets if t[:100] not in posted_texts]
    
    if not pending:
        return {"status": "done", "message": "Tous les tweets ont ete postes!", "remaining": 0}
    
    results = []
    for i, tweet_text in enumerate(pending[:count]):
        if not TWITTER_ENABLED:
            results.append({"index": i+1, "status": "simulated", "text": tweet_text[:80]})
            # NE PAS marquer comme poste en mode simule
        else:
            tweet_id = post_tweet(client, tweet_text)
            if tweet_id:
                results.append({"index": i+1, "status": "posted", "tweet_id": tweet_id, "text": tweet_text[:80]})
                mark_posted(tweet_text, tweet_id)
                print(f"[TWITTER] Poste: {tweet_text[:60]}...")
            else:
                results.append({"index": i+1, "status": "error", "text": tweet_text[:80]})
                break  # Stop on error
        
        if i < count - 1 and i < len(pending) - 1:
            time.sleep(min(INTERVAL_SECONDS, 30))  # Max 30s entre posts en mode manuel
    
    remaining = len(pending) - len(results)
    return {
        "status": "ok",
        "posted": len([r for r in results if r["status"] in ("posted", "simulated")]),
        "errors": len([r for r in results if r["status"] == "error"]),
        "remaining": max(0, remaining),
        "results": results,
        "total_posted": load_posted()["total_posted"]
    }


def auto_scheduler():
    """Lance le scheduler automatique (tourne en boucle)."""
    client = get_client()
    print(f"[TWITTER] Scheduler demarre - intervalle: {INTERVAL_SECONDS}s")
    
    while True:
        try:
            result = post_next_tweets(count=1, client=client)
            if result["status"] == "done":
                print("[TWITTER] Tous les tweets postes. Arret du scheduler.")
                break
            print(f"[TWITTER] Poste. Restants: {result['remaining']}. Prochain dans {INTERVAL_SECONDS}s")
            time.sleep(INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\n[TWITTER] Scheduler arrete.")
            break
        except Exception as e:
            print(f"[TWITTER] Erreur scheduler: {e}")
            time.sleep(60)


# ==================== STATUS ====================

def get_status():
    """Retourne le statut actuel de la publication Twitter."""
    all_tweets = load_tweets()
    posted_data = load_posted()
    posted_texts = {p["text"] for p in posted_data["posted"]}
    pending = [t for t in all_tweets if t[:100] not in posted_texts]
    
    return {
        "twitter_enabled": TWITTER_ENABLED and TWEEPY_AVAILABLE,
        "total_tweets": len(all_tweets),
        "total_posted": posted_data.get("total_posted", 0),
        "remaining": len(pending),
        "last_post_at": posted_data.get("last_post_at"),
        "interval_seconds": INTERVAL_SECONDS,
        "pending_sample": [t[:80] for t in pending[:3]]
    }


# ==================== CLI ====================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Affilimax - Auto-Publication Twitter")
    parser.add_argument("--test", action="store_true", help="Poste 1 tweet test")
    parser.add_argument("--post", type=int, default=0, help="Poste N tweets")
    parser.add_argument("--schedule", action="store_true", help="Lance le scheduler automatique")
    parser.add_argument("--status", action="store_true", help="Affiche le statut")
    
    args = parser.parse_args()
    
    if args.status:
        print(json.dumps(get_status(), indent=2, ensure_ascii=False))
        sys.exit(0)
    
    if args.test:
        print("Posting 1 test tweet...")
        result = post_next_tweets(count=1)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0)
    
    if args.post > 0:
        print(f"Posting {args.post} tweets...")
        result = post_next_tweets(count=args.post)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0)
    
    if args.schedule:
        auto_scheduler()
        sys.exit(0)
    
    parser.print_help()
