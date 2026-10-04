from odoo import fields, models

OWNERSHIP_SELECTION = [
    ("owned", "Owned"),
    ("borrowed", "Borrowed"),
    ("rented", "Rented"),
    ("lent_out", "Lent Out"),
]


class OwnershipType(models.Model):
    _name = "lartdubati.ownership.type"
    _description = "Ownership Type"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Selection(OWNERSHIP_SELECTION, required=True)
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        ("code_unique", "unique(code)", "Each ownership type can only exist once."),
    ]


class ItemFamily(models.Model):
    _name = "lartdubati.item.family"
    _description = "Item Family"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Selection(
        [("asset", "Asset"), ("consumable", "Consumable")], required=True
    )
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        ("code_unique", "unique(code)", "Each item family can only exist once."),
    ]
