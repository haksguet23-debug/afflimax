# Affilimax — Stripe Connect LIVE Setup

Guide pour basculer les paiements partenaires du mode DEMO (simulation locale) au mode LIVE (Stripe Connect Express, virements reels en EUR).

> **Important** : Toujours tester en mode TEST (sk_test_...) AVANT de passer en LIVE (sk_live_...). Le LIVE engage de l'argent reel.

---

## 1. Variables d'environnement requises

Definir dans **Render.com Dashboard > Environment** (ou localement dans un fichier `.env` / shell) :

| Variable | Obligatoire | Description | Exemple |
|---|---|---|---|
| `STRIPE_SECRET_KEY` | Oui | Cle secrete Stripe (sk_test_ ou sk_live_) | `sk_test_51Nx...` |
| `STRIPE_PUBLISHABLE_KEY` | Recommandé | Cle publique pour le front | `pk_test_51Nx...` |
| `STRIPE_WEBHOOK_SECRET` | **Obligatoire en prod.** (Recommandé en dev) | Signature des webhooks (voir etape 3). Sans elle, le webhook REJETE tout en mode strict. | `whsec_xxxxx` |
| `STRIPE_DEFAULT_COUNTRY` | Non | Code pays ISO pour Connect (defaut `FR`) | `FR`, `BE`, `CH`... |
| `STRIPE_DEFAULT_CURRENCY` | Non | Code devise (defaut `eur`) | `eur`, `chf`... |
| `STRIPE_DEFAULT_BUSINESS_TYPE` | Non | `individual` ou `company` (defaut `individual`) | |
| `PLATFORM_FEE_PERCENT` | Non | Commission prelevee par la plateforme sur chaque transfer (defaut 0) | `0`, `5` (= 5%) |
| `AFFILMAX_BASE_URL` | Recommandé | URL du site pour les liens onboarding (defaut: Render externe ou localhost) | `https://affilmax.render.com` |
| `AFFILMAX_REQUIRE_LIVE` | **OBLIGATOIRE en production** | `1` = refuse tout demarrage en mode DEMO ou sans auth admin (fail-fast). Voir section ci-dessous. | `1` (prod), `0` (dev/test) |
| `ADMIN_USER` | **Obligatoire si AFFILMAX_REQUIRE_LIVE=1**, recommandé sinon | Identifiant pour acceder a `/admin.html`, `/payouts.html` et `/api/stripe/*` | `admin` |
| `ADMIN_PASSWORD` | **Obligatoire si AFFILMAX_REQUIRE_LIVE=1**, recommandé sinon | Mot de passe admin (HTTP Basic Auth, comparaison en temps constant) | `<32 chars aleatoires>` |
| `PARTNER_SECRET_KEY` | **Obligatoire si AFFILMAX_REQUIRE_LIVE=1** | Cle de signature des tokens de session partenaire. 32+ chars aleatoires recommandes. | `<hex 64 chars>` |

---

## 1.1. Mode strict `AFFILMAX_REQUIRE_LIVE=1` (PRODUCTION)

**C'est le seul mode acceptable en production.** Aucun fallback vers DEMO, aucune auth admin optionnelle.

### Effets du flag

| Si `AFFILMAX_REQUIRE_LIVE=1` et que ... | Comportement |
|---|---|
| `STRIPE_SECRET_KEY` manquant | **RuntimeError au démarrage** — serveur refuse de demarrer |
| `ADMIN_USER` ou `ADMIN_PASSWORD` manquant | **RuntimeError au démarrage** — empêche les routes admin non protégées |
| `PARTNER_SECRET_KEY` manquant | **RuntimeError au démarrage** — empêche les tokens forgeables |
| `STRIPE_WEBHOOK_SECRET` manquant sur le webhook | **HTTP 503 refuse l'événement** (fail-closed, pas fail-open) |

### Comment basculer en mode strict (Render.com)

Dans **Environment > Add Env Var** :
```
AFFILMAX_REQUIRE_LIVE=1
ADMIN_USER=<votre_identifiant>
ADMIN_PASSWORD=<32+ chars aléatoires>
PARTNER_SECRET_KEY=<openssl rand -hex 32>
STRIPE_WEBHOOK_SECRET=whsec_...   # sinon le webhook Stripe sera rejeté
```

> **Note** : `ADMIN_USER` + `ADMIN_PASSWORD` sécurisent via **HTTP Basic Auth**. Le navigateur affichera une popup de login. Aucun cookie : c'est stateless et sûr.

### Comment générer les secrets forts

```bash
# Server-side / shell
openssl rand -hex 32   # 64 chars hex
openssl rand -base64 48  # ~64 chars base64

# Python
python -c "import secrets; print(secrets.token_hex(32))"
```

### Auth admin : protéger l'accès

Quand `ADMIN_USER` et `ADMIN_PASSWORD` sont définis, les routes suivantes exigent `Authorization: Basic <base64(user:password)>` :
- `/admin.html`
- `/payouts.html`
- `GET /api/stripe/health`
- `GET /api/stripe/partner-status/<id>`
- `GET /api/stripe/regonboard/<id>`
- `POST /api/stripe/onboard`
- `POST /api/stripe/payout`

