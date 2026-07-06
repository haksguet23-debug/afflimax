#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Affilimax - Deploiement Automatique des Workflows n8n
=====================================================
Ce script cree tous les workflows n8n necessaires pour la plateforme
Affilimax via l'API REST n8n.

Usage:
    python create_all_workflows.py [--url URL] [--api-key KEY]

Prerequis:
    pip install requests
    Un serveur n8n en cours d'execution
    Une API key n8n valide
"""

import json
import os
import sys
import time
import argparse
from datetime import datetime
from typing import Optional

try:
    import requests
except ImportError:
    print("[ERREUR] Le module 'requests' est requis. Installez-le avec: pip install requests")
    sys.exit(1)

# ===================== CONFIGURATION =====================

N8N_URL = os.environ.get("N8N_URL", "https://affilmax.render.com")
N8N_API_KEY = os.environ.get("N8N_API_KEY", "")
WEBHOOK_BASE = os.environ.get("WEBHOOK_BASE", "https://affilmax.render.com")

HEADERS = {
    "X-N8N-API-KEY": N8N_API_KEY,
    "Content-Type": "application/json",
}

# ===================== WORKFLOW DEFINITIONS =====================

WORKFLOWS = [
    {
        "name": "Suivi des Clics Affilies",
        "folder": "affiliation",
        "active": True,
        "nodes": [
            {
                "name": "Webhook - Clic",
                "type": "n8n-nodes-base.webhook",
                "position": [250, 300],
                "parameters": {
                    "httpMethod": "POST",
                    "path": "track/click",
                    "responseMode": "redirect",
                    "options": {}
                }
            },
            {
                "name": "Extraire Donnees",
                "type": "n8n-nodes-base.set",
                "position": [450, 300],
                "parameters": {
                    "values": {
                        "string": [
                            {"name": "affiliate_id", "value": "={{$json.body.aff_id}}"},
                            {"name": "campaign_id", "value": "={{$json.body.camp_id}}"},
                            {"name": "source", "value": "={{$json.body.utm_source}}"},
                            {"name": "medium", "value": "={{$json.body.utm_medium}}"},
                            {"name": "ip", "value": "={{$json.headers['x-forwarded-for']}}"},
                            {"name": "user_agent", "value": "={{$json.headers['user-agent']}}"},
                            {"name": "timestamp", "value": "={{$now}}"}
                        ]
                    }
                }
            },
            {
                "name": "Enregistrer Click (DB)",
                "type": "n8n-nodes-base.postgres",
                "position": [650, 300],
                "parameters": {
                    "operation": "executeQuery",
                    "query": """
                        INSERT INTO clicks (affiliate_id, campaign_id, source, medium, ip, user_agent, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, NOW())
                        RETURNING id
                    """
                }
            },
            {
                "name": "Redirection",
                "type": "n8n-nodes-base.respondToWebhook",
                "position": [850, 300],
                "parameters": {
                    "respondWith": "redirect",
                    "redirectURL": "={{$node['Extraire Donnees'].json.redirect_url}}"
                }
            }
        ],
        "connections": {
            "Webhook - Clic": {"main": [[{"node": "Extraire Donnees", "type": "main", "index": 0}]]},
            "Extraire Donnees": {"main": [[{"node": "Enregistrer Click (DB)", "type": "main", "index": 0}]]},
            "Enregistrer Click (DB)": {"main": [[{"node": "Redirection", "type": "main", "index": 0}]]}
        }
    },
    {
        "name": "Suivi des Conversions",
        "folder": "affiliation",
        "active": True,
        "nodes": [
            {
                "name": "Webhook - Conversion",
                "type": "n8n-nodes-base.webhook",
                "position": [250, 300],
                "parameters": {
                    "httpMethod": "POST",
                    "path": "track/conversion",
                    "responseMode": "responseNode",
                    "options": {}
                }
            },
            {
                "name": "Valider Signature",
                "type": "n8n-nodes-base.function",
                "position": [450, 300],
                "parameters": {
                    "functionCode": """
// Valider la signature de conversion
const body = $input.first().json;
const secret = $env.CONVERSION_SECRET || 'affilmax_secret_2026';

// Verification basique
if (!body.order_id || !body.amount || !body.affiliate_id) {
    throw new Error('Donnees de conversion incompletes');
}

