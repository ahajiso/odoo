{
    'name': "L'Art du Bâti - Facturation BTP",
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': "Taxes autoliquidation sous-traitance BTP, articles de facturation, "
               "activation des taux réduits rénovation/rénovation énergétique",
    'description': """
Facturation BTP - L'Art du Bâti
================================

Ce module prépare la facturation pour une activité de finition / façade
en BTP (main d'œuvre, matériaux, conseil), en couvrant :

1. **Taux de TVA rénovation** : active les taux réduits 10% (travaux de
   rénovation de logements achevés depuis plus de 2 ans) et 5,5%
   (travaux d'amélioration énergétique), désactivés par défaut dans le
   modèle fiscal français d'Odoo. Le taux normal 20% (neuf, conseil)
   reste disponible nativement.

2. **Autoliquidation sous-traitance BTP (Article 283-2 nonies du CGI)** :
   - Une taxe de vente à 0% avec mention légale, à utiliser quand
     L'Art du Bâti intervient en tant que **sous-traitant** (le client
     donneur d'ordre autoliquide la TVA).
   - Trois taxes d'achat à 20% / 10% / 5,5% en auto-liquidation, à
     utiliser quand L'Art du Bâti **fait appel à un sous-traitant**
     (la TVA due par le sous-traitant est autoliquidée et déclarée par
     L'Art du Bâti, collectée et déduite simultanément).
   - Une position fiscale "Sous-traitance BTP" regroupant ces
     correspondances, à affecter au contact concerné (donneur d'ordre
     ou sous-traitant).

   ⚠️ Les cases de déclaration de TVA (CA3) ne sont PAS pré-remplies
   sur ces taxes : à compléter après validation du régime exact par
   l'expert-comptable (voir la fiche du module et le README).

3. **Articles de facturation de base** : main d'œuvre (horaire),
   matériaux de construction, conseil / prestation intellectuelle —
   avec une fiscalité de départ cohérente (10% pour les deux premiers,
   20% pour le conseil, non éligible au taux réduit).

À installer et valider sur une base de test avant toute mise en
production.
""",
    'author': "L'Art du Bâti",
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [],
    'installable': True,
    'application': False,
    'post_init_hook': 'post_init_hook',
}
