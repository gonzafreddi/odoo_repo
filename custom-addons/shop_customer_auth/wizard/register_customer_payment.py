from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class RegisterCustomerPayment(models.TransientModel):
    _name = "shop.customer.account.payment.wizard"
    _description = "Registrar Cobranza de Cuenta Corriente"

    partner_id = fields.Many2one("res.partner", string="Cliente", required=True)
    amount = fields.Monetary(
        string="Importe", required=True, currency_field="currency_id",
    )
    date = fields.Date(string="Fecha", required=True, default=fields.Date.context_today)
    reference = fields.Char(string="Referencia")
    note = fields.Text(string="Observaciones")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", readonly=True,
    )

    def action_confirm(self):
        self.ensure_one()
        if float_compare(
            self.amount, 0.0, precision_rounding=self.currency_id.rounding
        ) <= 0:
            raise ValidationError(_("El importe debe ser mayor que cero."))
        self.env["shop.customer.account.move"].create({
            "partner_id": self.partner_id.id,
            "date": self.date,
            "move_type": "payment",
            "amount": self.amount,
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "reference": self.reference,
            "note": self.note,
            "user_id": self.env.user.id,
        })
        return self.partner_id.action_view_customer_account_moves()
