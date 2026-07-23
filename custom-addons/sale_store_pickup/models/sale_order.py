from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    x_is_store_pickup = fields.Boolean(
        string="Retiro en local",
        default=False,
        index=True,
        help="Indica que el cliente retirará el pedido en el local.",
    )
