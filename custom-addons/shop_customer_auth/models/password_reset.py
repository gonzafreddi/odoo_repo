from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError


def _check_password_reset_api_group(env):
    if not env.user.has_group("shop_customer_auth.group_shop_password_reset_api"):
        raise AccessError("Password reset API access is required.")


class PasswordResetToken(models.Model):
    _name = "password.reset.token"
    _description = "Password Reset Token"
    _table = "password_reset_tokens"
    _order = "created_at desc"

    user_id = fields.Many2one(
        "shop.customer.auth",
        string="Customer Auth",
        index=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        index=True,
        ondelete="cascade",
    )
    email = fields.Char(required=True, index=True)
    token_hash = fields.Char(required=True, index=True)
    expires_at = fields.Datetime(required=True, index=True)
    used_at = fields.Datetime(index=True)
    created_at = fields.Datetime(
        string="Created At",
        default=fields.Datetime.now,
        required=True,
        index=True,
    )
    ip = fields.Char()
    user_agent = fields.Char()

    _sql_constraints = [
        (
            "password_reset_token_hash_unique",
            "unique(token_hash)",
            "Password reset token hash must be unique.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        _check_password_reset_api_group(self.env)
        now = fields.Datetime.now()
        normalized_vals_list = []

        for vals in vals_list:
            values = dict(vals)
            if values.get("email"):
                values["email"] = values["email"].strip().lower()
            normalized_vals_list.append(values)

        records = super().create(normalized_vals_list)

        for record in records:
            domain = [("id", "!=", record.id), ("used_at", "=", False)]
            if record.user_id:
                domain += [
                    "|",
                    ("email", "=", record.email),
                    ("user_id", "=", record.user_id.id),
                ]
            else:
                domain.append(("email", "=", record.email))
            self.search(domain).write({"used_at": now})

        return records

    def consume(self, values):
        _check_password_reset_api_group(self.env)
        self.ensure_one()
        auth_id = values.get("auth_id")
        email = (values.get("email") or "").strip().lower()
        password_hash = values.get("password_hash")

        if not auth_id or not email or not password_hash:
            raise UserError("Invalid password reset payload.")

        with self.env.cr.savepoint():
            self.env.cr.execute(
                "SELECT id FROM password_reset_tokens WHERE id = %s FOR UPDATE",
                [self.id],
            )
            self.invalidate_recordset(["used_at"])

            now = fields.Datetime.now()
            if self.used_at or self.expires_at <= now:
                raise UserError("Invalid password reset token.")

            auth = self.env["shop.customer.auth"].browse(auth_id).exists()
            if not auth or auth.email.strip().lower() != email or auth != self.user_id:
                raise UserError("Invalid password reset token.")

            auth.write({"password_hash": password_hash})
            self.write({"used_at": now})

            others = self.search(
                [
                    ("id", "!=", self.id),
                    ("used_at", "=", False),
                    "|",
                    ("email", "=", email),
                    ("user_id", "=", auth.id),
                ]
            )
            others.write({"used_at": now})

            self.env["shop.password.reset.audit"].create(
                {
                    "user_id": self.env.uid,
                    "auth_id": auth.id,
                    "partner_id": auth.partner_id.id,
                    "email": auth.email,
                    "action": "password_reset",
                }
            )

        return True

    @api.model
    def _cron_cleanup_password_resets(self):
        now = fields.Datetime.now()
        self.sudo().search(
            [
                "|",
                ("expires_at", "<", now),
                ("used_at", "!=", False),
            ]
        ).unlink()


class ShopPasswordResetAudit(models.Model):
    _name = "shop.password.reset.audit"
    _description = "Shop Password Reset Audit"
    _order = "create_date desc"

    user_id = fields.Many2one(
        "res.users",
        string="Internal RPC User",
        required=True,
        readonly=True,
        ondelete="restrict",
        index=True,
    )
    auth_id = fields.Many2one(
        "shop.customer.auth",
        string="Shop Auth Account",
        required=True,
        readonly=True,
        ondelete="cascade",
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        readonly=True,
        ondelete="cascade",
        index=True,
    )
    email = fields.Char(required=True, readonly=True, index=True)
    action = fields.Selection(
        [("password_reset", "Password Reset")],
        required=True,
        readonly=True,
        default="password_reset",
        index=True,
    )
