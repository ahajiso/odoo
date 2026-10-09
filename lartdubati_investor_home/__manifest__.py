{
    "name": "L'Art du Bâti - Investor Home and Stock Monitor",
    "version": "18.0.1.6.0",
    "summary": "Stock place type, per-user stock access and a mandatory stock "
    "on equipment for the investor stock monitor.",
    "author": "L'Art du Bâti",
    "license": "LGPL-3",
    "category": "Inventory/Inventory",
    "depends": ["stock", "maintenance_shareholder_equipment", "maintenance_account"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ownership_data.xml",
        "views/stock_access_views.xml",
        "views/res_users_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
}
