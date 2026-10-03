{
    "name": "L'Art du Bâti - Investor Home and Stock Monitor",
    "version": "18.0.1.0.0",
    "summary": "Stock attributes, unified ownership and per-user stock access "
    "for the investor stock monitor.",
    "author": "L'Art du Bâti",
    "license": "LGPL-3",
    "category": "Inventory/Inventory",
    "depends": ["stock", "maintenance_shareholder_equipment"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ownership_data.xml",
        "views/stock_location_views.xml",
        "views/maintenance_equipment_views.xml",
        "views/stock_rental_views.xml",
        "views/stock_access_views.xml",
        "views/res_users_views.xml",
    ],
    "installable": True,
    "application": False,
}
