from odoo import api, fields, models

CASH_DISCOUNT_PARAM = "shop_config.cash_discount_percent"


def get_cash_discount_percent(env):
    """% de descuento para efectivo/transferencia configurado en la tienda."""
    try:
        value = float(env["ir.config_parameter"].sudo().get_param(CASH_DISCOUNT_PARAM) or 0.0)
    except ValueError:
        return 0.0
    return min(max(value, 0.0), 99.99)


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

    combo_cost = fields.Float(
        string="Costo del combo",
        compute="_compute_combo_cost",
        digits="Product Price",
        groups="base.group_user",
        help="Suma del costo de los productos del combo por la cantidad de cada "
             "línea. Si una línea tiene varias opciones se toma la más cara.",
    )

    @api.depends(
        "type",
        "combo_ids.qty_max",
        "combo_ids.combo_item_ids.product_id.standard_price",
    )
    @api.depends_context("company")
    def _compute_combo_cost(self):
        for product in self:
            product.combo_cost = sum(
                max(combo.combo_item_ids.product_id.mapped("standard_price"), default=0.0)
                * max(combo.qty_max or 1, 1)
                for combo in product.combo_ids
            ) if product.type == "combo" else 0.0

    @api.depends("list_price", "standard_price", "combo_cost")
    @api.depends_context("company")
    def _compute_margin_percentage(self):
        for product in self:
            cost = product.combo_cost if product.type == "combo" else product.standard_price
            product.margin_percentage = (
                (product.list_price - cost) / product.list_price
                if product.list_price
                else 0.0
            )

    offer_price = fields.Monetary(
        string="Precio de oferta",
        currency_field="currency_id",
        help="Precio promocional que se aplica cuando la oferta está activa.",
    )

    card_price = fields.Monetary(
        string="Precio tarjeta",
        compute="_compute_payment_prices",
        currency_field="currency_id",
        help="Precio de lista, o el de oferta cuando está activa y es menor.",
    )
    cash_price = fields.Monetary(
        string="Precio efectivo / transferencia",
        compute="_compute_payment_prices",
        currency_field="currency_id",
        help="Precio tarjeta menos el descuento de efectivo configurado en la tienda.",
    )

    @api.depends("list_price", "offer_active", "offer_price")
    def _compute_payment_prices(self):
        discount = get_cash_discount_percent(self.env)
        for product in self:
            card_price = product.list_price
            if product.offer_active and product.offer_price > 0:
                card_price = min(card_price, product.offer_price)
            product.card_price = card_price
            product.cash_price = card_price * (1 - discount / 100)

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_to_load = super()._load_pos_data_fields(config_id)
        return [*fields_to_load, "offer_active", "offer_price"]
