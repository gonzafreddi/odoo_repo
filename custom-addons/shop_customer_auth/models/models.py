from odoo import models, fields
from odoo.exceptions import ValidationError

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