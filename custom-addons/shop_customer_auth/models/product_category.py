from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = "product.category"

    description = fields.Text(string="Descripción")
    active = fields.Boolean(string="Activa", default=True)
