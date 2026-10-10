{
    "name": "L'Art du Bâti - Investor Home and Stock Monitor",
    "version": "18.0.3.0.0",
    "summary": "Stock place type, per-user stock access and a mandatory stock "
    "on equipment for the investor stock monitor.",
    "author": "L'Art du Bâti",
    "license": "LGPL-3",
    "category": "Inventory/Inventory",
    "depends": [
        "stock", "maintenance_shareholder_equipment", "maintenance_account",
        "account_asset_management", "contract", "web_quick_start_screen",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ownership_data.xml",
        "views/stock_access_views.xml",
        "views/res_users_views.xml",
        "views/res_config_settings_views.xml",
        "views/stock_monitor_views.xml",
        "views/investor_home_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "lartdubati_investor_home/static/src/stock_monitor/**/*",
            "lartdubati_investor_home/static/src/investor_home/**/*",
        ],
        "web.assets_tests": [
            "lartdubati_investor_home/static/tests/tours/**/*",
        ],
        "web.assets_unit_tests": [
            "lartdubati_investor_home/static/tests/**/*.test.js",
        ],
    },
    "installable": True,
    "application": False,
}
