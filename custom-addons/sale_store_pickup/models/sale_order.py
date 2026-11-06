import base64

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    x_is_store_pickup = fields.Boolean(
        string="Retiro en local",
        default=False,
        index=True,
        help="Indica que el cliente retirará el pedido en el local.",
    )
    x_shipping_destination_type = fields.Selection(
        selection=[("home", "Domicilio"), ("agency", "Sucursal Correo Argentino")],
        string="Destino postal",
        default="home",
        index=True,
    )
    x_shipping_agency_code = fields.Char(string="Código de sucursal postal")
    x_shipping_agency_name = fields.Char(string="Sucursal postal")
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
    x_shipping_products_weight_g = fields.Integer(
        string="Peso total de productos (g)",
        readonly=True,
    )
    x_shipping_total_weight_g = fields.Integer(
        string="Peso total de bultos (g)",
        readonly=True,
        help="Incluye el peso de los productos y la tara de todas las cajas.",
    )
    x_shipping_parcels_details = fields.Text(
        string="Detalle de cajas y productos",
        readonly=True,
    )
    x_is_correo_argentino = fields.Boolean(
        string="Envío por Correo Argentino",
        default=False,
        readonly=True,
        copy=False,
        index=True,
    )
    x_correo_quote_snapshot = fields.Text(
        string="Datos de cotización postal",
        readonly=True,
        copy=False,
    )
    x_correo_shipment_status = fields.Selection(
        selection=[
            ("not_requested", "No solicitado"),
            ("requested", "Solicitado manualmente"),
            ("importing", "Importando"),
            ("imported", "Importado en MiCorreo"),
            ("failed", "Error de importación"),
            ("unknown", "Resultado pendiente de revisar"),
        ],
        string="Estado MiCorreo",
        default="not_requested",
        readonly=True,
        copy=False,
        index=True,
        tracking=True,
    )
    x_correo_shipment_created_at = fields.Char(
        string="Fecha de importación MiCorreo",
        readonly=True,
        copy=False,
    )
    x_correo_shipping_id = fields.Char(
        string="ID de envío MiCorreo",
        readonly=True,
        copy=False,
    )
    x_correo_tracking_number = fields.Char(
        string="Número de seguimiento postal",
        readonly=True,
        copy=False,
        index=True,
    )
    x_correo_shipment_error = fields.Text(
        string="Error de envío postal",
        readonly=True,
        copy=False,
    )

    def action_request_correo_shipment(self):
        self.ensure_one()
        if not self.env.user.has_group(
            "sale_store_pickup.group_correo_integration"
        ):
            raise AccessError("No tenés permiso para solicitar el envío postal.")
        if not self.x_is_correo_argentino or self.x_is_store_pickup:
            raise ValidationError(
                "Esta orden no corresponde a un envío de Correo Argentino."
            )
        if not self.x_correo_quote_snapshot:
            raise ValidationError(
                "La orden no tiene guardados los datos de la cotización postal."
            )
        if self.x_correo_shipment_status in ("imported", "unknown", "importing"):
            raise ValidationError(
                "La importación ya se realizó o tiene un resultado pendiente. "
                "Revisá el estado antes de volver a solicitarla."
            )
        self.write({
            "x_correo_shipment_status": "requested",
            "x_correo_shipment_error": False,
        })
        return True

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

    def action_print_shipping_remito(self):
        return self.env.ref(
            "sale_store_pickup.action_report_shipping_remito"
        ).report_action(self)

    def _generate_shipping_remito_attachment(self):
        attachment_model = self.env["ir.attachment"]
        for order in self:
            attachment_name = f"Remito de envío - {order.name}.pdf"
            existing = attachment_model.search([
                ("res_model", "=", order._name),
                ("res_id", "=", order.id),
                ("name", "=", attachment_name),
            ], limit=1)
            if existing:
                continue
            pdf_content, _content_type = self.env[
                "ir.actions.report"
            ]._render_qweb_pdf(
                "sale_store_pickup.action_report_shipping_remito",
                res_ids=order.ids,
            )
            attachment = attachment_model.create({
                "name": attachment_name,
                "type": "binary",
                "datas": base64.b64encode(pdf_content),
                "mimetype": "application/pdf",
                "res_model": order._name,
                "res_id": order.id,
            })
            order.message_post(
                body="Remito de envío generado automáticamente.",
                attachment_ids=attachment.ids,
            )

    def write(self, values):
        orders_to_generate = self.env["sale.order"]
        if values.get("x_logistics_status") == "shipped":
            orders_to_generate = self.filtered(
                lambda order: order.x_logistics_status != "shipped"
            )
        result = super().write(values)
        orders_to_generate._generate_shipping_remito_attachment()
        return result
