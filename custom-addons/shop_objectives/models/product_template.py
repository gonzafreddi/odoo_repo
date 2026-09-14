from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    objective_line_ids = fields.One2many(
        "shop.product.objective.line",
        "product_tmpl_id",
    )
