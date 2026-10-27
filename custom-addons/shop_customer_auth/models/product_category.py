from odoo import fields, models


class ProductCategory(models.Model):
    _name = "product.category"
    _inherit = ["product.category", "image.mixin"]

    description = fields.Text(string="Descripción")
    active = fields.Boolean(string="Activa", default=True)
