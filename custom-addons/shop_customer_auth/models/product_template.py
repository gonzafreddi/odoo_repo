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

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_to_load = super()._load_pos_data_fields(config_id)
        return [*fields_to_load, "offer_active", "offer_price"]
