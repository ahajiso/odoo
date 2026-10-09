{
    "name": "L'Art du Bâti - Stock Monitor (mock-up, phase 3)",
    "version": "18.0.0.1.0",
    "summary": "Throwaway mock-up of the stock monitor dashboard, static demo data. "
    "Never installed on a server.",
    "author": "L'Art du Bâti",
    "license": "LGPL-3",
    "depends": ["web"],
    "data": ["views/actions.xml"],
    "assets": {
        "web.assets_backend": [
            "lartdubati_stock_monitor_mockup/static/src/**/*",
        ],
    },
    "installable": True,
}