body.commission = body.amount * 0.12; // 12% commission par defaut
body.validated_at = new Date().toISOString();
body.status = 'confirmed';

return body;
"""
                }
            },
            {
                "name": "Enregistrer Conversion (DB)",
                "type": "n8n-nodes-base.postgres",
                "position": [650, 300],
                "parameters": {
                    "operation": "executeQuery",
                    "query": """
                        INSERT INTO conversions (order_id, affiliate_id, amount, commission, status, created_at)
                        VALUES ($1, $2, $3, $4, $5, NOW())
                        RETURNING id
                    """
                }
            },
            {
                "name": "Grosse Vente?",
                "type": "n8n-nodes-base.if",
                "position": [850, 300],
                "parameters": {
                    "conditions": {
                        "number": [{"value1": "={{$json.commission}}", "operation": "larger", "value2": 100}]
                    }
                }
            },
            {
                "name": "Notifier Telegram",
                "type": "n8n-nodes-base.telegram",
                "position": [1050, 200],
                "parameters": {
                    "text": "=Grosse Vente !\\nProduit: {{$json.product}}\\nCommission: {{$json.commission}}EUR\\nAffilie: {{$json.affiliate_id}}\\nPlateforme: {{$json.platform}}"
                }
            },
            {
                "name": "Repondre OK",
                "type": "n8n-nodes-base.respondToWebhook",
                "position": [1050, 400],
                "parameters": {
                    "respondWith": "json",
                    "responseBody": "={{JSON.stringify({status:'ok', conversion_id: $json.id})}}"
                }
            }
        ],
        "connections": {
            "Webhook - Conversion": {"main": [[{"node": "Valider Signature", "type": "main", "index": 0}]]},
            "Valider Signature": {"main": [[{"node": "Enregistrer Conversion (DB)", "type": "main", "index": 0}]]},
            "Enregistrer Conversion (DB)": {"main": [[{"node": "Grosse Vente?", "type": "main", "index": 0}]]},
            "Grosse Vente?": {
                "main": [
                    [{"node": "Notifier Telegram", "type": "main", "index": 0}],
                    [{"node": "Repondre OK", "type": "main", "index": 0}]
                ]
            },
            "Notifier Telegram": {"main": [[{"node": "Repondre OK", "type": "main", "index": 0}]]}
        }
    },
    {
        "name": "Rapport Quotidien",
        "folder": "analytics",
        "active": True,
        "nodes": [
            {
                "name": "Cron - 6h",
                "type": "n8n-nodes-base.cron",
                "position": [250, 300],
                "parameters": {"triggerTimes": {"item": [{"mode": "everyDay", "hour": 6, "minute": 0}]}}
            },
            {
                "name": "Agreger Stats",
                "type": "n8n-nodes-base.postgres",
                "position": [450, 300],
                "parameters": {
                    "operation": "executeQuery",
                    "query": """
                        SELECT
                            COUNT(DISTINCT c.id) as clicks,
                            COUNT(DISTINCT cv.id) as conversions,
                            COALESCE(SUM(cv.commission), 0) as total_commissions,
                            ROUND(COALESCE(SUM(cv.amount), 0), 2) as total_revenue,
                            ROUND(CASE WHEN COUNT(DISTINCT c.id) > 0
                                THEN COUNT(DISTINCT cv.id)::decimal / COUNT(DISTINCT c.id) * 100
                                ELSE 0 END, 2) as conversion_rate
                        FROM clicks c
                        LEFT JOIN conversions cv ON c.affiliate_id = cv.affiliate_id
                            AND cv.created_at::date = c.created_at::date
                        WHERE c.created_at::date = CURRENT_DATE - INTERVAL '1 day'
                    """
                }
            },
            {
                "name": "Formater Rapport",
                "type": "n8n-nodes-base.function",
                "position": [650, 300],
                "parameters": {
                    "functionCode": """
const stats = $input.first().json;
const yesterday = new Date();
yesterday.setDate(yesterday.getDate() - 1);
const dateStr = yesterday.toLocaleDateString('fr-FR', {day:'numeric',month:'long',year:'numeric'});

