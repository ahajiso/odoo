# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Mentions obligatoires sur les devis et factures d'une entreprise du bâtiment
    # (assurance de responsabilité décennale, art. L.241-1 du Code des assurances
    # et art. 22-2 de la loi n° 96-603 du 5 juillet 1996).
    lartdubati_decennale_assureur = fields.Char(
        string="Assureur décennale",
        help="Nom de la compagnie d'assurance couvrant la responsabilité décennale.",
    )
    lartdubati_decennale_contrat = fields.Char(
        string="N° de contrat décennale",
        help="Numéro du contrat d'assurance de responsabilité décennale.",
    )
    lartdubati_decennale_zone = fields.Char(
        string="Couverture géographique",
        default="France métropolitaine",
        help="Zone géographique couverte par le contrat d'assurance décennale.",
    )
    lartdubati_mentions_btp = fields.Boolean(
        string="Imprimer les mentions BTP",
        default=True,
        help="Ajoute sur les factures les mentions obligatoires du bâtiment : "
             "assurance décennale, pénalités de retard, indemnité forfaitaire de "
             "recouvrement, médiateur de la consommation et gestion des déchets.",
    )
    lartdubati_mediateur = fields.Char(
        string="Médiateur de la consommation",
        help="Nom et coordonnées du médiateur de la consommation, mention "
             "obligatoire pour les clients particuliers (art. L.616-1 du Code "
             "de la consommation).",
    )
    lartdubati_dechets_mention = fields.Text(
        string="Mention déchets (AGEC)",
        default="Les déchets issus du chantier sont collectés et traités par "
                "les filières agréées. Les modalités d'enlèvement, le point de "
                "collecte et le coût de la gestion des déchets figurent au devis "
                "(art. L.541-21-2-3 du Code de l'environnement).",
        help="Mention relative à la gestion des déchets de chantier, obligatoire "
             "sur les devis depuis la loi AGEC.",
    )
