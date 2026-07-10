from odoo import _, api, models, fields
from odoo.exceptions import AccessError, ValidationError


class ShopCustomerAuth(models.Model):
    _name = "shop.customer.auth"
    _description = "Shop Customer Auth"
    _rec_name = "email"

    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        required=True,
        ondelete="cascade",
    )

    email = fields.Char(
        string="Email",
        required=True,
        index=True,
    )

    password_hash = fields.Char(
        string="Password Hash",
        required=True,
    )

    active = fields.Boolean(
        default=True,
    )

    email_verified = fields.Boolean(
        default=False,
    )

    last_login = fields.Datetime()

    register_source = fields.Selection(
        [
            ("web", "Web"),
            ("google", "Google"),
            ("admin", "Admin"),
        ],
        default="web",
    )
    role = fields.Selection(
        [
            ("customer", "Cliente"),
            ("seller", "Vendedor"),
            ("admin", "Administrador"),
        ],
        string="Rol",
        default="customer",
        required=True,
        index=True,
    )

    _sql_constraints = [
        (
            "shop_customer_auth_email_unique",
            "unique(email)",
            "El email ya está registrado.",
        ),
    ]

    def name_get(self):
        result = []

        for record in self:
            name = f"{record.email}"

            if record.partner_id:
                name = f"{record.partner_id.name} ({record.email})"

            result.append((record.id, name))

        return result

    @api.model
    def _normalize_email(self, email):
        return (email or "").strip().lower()

    @api.model
    def _require_password_reset_api_group(self):
        if not self.env.user.has_group(
            "shop_customer_auth.group_shop_password_reset_api"
        ):
            raise AccessError(_("Password reset API access is required."))

    @api.model
    def _password_reset_response(self, status="accepted"):
        return {
            "ok": True,
            "status": status,
            "message": "If the account exists, the password reset was processed.",
        }

    @api.model
    def check_password_reset_customer(self, email):
        """Internal RPC helper for NestJS to confirm whether an account can reset."""
        self._require_password_reset_api_group()
        normalized_email = self._normalize_email(email)
        if not normalized_email:
            raise ValidationError(_("Email is required."))

        auth = self.search(
            [("email", "=ilike", normalized_email), ("active", "=", True)],
            limit=1,
        )
        if not auth:
            return {
                **self._password_reset_response(),
                "exists": False,
            }

        return {
            **self._password_reset_response(),
            "exists": True,
            "auth_id": auth.id,
            "partner_id": auth.partner_id.id,
            "email": auth.email,
        }

    @api.model
    def reset_password_by_email(self, email, new_password_hash):
        """Set the final password hash after NestJS has validated its reset token."""
        self._require_password_reset_api_group()
        normalized_email = self._normalize_email(email)
        if not normalized_email:
            raise ValidationError(_("Email is required."))
        if not new_password_hash:
            raise ValidationError(_("The new password hash is required."))

        self.env.cr.execute(
            """
                SELECT id
                  FROM shop_customer_auth
                 WHERE lower(email) = %s
                   AND active
                 FOR UPDATE
            """,
            [normalized_email],
        )
        row = self.env.cr.fetchone()
        if not row:
            return self._password_reset_response()

        auth = self.browse(row[0])
        auth.write({"password_hash": new_password_hash})
        self.env["shop.password.reset.audit"].create(
            {
                "user_id": self.env.uid,
                "auth_id": auth.id,
                "partner_id": auth.partner_id.id,
                "email": auth.email,
                "action": "password_reset",
            }
        )
        return self._password_reset_response()