Routes **publiques** (pas d'auth admin nécessaire) :
- `/api/stats`, `/api/produits`, `/api/click`, `/api/conversion` (dashboard public)
- `/api/partner/login`, `/api/partner/me`, `/api/partner/stats` (espace partenaire)

### Tester l'auth admin en local

```bash
# Sans credentials -> 401
curl -i http://localhost:8765/admin.html

# Avec credentials ->
curl -i -u admin:votre_password http://localhost:8765/admin.html
```

### Verification locale rapide

```bash
python -c "import stripe_config; import json; print(json.dumps(stripe_config.stripe_health_check(), indent=2))"
```

Doit renvoyer `{"mode": "live", "enabled": true, "available": [...], ...}` (et pas `{"mode": "demo"}`).

---

## 2. Configuration dans le Dashboard Stripe

### 2.1 Activer Stripe Connect

1. Aller sur https://dashboard.stripe.com/connect/overview
2. Cliquer **"Get started with Connect"** si pas deja fait
3. Choisir le type : **Express** (recommande pour Affilimax)
4. Remplir les informations de la plateforme :
   - Nom : `Affilimax`
   - Site web : `https://affilmax.render.com`
   - Pays : `France`
   - Type d'activite : `Marketing d'affiliation`
5. Configurer le **branding** :
   - Logo, couleurs, message affiché aux partenaires pendant le KYC
6. Activer **transfers** (la capability qu'on utilise)
7. Sauvegarder

### 2.2 Obtenir les cles API

1. https://dashboard.stripe.com/apikeys
2. **Mode TEST** (pour tester d'abord) :
   - "Standard keys" > **Reveal test key** > copier `Secret key` (sk_test_...)
3. **Mode LIVE** (apres validation complete) :
   - Basculer en mode LIVE en haut du dashboard
   - Re-meme etape, copier la cle `sk_live_...`
4. Verifier que vous avez aussi la **Restricted key** appropriee si besoin

### 2.3 Configurer le webhook

1. https://dashboard.stripe.com/webhooks (selectionner le bon mode : test OU live)
2. **Add endpoint** :
   - URL : `https://affilmax.render.com/api/stripe/webhook`
   - Description : `Affilimax Connect events`
3. Selectionner les **events** a recevoir :
   - `account.updated` (changements KYC d'un partenaire Connect)
   - `capability.updated` (capabilities activees/inactivees)
   - `payout.paid` (payout reussi cote plateforme)
   - `payout.failed` (payout echoue cote plateforme)
   - `transfer.created` / `transfer.reversed` (debug optionnel)
4. Copier le **Signing secret** (commence par `whsec_...`) → definir comme `STRIPE_WEBHOOK_SECRET`

### 2.4 Activer le compte plateforme

Pour utiliser Connect en LIVE, Stripe exige que la plateforme soit elle-meme activee (KYC sur **vous**, le proprietaire d'Affilimax). 

> Si votre dashboard affiche "Platform profile not complete", completez votre propre verification d'identite dans **Settings > Public details > Business settings**.

---

## 3. Tester en mode TEST avant de basculer en LIVE

### 3.1 Configurer les cles test

```bash
export STRIPE_SECRET_KEY="sk_test_51Nx..."
export STRIPE_PUBLISHABLE_KEY="pk_test_51Nx..."
export STRIPE_WEBHOOK_SECRET="whsec_test_..."
```

### 3.2 Creer des partenaires TEST dans `partners.json`

Les cles test necessitent des partenaires avec des emails valides (mais ils ne peuvent pas recevoir de vrais virements). Creer 2-3 partenaires de test :

```json
{
  "id": "test_partner_1",
  "nom": "Test User 1",
  "email": "votre-email+test1@gmail.com",
  "stripe_account_id": null,
  "onboarded": false,
  "commission_rate": 12.5,
  ...
}
```

### 3.3 Lancer la migration en mode test

```bash
python onboard_partners_live.py --apply --allow-test --include-demo
```

Le script va :
1. Verifier la cle API
2. Creer un backup `partners.json.bak`
3. Creer le compte Connect Stripe pour chaque partenaire
4. Generer une URL d'onboarding par partenaire
5. Mettre a jour `partners.json` avec les `stripe_account_id`

### 3.4 Completer le KYC (en mode test)

Pour chaque URL d'onboarding generee :
- Ouvrir l'URL dans un navigateur
- Stripe affiche un formulaire de test (noms, IBAN test, etc.)
- Soumettre → le webhook `account.updated` met automatiquement `onboarded=True`

IBAN de test Stripe : `GB29 NWBK 6016 1331 9268 19`

### 3.5 Tester un payout reel

Via l'admin UI ou API :
```bash
curl -X POST http://localhost:8765/api/stripe/payout \
  -H "Content-Type: application/json" \
  -d '{"partner_id":"test_partner_1","amount":25.0}'
```

Verifier :
- Le solde du partenaire est decremente
- La facture PDF est generee
- La notification Telegram/Slack part (si configuree)

### 3.6 Verifier le webhook

Test rapide :
```bash
# Sur Render.com, consulter les logs du serveur apres avoir declenche un evenement
# Les logs doivent afficher : "[STRIPE] account.updated acct_..."
```

Ou utiliser Stripe CLI en local :
```bash
stripe listen --forward-to localhost:8765/api/stripe/webhook
```

---

## 4. Basculer en LIVE (apres validation test)

1. Sur https://dashboard.stripe.com, basculer en **mode LIVE**
2. Remplacer les cles test par les cles LIVE :
   ```bash
   export STRIPE_SECRET_KEY="sk_live_51Nx..."
   export STRIPE_PUBLISHABLE_KEY="pk_live_51Nx..."
   export STRIPE_WEBHOOK_SECRET="whsec_live_..."
   ```
3. Reconfigurer le **webhook en mode LIVE** (point 2.3 ci-dessus) avec l'URL de production
4. Relancer la migration :
   ```bash
   python onboard_partners_live.py --apply
   ```
   > Le script demande une confirmation "OUI" car on cree de VRAIS comptes en LIVE.
5. Pour chaque partenaire reel, envoyer l'URL d'onboarding generee par email/Slack :
   > "Bonjour, merci de rejoindre Affilimax. Cliquez ici pour finaliser votre inscription : <URL>"
6. Chaque partenaire complete le KYC Stripe avec ses vrais documents
7. Le webhook met `onboarded=True` automatiquement
8. Les payouts peuvent desormais etre envoyes reellement

---

## 5. Diagnostic en production

### Endpoint sante (GET)

```bash
curl https://affilmax.render.com/api/stripe/health
```

Reponse type en LIVE :
```json
{
  "mode": "live",
  "enabled": true,
  "available": [{"currency": "EUR", "amount_eur": 0.0}],
  "pending": [],
  "livemode": true,
  "default_country": "FR",
  "default_currency": "EUR"
}
```

### Endpoint statut partenaire (GET)

```bash
curl https://affilmax.render.com/api/stripe/partner-status/demo_partner_1
```

Reponse :
```json
{
  "success": true,
  "details_submitted": true,
  "transfers_capability": "active",
  "transfers_active": true,
  "requirements_currently_due": [],
  "country": "FR",
  "default_currency": "eur"
}
```

### Regenerer lien onboarding (POST)

```bash
curl -X POST https://affilmax.render.com/api/stripe/regonboard/demo_partner_1
```

Reponse : `{"success": true, "onboarding_url": "https://connect.stripe.com/express/..."}`

---

## 6. Erreurs courantes

| Erreur | Cause | Solution |
|---|---|---|
| `Module 'stripe' not found` | Dependance manquante | `pip install stripe` (deja dans requirements.txt normalement) |
| `The 'country' parameter is required` | Stripe exige country depuis 2023 | Deja corrige dans `create_connect_account()` |
| `transfers capability not active` | KYC partenaire incomplet | Completer le formulaire d'onboarding ou regenerer le lien |
| `IdempotencyError` | Meme requete envoyee 2 fois dans la meme minute | OK, c'est le comportement attendu. Sinon utiliser une cle d'idempotence differente |
| `webhook signature verification failed` | `STRIPE_WEBHOOK_SECRET` incorrect ou webhook mal configure | Re-copier le signing secret depuis Stripe Dashboard > Webhooks |
| `API key not valid` | Cle API test/live inversee | Verifier la cle avec le bon mode dans le Dashboard Stripe |
| `Platform profile not complete` | Votre propre KYC plateforme incomplet | Completer dans Stripe Dashboard > Settings > Business |

---

## 7. Securite en production

1. **Ne JAMAIS commit le `.env` ou `partners.json.bak`** avec de vraies cles
2. Utiliser `git-crypt` ou des secrets manager externes si possible
3. Verifier que `STRIPE_WEBHOOK_SECRET` est different entre test et live
4. Surveiller le endpoint `/api/stripe/health` via un uptime checker (UptimeRobot, Better Stack, etc.)
5. Mettre en place une **alerte** sur les payouts.failed (script qui appelle le webhook et notifie)
6. Auditer regulierement la liste des partenaires onboarded (`stripe.onboarded=True`) et leurs soldes

---

## 8. Rollback vers DEMO

Si probleme en LIVE, on peut revenir en DEMO instantanement :

```bash
unset STRIPE_SECRET_KEY
# ou
export STRIPE_SECRET_KEY=""
```

Le code bascule automatiquement en mode DEMO. Les partenaires ayant un `stripe_account_id` seront ignores (leur compte reste chez Stripe mais Affilimax ne les traite plus).

Pour nettoyable complet : supprimer `partners.json` et recreer avec les 3 partenaires demo.

---

**Date de derniere mise a jour** : Juillet 2026
**Mode par defaut** : DEMO (securite - aucun mouvement d'argent sans cle explicite)
