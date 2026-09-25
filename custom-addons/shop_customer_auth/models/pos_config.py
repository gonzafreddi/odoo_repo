from odoo import api, fields, models

from .product_template import get_card_surcharge_percent


class PosConfig(models.Model):
    _inherit = "pos.config"

    shop_card_surcharge_percent = fields.Float(
        string="Recargo tarjeta / Mercado Pago (%)",
        compute="_compute_shop_card_surcharge_percent",
    )

    def _compute_shop_card_surcharge_percent(self):
        surcharge = get_card_surcharge_percent(self.env)
        for config in self:
            config.shop_card_surcharge_percent = surcharge


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    shop_card_surcharge_base = fields.Float(
        string="Precio antes del recargo de tarjeta",
        digits="Product Price",
        help="Precio unitario original cuando se aplicó el recargo de tarjeta en el POS; "
             "0 si la línea no lleva recargo.",
    )

    @api.model
    def _load_pos_data_fields(self, config):
        return [*super()._load_pos_data_fields(config), "shop_card_surcharge_base"]