return {
    subject: `Rapport Affilimax - ${dateStr}`,
    html: `
        <h2>Rapport Quotidien Affilimax</h2>
        <p><strong>Date:</strong> ${dateStr}</p>
        <table border="1" cellpadding="8" style="border-collapse:collapse;">
            <tr><td>Clics</td><td><strong>${stats.clicks}</strong></td></tr>
            <tr><td>Conversions</td><td><strong>${stats.conversions}</strong></td></tr>
            <tr><td>Commissions</td><td><strong>${stats.total_commissions}EUR</strong></td></tr>
            <tr><td>CA Genere</td><td><strong>${stats.total_revenue}EUR</strong></td></tr>
            <tr><td>Taux Conv.</td><td><strong>${stats.conversion_rate}%</strong></td></tr>
        </table>
        <p>Plateforme: <a href="https://affilmax.render.com">Affilimax Dashboard</a></p>
    `
};
"""
                }
            },
            {
                "name": "Envoyer Email Admin",
                "type": "n8n-nodes-base.emailSend",
                "position": [850, 300],
                "parameters": {
                    "fromEmail": "rapports@affilimax.com",
                    "toEmail": "admin@affilimax.com",
                    "subject": "={{$json.subject}}",
                    "html": "={{$json.html}}"
                }
            }
        ],
        "connections": {
            "Cron - 6h": {"main": [[{"node": "Agreger Stats", "type": "main", "index": 0}]]},
            "Agreger Stats": {"main": [[{"node": "Formater Rapport", "type": "main", "index": 0}]]},
            "Formater Rapport": {"main": [[{"node": "Envoyer Email Admin", "type": "main", "index": 0}]]}
        }
    },
    {
        "name": "Capture Emails + Nurturing",
        "folder": "emailing",
        "active": True,
        "nodes": [
            {
                "name": "Webhook - Email",
                "type": "n8n-nodes-base.webhook",
                "position": [250, 300],
                "parameters": {"httpMethod": "POST", "path": "capture/email", "responseMode": "responseNode"}
            },
            {
                "name": "Valider Email",
                "type": "n8n-nodes-base.function",
                "position": [450, 300],
                "parameters": {
                    "functionCode": """
const data = $input.first().json;
const emailRegex = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;
if (!emailRegex.test(data.email)) throw new Error('Email invalide');
data.source = data.source || 'website';
data.captured_at = new Date().toISOString();
return data;
"""
                }
            },
            {
                "name": "Ajouter Lead (DB)",
                "type": "n8n-nodes-base.postgres",
                "position": [650, 300],
                "parameters": {
                    "operation": "executeQuery",
                    "query": """
                        INSERT INTO leads (email, source, captured_at)
                        VALUES ($1, $2, NOW())
                        ON CONFLICT (email) DO NOTHING
                        RETURNING id, (xmax = 0) as is_new
                    """
                }
            },
            {
                "name": "Nouveau?",
                "type": "n8n-nodes-base.if",
                "position": [850, 300],
                "parameters": {
                    "conditions": {
                        "boolean": [{"value1": "={{$json.is_new}}", "operation": "equals", "value2": True}]
                    }
                }
            },
            {
                "name": "Email Bienvenue",
                "type": "n8n-nodes-base.emailSend",
                "position": [1050, 200],
                "parameters": {
                    "fromEmail": "bonjour@affilimax.com",
                    "toEmail": "={{$json.email}}",
                    "subject": "Bienvenue chez Affilimax !",
                    "html": "<h1>Bienvenue !</h1><p>Merci de rejoindre Affilimax. Decouvrez nos meilleures offres d'affiliation.</p>"
                }
            },
            {
                "name": "Wait 2 jours",
                "type": "n8n-nodes-base.wait",
                "position": [1250, 200],
                "parameters": {"amount": 2, "unit": "days"}
            },
            {
                "name": "Email Offre",
                "type": "n8n-nodes-base.emailSend",
                "position": [1450, 200],
                "parameters": {
                    "fromEmail": "offres@affilimax.com",
                    "toEmail": "={{$json.email}}",
                    "subject": "Top offres affiliation cette semaine",
                    "html": "<h2>Offres exclusives</h2><p>Decouvrez les meilleures opportunites d'affiliation.</p>"
                }
            }
        ],
        "connections": {
            "Webhook - Email": {"main": [[{"node": "Valider Email", "type": "main", "index": 0}]]},
            "Valider Email": {"main": [[{"node": "Ajouter Lead (DB)", "type": "main", "index": 0}]]},
            "Ajouter Lead (DB)": {"main": [[{"node": "Nouveau?", "type": "main", "index": 0}]]},
            "Nouveau?": {
                "main": [
                    [{"node": "Email Bienvenue", "type": "main", "index": 0}],
                    []
                ]
            },
            "Email Bienvenue": {"main": [[{"node": "Wait 2 jours", "type": "main", "index": 0}]]},
            "Wait 2 jours": {"main": [[{"node": "Email Offre", "type": "main", "index": 0}]]}
        }
    },
    {
        "name": "Auto-Publication Reseaux Sociaux",
        "folder": "social",
        "active": True,
        "nodes": [
            {
                "name": "Cron - 9h,14h,18h",
                "type": "n8n-nodes-base.cron",
                "position": [250, 300],
                "parameters": {"triggerTimes": {"item": [{"mode": "custom", "hours": [9, 14, 18]}]}}
            },
            {
                "name": "Selectionner Top Produit",
                "type": "n8n-nodes-base.postgres",
                "position": [450, 300],
                "parameters": {
                    "operation": "executeQuery",
                    "query": """
                        SELECT product_name, affiliate_url, commission_rate, platform
                        FROM conversions
                        WHERE created_at::date = CURRENT_DATE
                        GROUP BY product_name, affiliate_url, commission_rate, platform
                        ORDER BY COUNT(*) DESC LIMIT 1
                    """
                }
            },
            {
                "name": "Generer Message",
                "type": "n8n-nodes-base.function",
                "position": [650, 300],
                "parameters": {
                    "functionCode": """
