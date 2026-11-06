from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


PARAM_PREFIX = "sale_store_pickup.correo_argentino."
PASSWORD_PARAM = PARAM_PREFIX + "password"


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    correo_argentino_enabled = fields.Boolean(
        string="Activar Correo Argentino MiCorreo",
        config_parameter=PARAM_PREFIX + "enabled",
        default=False,
    )
    correo_argentino_username = fields.Char(
        string="Usuario MiCorreo",
        config_parameter=PARAM_PREFIX + "username",
    )
    correo_argentino_customer_id = fields.Char(
        string="ID de cliente MiCorreo",
        config_parameter=PARAM_PREFIX + "customer_id",
    )
    correo_argentino_origin_postal_code = fields.Char(
        string="Código postal de origen",
        config_parameter=PARAM_PREFIX + "origin_postal_code",
    )
    correo_argentino_sender_name = fields.Char(string="Nombre del remitente", config_parameter=PARAM_PREFIX + "sender_name")
    correo_argentino_sender_phone = fields.Char(string="Teléfono del remitente", config_parameter=PARAM_PREFIX + "sender_phone")
    correo_argentino_sender_cell_phone = fields.Char(string="Celular del remitente", config_parameter=PARAM_PREFIX + "sender_cell_phone")
    correo_argentino_sender_email = fields.Char(string="Email del remitente", config_parameter=PARAM_PREFIX + "sender_email")
    correo_argentino_sender_street = fields.Char(string="Calle del remitente", config_parameter=PARAM_PREFIX + "sender_street")
    correo_argentino_sender_street_number = fields.Char(string="Número del remitente", config_parameter=PARAM_PREFIX + "sender_street_number")
    correo_argentino_sender_floor = fields.Char(string="Piso del remitente", config_parameter=PARAM_PREFIX + "sender_floor")
    correo_argentino_sender_apartment = fields.Char(string="Departamento del remitente", config_parameter=PARAM_PREFIX + "sender_apartment")
    correo_argentino_sender_city = fields.Char(string="Localidad del remitente", config_parameter=PARAM_PREFIX + "sender_city")
    correo_argentino_sender_province_code = fields.Char(string="Código de provincia del remitente", config_parameter=PARAM_PREFIX + "sender_province_code", help="Código de provincia de MiCorreo, por ejemplo B para Buenos Aires o C para CABA.")
    correo_argentino_password_input = fields.Char(
        string="Contraseña MiCorreo",
        help="Dejá este campo vacío para conservar la contraseña guardada.",
    )
    correo_argentino_password_configured = fields.Boolean(
        string="Contraseña guardada",
        readonly=True,
    )
    correo_argentino_clear_password = fields.Boolean(
        string="Eliminar contraseña guardada",
    )

    @api.model
    def get_values(self):
        values = super().get_values()
        values["correo_argentino_password_configured"] = bool(
            self.env["ir.config_parameter"].sudo().get_param(PASSWORD_PARAM)
        )
        return values

    def set_values(self):
        self.ensure_one()
        params = self.env["ir.config_parameter"].sudo()
        saved_password = params.get_param(PASSWORD_PARAM) or ""
        new_password = self.correo_argentino_password_input or ""
        if self.correo_argentino_clear_password:
            password_after_save = ""
        elif new_password.strip():
            password_after_save = new_password
        else:
            password_after_save = saved_password
        if self.correo_argentino_enabled and not all(
            (
                (self.correo_argentino_username or "").strip(),
                password_after_save,
                (self.correo_argentino_customer_id or "").strip(),
                (self.correo_argentino_origin_postal_code or "").strip(),
            )
        ):
            raise ValidationError(
                _(
                    "Para activar Correo Argentino completá usuario, contraseña, "
                    "ID de cliente y código postal de origen."
                )
            )

        super().set_values()
        if self.correo_argentino_clear_password:
            params.set_param(PASSWORD_PARAM, "")
        elif new_password.strip():
            params.set_param(PASSWORD_PARAM, new_password)

    @api.model
    def get_correo_runtime_config(self):
        if not self.env.user.has_group(
            "sale_store_pickup.group_correo_integration"
        ):
            raise AccessError(
                _("No tenés permiso para consultar la configuración de MiCorreo.")
            )

        params = self.env["ir.config_parameter"].sudo()
        company_partner = self.env.company.partner_id.sudo()
        state_code = (company_partner.state_id.code or "").strip()
        if "-" in state_code:
            state_code = state_code.rsplit("-", 1)[-1]
        return {
            "enabled": params.get_param(PARAM_PREFIX + "enabled")
            in ("True", "true", "1"),
            "username": params.get_param(PARAM_PREFIX + "username") or "",
            "password": params.get_param(PASSWORD_PARAM) or "",
            "customerId": params.get_param(PARAM_PREFIX + "customer_id") or "",
            "originPostalCode": params.get_param(
                PARAM_PREFIX + "origin_postal_code"
            )
            or "",
            "sender": {
                "name": params.get_param(PARAM_PREFIX + "sender_name") or self.env.company.name or "",
                "phone": params.get_param(PARAM_PREFIX + "sender_phone") or company_partner.phone or "",
                "cellPhone": params.get_param(PARAM_PREFIX + "sender_cell_phone") or company_partner.mobile or "",
                "email": params.get_param(PARAM_PREFIX + "sender_email") or company_partner.email or "",
                "originAddress": {
                    "streetName": params.get_param(PARAM_PREFIX + "sender_street") or company_partner.street or "",
                    "streetNumber": params.get_param(PARAM_PREFIX + "sender_street_number") or "",
                    "floor": params.get_param(PARAM_PREFIX + "sender_floor") or "",
                    "apartment": params.get_param(PARAM_PREFIX + "sender_apartment") or "",
                    "city": params.get_param(PARAM_PREFIX + "sender_city") or company_partner.city or "",
                    "provinceCode": params.get_param(PARAM_PREFIX + "sender_province_code") or state_code,
                    "postalCode": params.get_param(PARAM_PREFIX + "origin_postal_code") or "",
                },
            },
        }
