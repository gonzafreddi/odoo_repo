from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    x_is_store_pickup = fields.Boolean(
        string="Retiro en local",
        default=False,
        index=True,
        help="Indica que el cliente retirará el pedido en el local.",
    )
    x_logistics_status = fields.Selection(
        selection=[
            ("pending", "Pendiente"),
            ("preparing", "En preparación"),
            ("shipped", "Enviado"),
            ("ready_pickup", "Listo para retirar"),
            ("delivered", "Entregado"),
            ("canceled", "Cancelado"),
        ],
        string="Estado logístico",
        default="pending",
        required=True,
        index=True,
        tracking=True,
        help="Estado interno de preparación y entrega del pedido.",
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

    @api.constrains("x_is_store_pickup", "x_logistics_status")
    def _check_logistics_status_matches_delivery_method(self):
        for order in self:
            if order.x_is_store_pickup and order.x_logistics_status == "shipped":
                raise ValidationError(
                    "Un retiro en local no puede tener estado Enviado."
                )
            if not order.x_is_store_pickup and (
                order.x_logistics_status == "ready_pickup"
            ):
                raise ValidationError(
                    "Un envío a domicilio no puede quedar Listo para retirar."
                )