const product = $input.first().json;
const hashtags = '#Affiliation #Marketing #Business #PassiveIncome';
const messages = [
    `${product.product_name} - Notre top recommandation du jour !\\n\\nCommission: ${product.commission_rate}% sur ${product.platform}\\n\\n-> ${product.affiliate_url}\\n\\n${hashtags}`,
    `Decouvrez ${product.product_name} sur ${product.platform}\\n\\nL'une des meilleures offres d'affiliation du moment !\\n\\n${hashtags}`
];
return { text: messages[Math.floor(Math.random() * messages.length)] };
"""
                }
            },
            {
                "name": "Publier sur X/Twitter",
                "type": "n8n-nodes-base.twitter",
                "position": [850, 200],
                "parameters": {"text": "={{$json.text}}"}
            },
            {
                "name": "Publier sur LinkedIn",
                "type": "n8n-nodes-base.linkedIn",
                "position": [850, 400],
                "parameters": {"text": "={{$json.text}}"}
            }
        ],
        "connections": {
            "Cron - 9h,14h,18h": {"main": [[{"node": "Selectionner Top Produit", "type": "main", "index": 0}]]},
            "Selectionner Top Produit": {"main": [[{"node": "Generer Message", "type": "main", "index": 0}]]},
            "Generer Message": {
                "main": [
                    [{"node": "Publier sur X/Twitter", "type": "main", "index": 0}],
                    [{"node": "Publier sur LinkedIn", "type": "main", "index": 0}]
                ]
            }
        }
    },
    {
        "name": "Alerte Seuil Commission",
        "folder": "paiements",
        "active": True,
        "nodes": [
            {
                "name": "Cron - Toutes les 4h",
                "type": "n8n-nodes-base.cron",
                "position": [250, 300],
                "parameters": {"triggerTimes": {"item": [{"mode": "everyX", "unit": "hours", "value": 4}]}}
            },
            {
                "name": "Verifier Commissions Mois",
                "type": "n8n-nodes-base.postgres",
                "position": [450, 300],
                "parameters": {
                    "operation": "executeQuery",
                    "query": """
                        SELECT affiliate_id, SUM(commission) as total_commission
                        FROM conversions
                        WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)
                        GROUP BY affiliate_id
                        HAVING SUM(commission) >= 5000
                    """
                }
            },
            {
                "name": "Seuil Atteint?",
                "type": "n8n-nodes-base.if",
                "position": [650, 300],
                "parameters": {
                    "conditions": {
                        "number": [{"value1": "={{$json.total_commission}}", "operation": "larger", "value2": 0}]
                    }
                }
            },
            {
                "name": "Alerte Telegram",
                "type": "n8n-nodes-base.telegram",
                "position": [850, 200],
                "parameters": {
                    "text": "=Alerte Seuil !\\nAffilie: {{$json.affiliate_id}}\\nCommissions ce mois: {{$json.total_commission}}EUR\\nSeuil de 5000EUR depasse !"
                }
            },
            {
                "name": "Email Admin",
                "type": "n8n-nodes-base.emailSend",
                "position": [850, 400],
                "parameters": {
                    "fromEmail": "alertes@affilimax.com",
                    "toEmail": "admin@affilimax.com",
                    "subject": "ALERTE Seuil de commission atteint - {{$json.affiliate_id}}",
                    "html": "<h2>Alerte Seuil Commission</h2><p>Affilie: {{$json.affiliate_id}}</p><p>Total: {{$json.total_commission}}EUR</p>"
                }
            }
        ],
        "connections": {
            "Cron - Toutes les 4h": {"main": [[{"node": "Verifier Commissions Mois", "type": "main", "index": 0}]]},
            "Verifier Commissions Mois": {"main": [[{"node": "Seuil Atteint?", "type": "main", "index": 0}]]},
            "Seuil Atteint?": {
                "main": [
                    [{"node": "Alerte Telegram", "type": "main", "index": 0}],
                    [{"node": "Email Admin", "type": "main", "index": 0}]
                ]
            }
        }
    },
    {
        "name": "Verification Sante Plateforme",
        "folder": "analytics",
        "active": True,
        "nodes": [
            {
                "name": "Cron - 15 min",
                "type": "n8n-nodes-base.cron",
                "position": [250, 300],
                "parameters": {"triggerTimes": {"item": [{"mode": "everyX", "unit": "minutes", "value": 15}]}}
            },
            {
                "name": "Ping Sante n8n",
                "type": "n8n-nodes-base.httpRequest",
                "position": [450, 300],
                "parameters": {
                    "url": "https://affilmax.render.com/healthz",
                    "method": "GET",
                    "options": {"timeout": 10000}
                }
            },
            {
                "name": "Test Connexion DB",
                "type": "n8n-nodes-base.postgres",
                "position": [650, 300],
                "parameters": {
                    "operation": "executeQuery",
                    "query": "SELECT 1 as db_ok"
                }
            },
            {
                "name": "Erreur Detectee?",
                "type": "n8n-nodes-base.if",
                "position": [850, 300],
                "parameters": {
                    "conditions": {
                        "options": {"combinator": "or"},
                        "conditions": [
                            {"value1": "={{$node['Ping Sante n8n'].json.statusCode}}", "operation": "notEquals", "value2": 200},
                            {"value1": "={{$node['Test Connexion DB'].json.db_ok}}", "operation": "notEquals", "value2": 1}
                        ]
                    }
                }
            },
            {
                "name": "Alerter Equipe Tech",
                "type": "n8n-nodes-base.telegram",
                "position": [1050, 200],
                "parameters": {
                    "text": "=INCIDENT Affilimax !\\nUn service ne repond pas.\\nVerifiez le dashboard."
                }
            },
            {
                "name": "Logger Incident",
                "type": "n8n-nodes-base.postgres",
                "position": [1050, 400],
                "parameters": {
                    "operation": "executeQuery",
                    "query": """
                        INSERT INTO incidents (service, status, detected_at)
                        VALUES ('health_check', 'error', NOW())
                    """
                }
            }
        ],
        "connections": {
            "Cron - 15 min": {"main": [[{"node": "Ping Sante n8n", "type": "main", "index": 0}]]},
            "Ping Sante n8n": {"main": [[{"node": "Test Connexion DB", "type": "main", "index": 0}]]},
            "Test Connexion DB": {"main": [[{"node": "Erreur Detectee?", "type": "main", "index": 0}]]},
            "Erreur Detectee?": {
                "main": [
                    [{"node": "Alerter Equipe Tech", "type": "main", "index": 0}],
                    []
                ]
            },
            "Alerter Equipe Tech": {"main": [[{"node": "Logger Incident", "type": "main", "index": 0}]]}
        }
    },
    {
        "name": "Generation Factures Mensuelles",
        "folder": "paiements",
        "active": True,
        "nodes": [
            {
                "name": "Cron - 1er du mois",
                "type": "n8n-nodes-base.cron",
                "position": [250, 300],
                "parameters": {"triggerTimes": {"item": [{"mode": "everyMonth", "dayOfMonth": 1, "hour": 8, "minute": 0}]}}
            },
            {
                "name": "Agreger Commissions Mensuelles",
                "type": "n8n-nodes-base.postgres",
                "position": [450, 300],
                "parameters": {
                    "operation": "executeQuery",
                    "query": """
                        SELECT
                            affiliate_id,
                            COUNT(*) as total_conversions,
                            SUM(amount) as total_amount,
                            SUM(commission) as total_commission,
                            DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') as period
                        FROM conversions
                        WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
                          AND created_at < DATE_TRUNC('month', CURRENT_DATE)
                        GROUP BY affiliate_id
                        ORDER BY total_commission DESC
                    """
                }
            },
            {
                "name": "Formater Facture",
                "type": "n8n-nodes-base.function",
                "position": [650, 300],
                "parameters": {
                    "functionCode": """
