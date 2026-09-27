{
    'name': "L'Art du Bâti - Indicateur environnement (Test/Prod)",
    'version': '18.0.1.0.0',
    'category': 'Extra Tools',
    'summary': "Bandeau rouge indiquant qu'on est connecté à une base de TEST",
    'description': """
Indicateur visuel Test / Production
====================================

Affiche un bandeau rouge fixe en haut de l'écran (interface Odoo) dès que
le nom de la base de données se termine par ``_test`` ou ``_staging``.

But : éviter toute confusion entre l'environnement de test
(ex. ``artdubati_test``) et la production (``artdubati``) pendant les
phases de configuration et de validation (facturation, comptabilité,
modules OCA, etc.).

Aucune configuration nécessaire : le bandeau se base uniquement sur le
nom de la base de données courante (``session.db``), donc il apparaît
automatiquement sur toute future base de test créée avec le même
suffixe.
""",
    'author': "L'Art du Bâti",
    'license': 'LGPL-3',
    'depends': ['web'],
    'assets': {
        'web.assets_backend': [
            'lartdubati_env_ribbon/static/src/env_ribbon/env_ribbon.js',
            'lartdubati_env_ribbon/static/src/env_ribbon/env_ribbon.xml',
            'lartdubati_env_ribbon/static/src/env_ribbon/env_ribbon.css',
        ],
    },
    'installable': True,
    'application': False,
}
