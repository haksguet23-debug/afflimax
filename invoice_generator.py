#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Affilimax - Generateur de Factures PDF
=======================================
Cree des factures PDF professionnelles pour chaque reversement de commission
aux partenaires. Conforme aux normes françaises (SIRET, TVA, numéro de facture).

Utilisation:
    from invoice_generator import generate_invoice
    pdf_path = generate_invoice(partner, payout_record, company_info)
"""

import os
import json
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

BASE_DIR = Path(__file__).parent.resolve()
INVOICES_DIR = BASE_DIR / "invoices"
INVOICES_DIR.mkdir(parents=True, exist_ok=True)

# ==================== INFORMATION DE L'ENTREPRISE ====================

COMPANY_INFO = {
    "nom": "Affilimax SARL",
    "adresse": "12 Rue de la République\n75001 Paris, France",
    "siret": "123 456 789 00012",
    "tva_intra": "FR12 345678900012",
    "rcs": "Paris B 123 456 789",
    "capital": "10 000 EUR",
    "email": "comptabilite@affilimax.com",
    "telephone": "+33 1 23 45 67 89",
    "iban": "FR76 1234 5678 9012 3456 7890 123",
    "bic": "SOGEFRPP",
}


def generate_invoice(partner, payout, company=None):
    """Genère une facture PDF pour un reversement de commission.

    Args:
        partner: dict du partenaire (nom, email, etc.)
        payout: dict du reversement (montant, id, date, etc.)
        company: dict info entreprise (optionnel, utilise COMPANY_INFO par défaut)

    Returns:
        chemin du fichier PDF généré
    """
    if company is None:
        company = COMPANY_INFO

    # Numéro de facture unique
    invoice_num = f"FAC-{datetime.now().strftime('%Y%m')}-{payout['id'][-8:].upper()}"
    output_path = INVOICES_DIR / f"{invoice_num}.pdf"

    pdf = InvoicePDF(company, partner, payout, invoice_num)
    pdf.build()
    pdf.output(str(output_path))

    print(f"  [FACTURE] PDF generee: {output_path}")
    return str(output_path)


class InvoicePDF(FPDF):
    """Classe PDF pour les factures de reversement."""

    def __init__(self, company, partner, payout, invoice_num):
        super().__init__("P", "mm", "A4")
        self.company = company
        self.partner = partner
        self.payout = payout
        self.invoice_num = invoice_num

        # Couleurs du thème Affilimax
        self.gold = (240, 165, 0)
        self.dark = (10, 10, 26)
        self.gray = (100, 116, 139)
        self.light_gray = (241, 245, 249)

    def build(self):
        """Construit la facture complete."""
        self.add_page()
        self._header_block()
        self._partner_block()
        self._invoice_details()
        self._payment_table()
        self._totals()
        self._legal_notice()
        self._footer_block()

    def _header_block(self):
        """En-tête avec logo et info entreprise."""
        # Bandeau doré en haut
        self.set_fill_color(*self.gold)
        self.rect(0, 0, 210, 8, "F")

        # Logo / Nom entreprise
        self.set_y(16)
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(*self.dark)
        self.cell(0, 10, self.company["nom"], ln=True)

        self.set_font("Helvetica", "", 8)
        self.set_text_color(*self.gray)

        # Adresse entreprise (colonne gauche)
        addr_lines = self.company["adresse"].split("\n")
        for line in addr_lines:
            self.cell(0, 4, line, ln=True)

        # SIRET
        self.cell(0, 4, f"SIRET: {self.company['siret']}", ln=True)
        self.cell(0, 4, f"TVA: {self.company['tva_intra']}", ln=True)

        # Titre FACTURE (colonne droite)
        self.set_y(16)
        self.set_font("Helvetica", "B", 28)
        self.set_text_color(*self.gold)
        self.cell(0, 12, "FACTURE", ln=True, align="R")

        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.dark)
        self.cell(0, 6, f"N° {self.invoice_num}", ln=True, align="R")

        # Date
        date_str = datetime.now().strftime("%d/%m/%Y")
        self.cell(0, 6, f"Date: {date_str}", ln=True, align="R")

        # Ligne de séparation
        self.set_y(52)
        self.set_draw_color(*self.gold)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())

    def _partner_block(self):
        """Bloc partenaire (destinataire de la facture)."""
        self.set_y(58)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*self.dark)
        self.cell(0, 6, "DESTINATAIRE", ln=True)

        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.gray)
        self.cell(0, 5, self.partner.get("nom", "Partenaire"), ln=True)
        self.cell(0, 5, self.partner.get("email", ""), ln=True)

        # ID partenaire
        if "id" in self.partner:
            self.cell(0, 5, f"ID: {self.partner['id']}", ln=True)

    def _invoice_details(self):
        """Détails de la facture."""
        self.set_y(90)
        self.set_draw_color(*self.gray)
        self.set_line_width(0.2)
        self.line(10, self.get_y(), 200, self.get_y())
        self.set_y(94)

        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*self.dark)
        self.cell(0, 6, "OBJET DE LA FACTURE", ln=True)

        self.set_font("Helvetica", "", 9)
        self.set_text_color(*self.gray)
        desc = self.payout.get("description", "Reversement de commissions d'affiliation")
        self.cell(0, 5, desc, ln=True)
        self.cell(0, 5, f"Période: {self.payout.get('date_creation', 'N/A')[:10]}", ln=True)
        self.cell(0, 5, f"Mode: {self.payout.get('mode', 'standard').upper()}", ln=True)

    def _payment_table(self):
        """Tableau détaillé du paiement."""
        self.set_y(120)

        # En-tête du tableau
        self.set_fill_color(*self.dark)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 9)

        col_w = [90, 30, 30, 40]  # Largeurs des colonnes
        headers = ["Description", "Quantité", "Taux", "Montant"]

        for i, header in enumerate(headers):
            x = 14 + sum(col_w[:i])
            self.set_xy(x, self.get_y())
            self.cell(col_w[i], 8, header, border=1, fill=True, align="C")

        self.ln(8)

        # Ligne de données
        self.set_fill_color(*self.light_gray)
        self.set_text_color(*self.dark)
        self.set_font("Helvetica", "", 9)

        montant = self.payout["montant"]
        taux_tva = 0.0  # Commission non soumise à TVA (auto-entrepreneur)
        ht = montant
        tva = 0.0
        ttc = montant

        rows = [
            ["Commission d'affiliation", "1", f"{taux_tva:.1f}%", f"{ht:.2f} EUR"],
        ]

        for row in rows:
            for i, cell in enumerate(row):
                x = 14 + sum(col_w[:i])
                self.set_xy(x, self.get_y())
                self.cell(col_w[i], 7, cell, border=1, align="C" if i > 0 else "L")
            self.ln(7)

    def _totals(self):
        """Bloc des totaux."""
        self.set_y(self.get_y() + 4)
        montant = self.payout["montant"]

        # Position à droite
        x_start = 120
        col1_w = 40
        col2_w = 40

        self.set_font("Helvetica", "", 9)
        self.set_text_color(*self.gray)

        # Sous-total HT
        self.set_xy(x_start, self.get_y())
        self.cell(col1_w, 6, "Total HT:", align="R")
        self.cell(col2_w, 6, f"{montant:.2f} EUR", align="R")
        self.ln(6)

        # TVA
        self.set_xy(x_start, self.get_y())
        self.cell(col1_w, 6, "TVA (0%):", align="R")
        self.cell(col2_w, 6, "0.00 EUR", align="R")
        self.ln(6)

        # Ligne de séparation
        self.set_draw_color(*self.gold)
        self.set_line_width(0.5)
        y = self.get_y()
        self.line(x_start, y, 200, y)
        self.set_y(y + 2)

        # Total TTC (gras, plus grand)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*self.gold)
        self.set_xy(x_start, self.get_y())
        self.cell(col1_w, 8, "TOTAL TTC:", align="R")
        self.cell(col2_w, 8, f"{montant:.2f} EUR", align="R")
        self.ln(8)

        # Montant en toutes lettres
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*self.gray)
        self.cell(0, 5, f"Arrêtée la présente facture à la somme de {montant:.2f} EUR.", ln=True)

    def _legal_notice(self):
        """Mentions légales en bas de page."""
        self.set_y(230)

        self.set_font("Helvetica", "", 7)
        self.set_text_color(*self.gray)

        notices = [
            "Conditions de paiement : Virement bancaire sous 30 jours.",
            f"IBAN: {self.company['iban']} - BIC: {self.company['bic']}",
            f"RCS {self.company['rcs']} - Capital social: {self.company['capital']}",
            f"TVA intracommunautaire: {self.company['tva_intra']}",
            "En cas de retard de paiement, pénalité de 3 fois le taux d'intérêt légal.",
            "Indemnité forfaitaire de recouvrement : 40 EUR (art. L.441-10 C.com.).",
        ]
        for notice in notices:
            self.cell(0, 3.5, notice, ln=True)

    def _footer_block(self):
        """Pied de page."""
        self.set_y(-20)
        self.set_fill_color(*self.gold)
        self.rect(0, self.get_y(), 210, 0.5, "F")

        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*self.gray)
        self.cell(0, 10, f"Affilimax - Facture {self.invoice_num} - Page {{nb}}", align="C")


# ==================== API ====================

def get_invoice_path(payout_id):
    """Retourne le chemin de la facture pour un payout ID."""
    for f in INVOICES_DIR.glob("*.pdf"):
        if payout_id in f.stem or payout_id[-8:].upper() in f.stem:
            return str(f)
    return None


def list_invoices():
    """Liste toutes les factures generees."""
    invoices = []
    for f in sorted(INVOICES_DIR.glob("*.pdf"), reverse=True):
        size_kb = round(f.stat().st_size / 1024, 1)
        invoices.append({
            "filename": f.name,
            "path": str(f),
            "size_kb": size_kb,
            "date": datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
        })
    return invoices


def generate_invoice_for_payout(partner_id, payout_id):
    """Genere une facture pour un payout existant.
    
    Args:
        partner_id: ID du partenaire
        payout_id: ID du reversement
    
    Returns:
        chemin de la facture ou None
    """
    # Charger les données
    from stripe_config import get_partner, load_partners

    partner = get_partner(partner_id)
    if not partner:
        print(f"  [FACTURE] Partenaire introuvable: {partner_id}")
        return None

    # Trouver le payout dans l'historique du partenaire
    payout = None
    for p in partner.get("payouts", []):
        if p.get("id") == payout_id:
            payout = p
            break

    if not payout:
        # Chercher aussi dans les transactions
        for t in partner.get("transactions", []):
            if t.get("source") == payout_id:
                payout = {
                    "id": payout_id,
                    "montant": abs(t.get("montant", 0)),
                    "date_creation": t.get("date", ""),
                    "statut": t.get("statut", "completed"),
                    "mode": "demo",
                    "description": f"Reversement commissions - {partner['nom']}"
                }
                break

    if not payout:
        print(f"  [FACTURE] Payout introuvable: {payout_id}")
        return None

    return generate_invoice(partner, payout)


# ==================== CLI ====================

if __name__ == "__main__":
    import sys

    if "--list" in sys.argv:
        invoices = list_invoices()
        print(f"\nFactures generees ({len(invoices)}):")
        for inv in invoices:
            print(f"  {inv['filename']} ({inv['size_kb']} KB) - {inv['date']}")
        print()

    elif "--test" in sys.argv:
        # Générer une facture de test
        test_partner = {
            "id": "demo_partner_1",
            "nom": "Sophie Martin",
            "email": "sophie@example.com",
        }
        test_payout = {
            "id": "po_demo_TEST001",
            "montant": 147.80,
            "devise": "EUR",
            "date_creation": "2026-07-06T18:30:00Z",
            "date_fin": "2026-07-09T18:30:00Z",
            "statut": "completed",
            "mode": "demo",
            "description": "Reversement commissions - Sophie Martin",
        }
        path = generate_invoice(test_partner, test_payout)
        print(f"\nFacture de test generee: {path}\n")

    else:
        print("Usage: python invoice_generator.py [--test | --list]")