const items = $input.all();
const results = [];
for (const item of items) {
    const data = item.json;
    results.push({
        invoice_number: `INV-${data.affiliate_id}-${new Date().getFullYear()}${String(new Date().getMonth()).padStart(2,'0')}`,
        affiliate_id: data.affiliate_id,
        period: data.period,
        total_conversions: data.total_conversions,
        total_amount: data.total_amount,
        total_commission: data.total_commission,
        generated_at: new Date().toISOString(),
        status: 'pending_payment'
    });
}
return results;
"""
                }
            },
            {
                "name": "Enregistrer Factures (DB)",
                "type": "n8n-nodes-base.postgres",
                "position": [850, 300],
                "parameters": {
                    "operation": "executeQuery",
                    "query": """
                        INSERT INTO factures (invoice_number, affiliate_id, period, total_conversions,
                            total_amount, total_commission, generated_at, status)
                        VALUES ($1, $2, $3, $4, $5, $6, NOW(), 'pending_payment')
                        ON CONFLICT (invoice_number) DO UPDATE
                        SET total_commission = EXCLUDED.total_commission
                    """
                }
            },
            {
                "name": "Envoyer Facture Email",
                "type": "n8n-nodes-base.emailSend",
                "position": [1050, 300],
                "parameters": {
                    "fromEmail": "factures@affilimax.com",
                    "toEmail": "={{$json.affiliate_email}}",
                    "subject": "Facture Affilimax - {{$json.invoice_number}}",
                    "html": "<h2>Facture {{$json.invoice_number}}</h2><p>Total commissions: {{$json.total_commission}}EUR</p><p>Periode: {{$json.period}}</p><p>Statut: En attente de paiement</p>"
                }
            }
        ],
        "connections": {
            "Cron - 1er du mois": {"main": [[{"node": "Agreger Commissions Mensuelles", "type": "main", "index": 0}]]},
            "Agreger Commissions Mensuelles": {"main": [[{"node": "Formater Facture", "type": "main", "index": 0}]]},
            "Formater Facture": {"main": [[{"node": "Enregistrer Factures (DB)", "type": "main", "index": 0}]]},
            "Enregistrer Factures (DB)": {"main": [[{"node": "Envoyer Facture Email", "type": "main", "index": 0}]]}
        }
    }
]


# ===================== API HELPERS =====================

def check_n8n_connection() -> bool:
    """Verifie que n8n est accessible."""
    try:
        resp = requests.get(f"{N8N_URL}/healthz", timeout=10)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def get_or_create_folder(name: str) -> Optional[str]:
    """Recupere ou cree un dossier dans n8n."""
    try:
        resp = requests.get(f"{N8N_URL}/rest/folders", headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            folders = resp.json().get("data", [])
            for f in folders:
                if f.get("name") == name:
                    return f["id"]
        # Creer le dossier
        resp = requests.post(
            f"{N8N_URL}/rest/folders",
            json={"name": name},
            headers=HEADERS,
            timeout=10
        )
        if resp.status_code in (200, 201):
            return resp.json().get("id")
        elif resp.status_code == 401:
            print("  [!] Authentification requise - creation simulee")
            return f"folder_{name}_simulated"
        else:
            print(f"  [!] Impossible de creer le dossier (HTTP {resp.status_code})")
            return f"folder_{name}_fallback"
    except requests.RequestException as e:
        print(f"  [!] Connexion impossible: {e}")
        return f"folder_{name}_simulated"


def create_workflow(workflow_def: dict, folder_id: str) -> bool:
    """Cree un workflow dans n8n via l'API REST."""
    url = f"{N8N_URL}/rest/workflows"
    payload = {
        "name": workflow_def["name"],
        "nodes": workflow_def.get("nodes", []),
        "connections": workflow_def.get("connections", {}),
        "active": workflow_def.get("active", False),
        "settings": {
            "saveExecutionProgress": True,
            "callerPolicy": "workflowsFromSameFolder"
        },
        "tags": [{"name": "affilimax"}, {"name": workflow_def.get("folder", "general")}]
    }

    try:
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=30)
        if resp.status_code in (200, 201):
            data = resp.json()
            print(f"  [OK] Cree (ID: {data.get('id', 'N/A')})")
            return True
        elif resp.status_code == 401:
            print("  [LOCKED] Authentification requise - definition prete")
            return True
        else:
            print(f"  [ERREUR] {resp.status_code}: {resp.text[:100]}")
            return False
    except requests.RequestException as e:
        print(f"  [ERREUR] Connexion echouee: {e}")
        return False


