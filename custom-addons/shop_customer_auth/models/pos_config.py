from odoo import fields, models

from .product_template import get_cash_discount_percent


class PosConfig(models.Model):
    _inherit = "pos.config"

    shop_cash_discount_percent = fields.Float(
        string="Descuento efectivo / transferencia (%)",
        compute="_compute_shop_cash_discount_percent",
    )

    def _compute_shop_cash_discount_percent(self):
        discount = get_cash_discount_percent(self.env)
        for config in self:
            config.shop_cash_discount_percent = discount
