from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    x_is_store_pickup = fields.Boolean(
        string="Retiro en local",
        default=False,
        index=True,
        help="Indica que el cliente retirará el pedido en el local.",
    )
    x_shipping_phone = fields.Char(
        string="Teléfono de entrega",
        help="Teléfono de contacto para coordinar la entrega.",
    )
    x_shipping_street = fields.Char(string="Calle")
    x_shipping_street_number = fields.Char(string="Número")
    x_shipping_floor_apartment = fields.Char(string="Piso / departamento")
    x_shipping_city = fields.Char(string="Localidad", index=True)
    x_shipping_state_id = fields.Many2one(
        comodel_name="res.country.state",
        string="Provincia",
        index=True,
        ondelete="restrict",
    )
    x_shipping_zip = fields.Char(string="Código postal", index=True)
    x_shipping_notes = fields.Text(
        string="Referencias de entrega",
        help="Entre calles, horarios u otras indicaciones para la entrega.",
    )
    x_shipping_real_cost = fields.Monetary(
        string="Costo real de envío",
        currency_field="currency_id",
        help="Costo cotizado del envío. Se completa manualmente.",
    )