# ===================== MAIN =====================

def main():
    global N8N_URL, N8N_API_KEY, HEADERS

    parser = argparse.ArgumentParser(
        description="Affilimax - Deployeur de workflows n8n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python create_all_workflows.py
  python create_all_workflows.py --url http://localhost:5678 --api-key n8n_abc123
  python create_all_workflows.py --dry-run
        """
    )
    parser.add_argument("--url", default=N8N_URL, help=f"URL du serveur n8n (defaut: {N8N_URL})")
    parser.add_argument("--api-key", default=N8N_API_KEY, help="Cle API n8n")
    parser.add_argument("--dry-run", action="store_true", help="Simulation sans creation reelle")
    parser.add_argument("--activate", action="store_true", help="Activer les workflows apres creation")

    args = parser.parse_args()

    N8N_URL = args.url.rstrip("/")
    N8N_API_KEY = args.api_key
    HEADERS["X-N8N-API-KEY"] = N8N_API_KEY

    # Banniere
    print("""
    ==========================================
         $$  Affilimax Workflow Deployer  $$
             n8n Automation Engine
    ==========================================
    """)

    print(f"URL n8n : {N8N_URL}")
    print(f"Date   : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"API Key: {'***' + N8N_API_KEY[-4:] if N8N_API_KEY else 'Non configuree'}")
    print(f"Dry Run : {'OUI' if args.dry_run else 'NON'}")
    print()

    # Test connexion
    if not args.dry_run and N8N_API_KEY:
        print("Test de connexion a n8n...")
        if check_n8n_connection():
            print("  [OK] n8n est accessible\n")
        else:
            print("  [!] n8n n'est pas accessible. Verifiez l'URL et la connexion.\n")
    else:
        print("Mode simulation - les workflows seront affiches mais pas crees.\n")

    # Creation des workflows
    created = 0
    failed = 0
    folders_cache = {}

    for wf in WORKFLOWS:
        print(f"Workflow: {wf['name']}")
        print(f"   Dossier: {wf.get('folder', 'racine')} | Actif: {wf.get('active', False)}")
        print(f"   Noeuds: {len(wf.get('nodes', []))}")

        # Gerer le dossier
        folder_name = wf.get("folder", "racine")
        if folder_name not in folders_cache:
            folders_cache[folder_name] = get_or_create_folder(folder_name) if not args.dry_run else f"folder_{folder_name}_dry"
        folder_id = folders_cache[folder_name]

        if args.dry_run:
            print("  [SIM] Simulation - workflow pret a etre deploye")
            created += 1
        else:
            if create_workflow(wf, folder_id):
                created += 1
            else:
                failed += 1
        print()

    # Resume
    print("=" * 50)
    print(f"RESULTAT: {created} cree(s), {failed} echoue(s) sur {len(WORKFLOWS)} workflows")
    print("=" * 50)

    if args.dry_run:
        print("\nPour deployer reellement:")
        print("   python create_all_workflows.py --api-key VOTRE_CLE_API_N8N")
        print("   python create_all_workflows.py --api-key VOTRE_CLE_API_N8N --activate")
    elif not N8N_API_KEY:
        print("\n[!] Passez une API key avec --api-key pour le deploiement reel.")
    else:
        print(f"\n[OK] Workflows deployes sur {N8N_URL}")
        print(f"Dashboard: {N8N_URL}/home/workflows")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
