from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class ResPartner(models.Model):
    _inherit = "res.partner"

    current_account_balance = fields.Monetary(
        string="Saldo actual", compute="_compute_customer_account",
        currency_field="customer_account_currency_id", search="_search_current_account_balance",
    )
    credit_limit = fields.Float(
        string="Límite de crédito", company_dependent=True,
        digits="Product Price",
    )
    available_credit = fields.Monetary(
        string="Disponible", compute="_compute_customer_account",
        currency_field="customer_account_currency_id",
    )
    customer_account_move_count = fields.Integer(
        string="Movimientos", compute="_compute_customer_account",
    )
    last_customer_account_move_date = fields.Date(
        string="Último movimiento", compute="_compute_customer_account",
    )
    customer_account_over_limit = fields.Boolean(
        string="Sobre límite", compute="_compute_customer_account",
        search="_search_customer_account_over_limit",
    )
    customer_account_currency_id = fields.Many2one(
        "res.currency", compute="_compute_customer_account_currency",
    )
    customer_account_move_ids = fields.One2many(
        "shop.customer.account.move", "partner_id", string="Movimientos de Cuenta Corriente",
        readonly=True,
    )
    shop_customer_auth_ids = fields.One2many(
        "shop.customer.auth", "partner_id", string="Credenciales de tienda",
    )
    is_web_registered_customer = fields.Boolean(
        string="Registrado en la web", store=True,
        compute="_compute_is_web_registered_customer",
        help="El cliente creó su cuenta desde la tienda web.",
    )

    @api.depends(
        "shop_customer_auth_ids",
        "shop_customer_auth_ids.register_source",
        "shop_customer_auth_ids.active",
    )
    def _compute_is_web_registered_customer(self):
        for partner in self:
            partner.is_web_registered_customer = any(
                auth.register_source == "web"
                for auth in partner.shop_customer_auth_ids
            )

    @api.depends_context("company", "allowed_company_ids")
    def _compute_customer_account_currency(self):
        for partner in self:
            partner.customer_account_currency_id = self.env.company.currency_id

    @api.depends(
        "customer_account_move_ids.signed_amount",
        "customer_account_move_ids.date",
    )
    @api.depends_context("company", "allowed_company_ids")
    def _compute_customer_account(self):
        company = self.env.company
        grouped = self.env["shop.customer.account.move"].sudo()._read_group(
            [("partner_id", "in", self.ids), ("company_id", "=", company.id)],
            ["partner_id"], ["signed_amount:sum", "__count", "date:max"],
        ) if self.ids else []
        values = {
            partner.id: (balance, count, last_date)
            for partner, balance, count, last_date in grouped
        }
        for partner in self:
            balance, count, last_date = values.get(partner.id, (0.0, 0, False))
            partner.current_account_balance = balance
            partner.customer_account_move_count = count
            partner.last_customer_account_move_date = last_date
            partner.available_credit = (
                partner.credit_limit - balance if partner.credit_limit > 0 else 0.0
            )
            partner.customer_account_over_limit = (
                partner.credit_limit > 0 and balance > partner.credit_limit
            )

    @api.model
    def _balance_partner_ids(self, operator, value):
        allowed = {"=", "!=", ">", ">=", "<", "<="}
        if operator not in allowed:
            return []
        self.env.cr.execute(
            f"""
                SELECT partner_id
                  FROM shop_customer_account_move
                 WHERE company_id = %s
                 GROUP BY partner_id
                HAVING COALESCE(SUM(signed_amount), 0) {operator} %s
            """,
            [self.env.company.id, value],
        )
        return [row[0] for row in self.env.cr.fetchall()]

    @api.model
    def _search_current_account_balance(self, operator, value):
        ids = self._balance_partner_ids(operator, value)
        if (operator == "=" and value == 0) or (operator in ("<=", ">=") and value == 0):
            nonzero = self._balance_partner_ids("!=", 0)
            zero_domain = [("id", "not in", nonzero)]
            if operator == "=":
                return zero_domain
            return ["|", ("id", "in", ids), *zero_domain]
        return [("id", "in", ids)]

    @api.model
    def _search_customer_account_over_limit(self, operator, value):
        if operator not in ("=", "!="):
            return [("id", "=", 0)]
        partners = self.search([("credit_limit", ">", 0)])
        over_ids = partners.filtered(
            lambda partner: partner.current_account_balance > partner.credit_limit
        ).ids
        wants_over = (operator == "=" and value) or (operator == "!=" and not value)
        return [("id", "in" if wants_over else "not in", over_ids)]

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + [
            "current_account_balance", "credit_limit", "available_credit",
            "customer_account_currency_id",
        ]

    def action_view_customer_account_moves(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "shop_customer_auth.action_customer_account_moves"
        )
        action["domain"] = [
            ("partner_id", "=", self.id), ("company_id", "=", self.env.company.id),
        ]
        action["context"] = {
            "default_partner_id": self.id, "default_company_id": self.env.company.id,
        }
        return action

    def action_register_customer_payment(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Registrar Cobranza"),
            "res_model": "shop.customer.account.payment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_partner_id": self.id},
        }

    def write(self, vals):
        if "credit_limit" in vals and not self.env.user.has_group(
            "shop_customer_auth.group_customer_account_manager"
        ):
            raise AccessError(_("Sólo un responsable puede modificar el límite de crédito."))
        return super().write(vals)
