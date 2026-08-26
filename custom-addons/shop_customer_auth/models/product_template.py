from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    margin_percentage = fields.Float(
        string="Margen (%)",
        compute="_compute_margin_percentage",
        digits=(12, 4),
        groups="base.group_user",
        help="Rentabilidad calculada como (precio de venta - costo) / precio de venta.",
    )

    offer_active = fields.Boolean(
        string="Oferta activa",
        default=False,
        help="Indica si el precio de oferta debe aplicarse al producto.",
    )

    @api.depends("list_price", "standard_price")
    def _compute_margin_percentage(self):
        for product in self:
            product.margin_percentage = (
                (product.list_price - product.standard_price) / product.list_price
                if product.list_price
                else 0.0
            )

    offer_price = fields.Monetary(
        string="Precio de oferta",
        currency_field="currency_id",
        help="Precio promocional que se aplica cuando la oferta está activa.",
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_to_load = super()._load_pos_data_fields(config_id)
        return [*fields_to_load, "offer_active", "offer_price"]
