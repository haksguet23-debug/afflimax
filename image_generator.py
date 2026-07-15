#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Affilimax - Generateur d'Images Produits par Stable Diffusion
==============================================================
Genere des images de produits realistes en local via Stable Diffusion
(Hugging Face diffusers). Fonctionne sur CPU (lent) et GPU (rapide).

Utilisation:
    python image_generator.py --all        # Genere les images pour tous les produits
    python image_generator.py --product 0  # Genere pour l'index 0
    python image_generator.py --list       # Liste les produits
"""

import os
import sys
import json
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
ASSETS_DIR = BASE_DIR / "assets" / "images"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
LIENS_FILE = BASE_DIR / "liens_affiliation.json"

# Mapping des categories aux prompts visuels
CATEGORY_PROMPTS = {
    "Business": "professional product photography, sleek modern device on minimalist desk, soft studio lighting, clean white background",
    "Formation": "elegant book mockup on wooden desk, warm lighting, educational concept, professional photography",
    "Tech": "high-tech gadget on dark surface, cyan ambient lighting, futuristic product showcase, sharp focus",
    "Bureau": "modern office accessories on clean desk, natural lighting, ergonomic setup, professional workspace photography",
    "Maison": "home appliance in modern kitchen setting, warm cozy lighting, lifestyle product photography",
    "E-Commerce": "modern book cover design on gradient background, clean typography, professional publishing mockup",
    "Marketing": "professional book mockup, marketing concept, creative desk setup, warm lighting",
    "Web": "digital workspace concept, laptop on desk, clean modern design, web development theme",
    "Audio": "premium audio equipment on dark background, gold accents, studio lighting, product photography",
    "Gaming": "gaming gear with RGB lighting, dark atmospheric background, neon accents, dynamic product shot",
    "Accessoires": "tech accessories on marble surface, clean white background, minimalist product photography",
    "Sport": "fitness equipment in modern home gym, motivational lighting, sporty dynamic composition",
    "High-Tech": "premium electronic device on minimalist surface, studio lighting, tech product photography",
    "Jeux": "collector item on display shelf, warm gallery lighting, premium product showcase",
    "Informatique": "computer hardware on clean desk setup, blue accent lighting, professional tech photography",
    "Livre": "elegant hardcover book on vintage wooden surface, warm natural lighting, literary photography",
    "Cuisine": "modern kitchen appliance on countertop, fresh ingredients nearby, warm lifestyle photography",
    "Audio": "premium headphones on dark surface, studio lighting, luxury audio product photography",
}

DEFAULT_PROMPT = "professional product photography on clean background, studio lighting, 4k quality, sharp focus, minimal composition"

def load_products():
    """Charge les produits depuis liens_affiliation.json."""
    try:
        with open(LIENS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  [ERREUR] Impossible de charger les produits: {e}")
        return None


def save_products(data):
    """Sauvegarde les produits dans liens_affiliation.json."""
    with open(LIENS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def generate_product_image(product, index=None):
    """Genere une image pour un produit via Stable Diffusion.

    Args:
        product: dict du produit (nom, description, categorie, slug)
        index: index optionnel pour le nom de fichier

    Returns:
        str: chemin de l'image generee, ou None si echec
    """
    nom = product["nom"]
    slug = product.get("slug", f"product-{index}")
    categorie = product.get("categorie", "")
    description = product.get("description", "")

    # Prompt optimise pour le produit
    base_prompt = CATEGORY_PROMPTS.get(categorie, DEFAULT_PROMPT)
    product_name = nom.split("(")[0].strip()
    prompt = f"Professional product photo of {product_name}, {base_prompt}"

    # Dimensions 600x400 (comme les placeholders)
    width, height = 600, 400

    print(f"  [SD] Generation de '{slug}'...")
    print(f"  [SD] Prompt: {prompt[:100]}...")
    start = time.time()

    try:
        from diffusers import StableDiffusionPipeline
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32

        print(f"  [SD] Device: {device.upper()} (chargement du modele...)")

        # Charger le modele (mis en cache apres le 1er chargement)
        pipe = StableDiffusionPipeline.from_pretrained(
            "runwayml/stable-diffusion-v1-5",
            torch_dtype=dtype,
            safety_checker=None,
        )
        pipe = pipe.to(device)

        # Optimisation CPU
        if device == "cpu":
            pipe.enable_attention_slicing()

        # Generer l'image
        image = pipe(
            prompt,
            negative_prompt="blurry, low quality, distorted, text, watermark, signature, extra limbs, bad anatomy",
            width=width,
            height=height,
            num_inference_steps=25 if device == "cuda" else 15,
            guidance_scale=7.5,
        ).images[0]

        elapsed = time.time() - start
        print(f"  [SD] Image generee en {elapsed:.1f}s")

        # Sauvegarder
        output_path = ASSETS_DIR / f"{slug}.png"
        image.save(output_path)
        print(f"  [SD] Sauvegardee: {output_path}")

        return str(output_path)

    except ImportError as e:
        print(f"  [ERREUR] Module manquant: {e}")
        print("  Installez: pip install diffusers accelerate transformers torch")
        return None
    except Exception as e:
        print(f"  [ERREUR] Generation echouee pour '{nom}': {e}")
        return None


def generate_all(force=False):
    """Genere les images pour tous les produits actifs.

    Args:
        force: Si True, regenere meme si l'image existe deja
    """
    data = load_products()
    if not data:
        return

    produits = [p for p in data["produits"] if p.get("actif")]
    total = len(produits)
    success = 0
    skipped = 0

    print(f"\n{'='*50}")
    print(f"  Generation d'images pour {total} produits")
    print(f"  Dossier: {ASSETS_DIR}")
    print(f"  Device: {'GPU' if __import__('torch').cuda.is_available() else 'CPU'}")
    print(f"{'='*50}\n")

    for i, produit in enumerate(produits):
        slug = produit.get("slug", f"product-{i}")
        local_path = ASSETS_DIR / f"{slug}.png"

        if local_path.exists() and not force:
            print(f"  [{i+1}/{total}] {produit['nom']} - IMAGE DEJA EXISTANTE (skipped)")
            skipped += 1
            # Mettre a jour le chemin dans le JSON meme si existe deja
            old_url = produit.get("image_url", "")
            new_url = f"/assets/images/{slug}.png"
            if old_url != new_url and old_url.startswith("https://placehold.co"):
                produit["image_url"] = new_url
                produit["image_ia"] = True
            continue

        print(f"  [{i+1}/{total}] {produit['nom']}...")
        result = generate_product_image(produit, i)

        if result:
            success += 1
            # Mettre a jour l'URL dans le JSON
            produit["image_url"] = f"/assets/images/{slug}.png"
            produit["image_ia"] = True
        else:
            print(f"  [ECHEC] {produit['nom']}")

        # Petite pause entre chaque generation
        if i < total - 1:
            time.sleep(1)

    # Sauvegarder les nouvelles URLs
    save_products(data)
    print(f"\n{'='*50}")
    print(f"  Resume: {success} generees, {skipped} deja existantes, {total - success - skipped} echecs")
    print(f"{'='*50}\n")
    return success


def list_products():
    """Liste les produits avec leur statut image."""
    data = load_products()
    if not data:
        return

    produits = [p for p in data["produits"] if p.get("actif")]
    print(f"\nProduits ({len(produits)}):")
    print(f"{'ID':<4} {'Nom':<35} {'Image':<45}")
    print("-" * 84)
    for i, p in enumerate(produits):
        slug = p.get("slug", f"product-{i}")
        local_path = ASSETS_DIR / f"{slug}.png"
        status = "LOCALE ✓" if local_path.exists() else "PLACEHOLDER"
        image = p.get("image_url", "")[:42]
        print(f"{i:<4} {p['nom'][:33]:<35} {image:<45} [{status}]")
    print()


def serve_image(request_path):
    """Sert une image generee. A integrer dans le handler HTTP.

    Args:
        request_path: Chemin de la requete (ex: /assets/images/ssd-samsung.png)

    Returns:
        (file_path, mime_type) ou None
    """
    # Securite: empecher le path traversal
    safe_path = request_path.replace("..", "").lstrip("/")
    full_path = BASE_DIR / safe_path

    if full_path.exists() and full_path.suffix in (".png", ".jpg", ".jpeg", ".webp"):
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }
        return str(full_path), mime_map.get(full_path.suffix, "image/png")

    return None


# ==================== CLI ====================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generateur d'images produits IA")
    parser.add_argument("--all", action="store_true", help="Generer les images pour tous les produits")
    parser.add_argument("--product", type=int, help="Index du produit a generer")
    parser.add_argument("--list", action="store_true", help="Lister les produits")
    parser.add_argument("--force", action="store_true", help="Forcer la regeneration meme si l'image existe")
    args = parser.parse_args()

    if args.list:
        list_products()
    elif args.product is not None:
        data = load_products()
        if data:
            produits = [p for p in data["produits"] if p.get("actif")]
            if 0 <= args.product < len(produits):
                result = generate_product_image(produits[args.product], args.product)
                if result:
                    slug = produits[args.product].get("slug", f"product-{args.product}")
                    produits[args.product]["image_url"] = f"/assets/images/{slug}.png"
                    produits[args.product]["image_ia"] = True
                    save_products(data)
                    print(f"  Image sauvegardee: {result}")
            else:
                print(f"  Index invalide. Utilisez --list pour voir les indices.")
    elif args.all:
        generate_all(force=args.force)
    else:
        parser.print_help()
        print("\nExemples:")
        print("  python image_generator.py --list")
        print("  python image_generator.py --product 0")
        print("  python image_generator.py --all")
        print("  python image_generator.py --all --force")
