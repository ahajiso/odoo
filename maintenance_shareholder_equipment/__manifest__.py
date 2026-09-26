{
    "name": "Maintenance - Shareholder-Owned Equipment",
    "version": "18.0.1.0.2",
    "summary": "Tracking of tools/equipment provided by a shareholder "
                "(owner, values, status, wear/depreciation) and repair cost.",
    "author": "UBI Solutions",
    "license": "LGPL-3",
    "category": "Manufacturing/Maintenance",
    "depends": ["maintenance", "stock"],
    "data": [
        "views/maintenance_equipment_views.xml",
        "views/maintenance_request_views.xml",
    ],
    "installable": True,
    "application": False,
}
