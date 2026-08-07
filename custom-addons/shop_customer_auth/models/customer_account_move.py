from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import float_compare


class CustomerAccountMove(models.Model):
    _name = "shop.customer.account.move"
    _description = "Movimiento de Cuenta Corriente"
    _order = "date desc, id desc"
    _check_company_auto = True

    partner_id = fields.Many2one(
        "res.partner", string="Cliente", required=True, index=True,
        ondelete="restrict", check_company=True,
    )
    date = fields.Date(string="Fecha", required=True, default=fields.Date.context_today, index=True)
    move_type = fields.Selection(
        [
            ("sale", "Venta"),
            ("payment", "Cobranza"),
            ("debit_adjustment", "Ajuste débito"),
            ("credit_adjustment", "Ajuste crédito"),
        ],
        string="Tipo", required=True, index=True,
    )
    amount = fields.Monetary(string="Importe", required=True, currency_field="currency_id")
    signed_amount = fields.Monetary(
        string="Importe con signo", compute="_compute_signed_amount", store=True,
        currency_field="currency_id",
    )
    debit = fields.Monetary(string="Debe", compute="_compute_debit_credit", currency_field="currency_id")
    credit = fields.Monetary(string="Haber", compute="_compute_debit_credit", currency_field="currency_id")
    running_balance = fields.Monetary(
        string="Saldo acumulado", compute="_compute_running_balance", currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        "res.currency", string="Moneda", required=True,
        default=lambda self: self.env.company.currency_id,
    )
    company_id = fields.Many2one(
        "res.company", string="Compañía", required=True, index=True,
        default=lambda self: self.env.company,
    )
    pos_order_id = fields.Many2one(
        "pos.order", string="Orden POS", index=True, ondelete="restrict", check_company=True,
    )
    pos_payment_id = fields.Many2one(
        "pos.payment", string="Pago POS", index=True, ondelete="restrict", check_company=True,
    )
    reference = fields.Char(string="Referencia", index=True)
    note = fields.Text(string="Observaciones")
    user_id = fields.Many2one(
        "res.users", string="Usuario", required=True, default=lambda self: self.env.user,
        ondelete="restrict",
    )
    state = fields.Selection(
        [("active", "Activo"), ("cancelled", "Cancelado")],
        string="Estado", required=True, default="active", index=True,
    )

    _unique_pos_payment = models.Constraint(
        "unique (pos_payment_id)",
        "Ya existe un movimiento de cuenta corriente para este pago de POS.",
    )
    _positive_amount = models.Constraint(
        "CHECK(amount > 0)", "El importe debe ser mayor que cero.",
    )

    @api.depends("amount", "move_type", "state")
    def _compute_signed_amount(self):
        positive_types = {"sale", "debit_adjustment"}
        for move in self:
            if move.state == "cancelled":
                move.signed_amount = 0.0
            else:
                move.signed_amount = move.amount if move.move_type in positive_types else -move.amount

    @api.depends("signed_amount")
    def _compute_debit_credit(self):
        for move in self:
            move.debit = max(move.signed_amount, 0.0)
            move.credit = max(-move.signed_amount, 0.0)

    def _compute_running_balance(self):
        for move in self:
            move.running_balance = 0.0
        if not self.ids:
            return
        self.flush_model(["signed_amount", "partner_id", "company_id", "date"])
        self.env.cr.execute("""
            SELECT target.id, COALESCE(SUM(previous.signed_amount), 0)
              FROM shop_customer_account_move target
              LEFT JOIN shop_customer_account_move previous
                ON previous.partner_id = target.partner_id
               AND previous.company_id = target.company_id
               AND (previous.date < target.date
                    OR (previous.date = target.date AND previous.id <= target.id))
             WHERE target.id = ANY(%s)
             GROUP BY target.id
        """, [self.ids])
        balances = dict(self.env.cr.fetchall())
        for move in self:
            move.running_balance = balances.get(move.id, 0.0)

    @api.constrains("amount")
    def _check_amount(self):
        for move in self:
            if float_compare(move.amount, 0.0, precision_rounding=move.currency_id.rounding) <= 0:
                raise ValidationError(_("El importe debe ser mayor que cero."))

    @api.constrains("company_id", "currency_id", "partner_id", "pos_order_id", "pos_payment_id")
    def _check_consistency(self):
        for move in self:
            if move.currency_id != move.company_id.currency_id:
                raise ValidationError(_("La cuenta corriente utiliza la moneda de la compañía."))
            if move.pos_order_id and move.pos_order_id.company_id != move.company_id:
                raise ValidationError(_("La orden POS pertenece a otra compañía."))
            if move.pos_payment_id and move.pos_payment_id.pos_order_id != move.pos_order_id:
                raise ValidationError(_("El pago POS no pertenece a la orden indicada."))
            if move.pos_order_id and move.pos_order_id.partner_id != move.partner_id:
                raise ValidationError(_("El cliente no coincide con el de la orden POS."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
            vals.setdefault("currency_id", company.currency_id.id)
            currency = self.env["res.currency"].browse(vals["currency_id"])
            if float_compare(
                vals.get("amount", 0.0), 0.0, precision_rounding=currency.rounding
            ) <= 0:
                raise ValidationError(_("El importe debe ser mayor que cero."))
            if vals.get("move_type") in ("debit_adjustment", "credit_adjustment"):
                is_pos_refund = vals.get("pos_payment_id") and self.env.context.get("customer_account_pos_sync")
                if not is_pos_refund and not self.env.user.has_group(
                    "shop_customer_auth.group_customer_account_manager"
                ):
                    raise AccessError(_("Sólo un responsable puede registrar ajustes."))
            elif vals.get("move_type") == "sale" and not self.env.context.get(
                "customer_account_pos_sync"
            ):
                raise AccessError(_("Las ventas de cuenta corriente se generan únicamente desde POS."))
        return super().create(vals_list)

    def write(self, vals):
        protected = {"partner_id", "amount", "move_type", "pos_order_id", "pos_payment_id", "company_id", "currency_id"}
        if protected.intersection(vals) and self.filtered("pos_payment_id"):
            raise AccessError(_("Los datos económicos de movimientos originados en POS no pueden modificarse."))
        if vals.get("state") == "cancelled" and not self.env.user.has_group(
            "shop_customer_auth.group_customer_account_manager"
        ):
            raise AccessError(_("Sólo un responsable puede cancelar movimientos."))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_("Los movimientos de cuenta corriente no se eliminan; deben cancelarse."))

    def action_cancel(self):
        self.write({"state": "cancelled"})
        return True

    def action_reactivate(self):
        if not self.env.user.has_group("shop_customer_auth.group_customer_account_manager"):
            raise AccessError(_("Sólo un responsable puede reactivar movimientos."))
        self.write({"state": "active"})
        return True
