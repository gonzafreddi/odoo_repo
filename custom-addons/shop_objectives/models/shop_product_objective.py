from odoo import fields, models


class ShopProductObjective(models.Model):
    _name = "shop.product.objective"
    _description = "Objetivo comercial de productos"
    _order = "sequence, id"

    name = fields.Char(required=True)
    # The slug is expected to be normalized by its caller; normalization is not automatic yet.
    slug = fields.Char(required=True, index=True)
    short_description = fields.Char()
    description = fields.Html()
    image = fields.Image()
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    line_ids = fields.One2many(
        "shop.product.objective.line",
        "objective_id",
    )

    _slug_unique = models.Constraint(
        "unique(slug)",
        "El slug del objetivo debe ser único.",
    )
