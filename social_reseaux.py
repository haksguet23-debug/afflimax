# AFFILIMAX - Templates Reseaux Sociaux
# ======================================
# Copiez-collez ces posts sur vos comptes sociaux.
# Les liens de tracking sont deja integres.

# ==================== POSTS POUR X / TWITTER ====================

POSTS_TWITTER = [
    """🔥 TOP OFFRE DU JOUR : Pack Business Pro sur Amazon
Commission 8% | Deja 5000+ clients
👉 http://localhost:8765/pub.html
#affiliation #business #Amazon""",

    """💰 Vous voulez generer un revenu passif ?
Decouvrez notre selection d'offres d'affiliation avec les meilleures commissions.
👉 http://localhost:8765/pub.html
#PassiveIncome #affiliation""",

    """📈 +170€ de commissions generees aujourd'hui sur Affilimax
Rejoignez la plateforme et commencez a gagner.
👉 http://localhost:8765/pub.html
#MarketingDigital #business""",

    """🎯 Formation Trading 2026 - 15% de commission !
La formation la plus complete du marche.
👉 http://localhost:8765/pub.html
#Trading #Formation #ClickBank""",

    """💎 Logiciel SEO Ultimate - Positionnez vos sites en 1ere page Google
12% de commission garantie
👉 http://localhost:8765/pub.html
#SEO #MarketingDigital""",

    """🚀 Coaching VIP Mensuel - 20% de commission !
Le meilleur taux du marche pour un coaching premium.
👉 http://localhost:8765/pub.html
#Coaching #Business #Awin""",

    """📊 Masterclass E-Commerce - Creez votre boutique en ligne
18% de commission | Formation complete video + templates
👉 http://localhost:8765/pub.html
#Ecommerce #Formation"""
]

# ==================== POSTS POUR LINKEDIN ====================

POSTS_LINKEDIN = [
    {
        "titre": "Comment generer un revenu passif avec l'affiliation en 2026",
        "contenu": """L'affiliation reste l'un des meilleurs moyens de generer un revenu passif en 2026.

Voici les 3 offres qui performent le mieux en ce moment :

1. Pack Business Pro (Amazon) - 8% commission
2. Formation Trading 2026 (ClickBank) - 15% commission
3. Coaching VIP Mensuel (Awin) - 20% commission

Tous les details sur notre plateforme : http://localhost:8765/pub.html

#Affiliation #RevenuPassif #MarketingDigital #Business2026""",
        "hashtags": ["Affiliation", "PassiveIncome", "Business2026", "MarketingDigital"]
    },
    {
        "titre": "Les 5 plateformes d'affiliation a connaitre absolument",
        "contenu": """🔗 Amazon Associates - Ideal pour les produits physiques
🔗 ClickBank - Top pour les formations et produits digitaux
🔗 ShareASale - Large choix de categories
🔗 CJ Affiliate - Excellent pour la tech et la finance
🔗 Awin - Parfait pour le marche europeen

Retrouvez nos meilleures offres sur chaque plateforme : http://localhost:8765/pub.html

#Affiliation #Marketing #BusinessIntelligence""",
        "hashtags": ["Affiliation", "Marketing", "Ecommerce"]
    }
]

# ==================== POSTS POUR FACEBOOK / INSTAGRAM ====================

POSTS_FACEBOOK = [
    """🎉 NOUVEAU : Affilimax - Votre plateforme d'affiliation nouvelle generation !

✅ Commissions jusqu'a 20%
✅ Paiement sous 30 jours
✅ Tracking en temps reel
✅ Dashboard complet

Decouvrez nos offres du moment : http://localhost:8765/pub.html

Likez et partagez si vous connaissez quelqu'un que ca interesse ! 🙏""",

    """📢 RECHERCHE AFFILIES MOTIVES !

Vous avez un site, un blog, une audience sur les reseaux sociaux ?
Transformez votre trafic en revenus avec nos offres d'affiliation premium.

Commissions : 8% a 20% selon les offres
Plateformes : Amazon, ClickBank, ShareASale, Awin, CJ Affiliate

👉 http://localhost:8765/pub.html

#Affiliation #GagnerArgent #Freelance"""
]

# ==================== INSTRUCTIONS ====================

print("""
============================================================
  AFFILIMAX - TEMPLATES RESEAUX SOCIAUX
============================================================

COPIEZ-COLLEZ ces posts sur vos comptes :

1. X/Twitter : 7 posts prets a l'emploi
2. LinkedIn : 2 posts professionnels
3. Facebook/Instagram : 2 posts grand public

Tous les liens pointent vers ta landing page :
  http://localhost:8765/pub.html

Chaque clic sur ces liens sera TRACKE dans ton dashboard !
============================================================
""")

for i, post in enumerate(POSTS_TWITTER, 1):
    print(f"\n--- TWITTER POST {i} ---")
    print(post)

for i, post in enumerate(POSTS_LINKEDIN, 1):
    print(f"\n--- LINKEDIN POST {i} ---")
    print(f"TITRE: {post['titre']}")
    print(post['contenu'])

for i, post in enumerate(POSTS_FACEBOOK, 1):
    print(f"\n--- FACEBOOK POST {i} ---")
    print(post)
