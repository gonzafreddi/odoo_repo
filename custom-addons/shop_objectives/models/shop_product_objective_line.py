from odoo import fields, models


class ShopProductObjectiveLine(models.Model):
    _name = "shop.product.objective.line"
    _description = "Producto de un objetivo comercial"
    _order = "sequence, id"

    objective_id = fields.Many2one(
        "shop.product.objective",
        required=True,
        ondelete="cascade",
    )
    product_tmpl_id = fields.Many2one(
        "product.template",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    featured = fields.Boolean(default=False)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "shop_product_objective_line_unique",
            "unique(objective_id, product_tmpl_id)",
            "Un producto solo puede aparecer una vez por objetivo.",
        ),
    ]
