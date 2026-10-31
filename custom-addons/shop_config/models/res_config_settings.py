import re
from datetime import datetime, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    x_free_shipping_enabled = fields.Boolean(
        string="Envío gratis activo",
        config_parameter="shop_config.free_shipping_enabled",
        default=True,
        help="Si está desactivado, la tienda online no muestra mensajes de envío gratis.",
    )
    x_free_shipping_threshold = fields.Float(
        string="Umbral de envío gratis",
        config_parameter="shop_config.free_shipping_threshold",
        default=130000.0,
        help="Subtotal a partir del cual el envío es gratis en la tienda online.",
    )
    x_default_shipping_cost = fields.Float(
        string="Costo de envío por defecto",
        config_parameter="shop_config.default_shipping_cost",
        default=3500.0,
        help="Costo de envío que muestra la tienda online cuando el subtotal no alcanza el umbral.",
    )
    x_mercadopago_paused = fields.Boolean(
        string="Pausar Mercado Pago en la tienda online",
        config_parameter="shop_config.mercadopago_paused",
        help="Si está tildado, la tienda online deja de ofrecer el pago con Mercado Pago "
             "y los pedidos se coordinan por WhatsApp. Los pagos ya hechos se siguen "
             "registrando.",
    )
    x_card_surcharge_percent = fields.Float(
        string="Recargo tarjeta / Mercado Pago (%)",
        config_parameter="shop_config.card_surcharge_percent",
        default=0.0,
        help="Recargo sobre el precio de lista (o de oferta) para pagos con tarjeta "
             "o Mercado Pago. Efectivo y transferencia pagan el precio de lista. "
             "Se aplica en la tienda online y en el POS.",
    )
    x_interest_free_installments = fields.Integer(
        string="Cuotas sin interés (tienda online)",
        config_parameter="shop_config.interest_free_installments",
        default=0,
        help="Cantidad de cuotas sin interés que muestra la tienda online. "
             "Ingresá 0 para ocultar el mensaje.",
    )
    x_cyber_campaign_enabled = fields.Boolean(
        string="Activar Cyber Suplex",
        config_parameter="shop_config.cyber_campaign_enabled",
        default=False,
    )
    x_cyber_campaign_start_local = fields.Char(
        string="Inicio (Argentina, UTC−03:00)",
        default="2026-11-02 00:00",
        help="Formato YYYY-MM-DD HH:MM en horario de Buenos Aires.",
    )
    x_cyber_campaign_end_exclusive_local = fields.Char(
        string="Fin exclusivo (Argentina, UTC−03:00)",
        default="2026-11-05 00:00",
        help="Instante en que termina la campaña; el último minuto activo es el anterior. Formato YYYY-MM-DD HH:MM.",
    )
    x_cyber_campaign_destination_url = fields.Char(
        string="Destino de Ver ofertas",
        config_parameter="shop_config.cyber_campaign_destination_url",
        default="/productos",
        help="Ruta del sitio que comienza con / o URL completa HTTP/HTTPS.",
    )
    x_cyber_campaign_id = fields.Char(
        string="Identificador de campaña",
        config_parameter="shop_config.cyber_campaign_id",
        default="cyber-suplex-2026",
        help="Usá un identificador único en cada edición para gestionar el cierre del widget.",
    )

    _CYBER_TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")
    _CYBER_START_KEY = "shop_config.cyber_campaign_start_utc"
    _CYBER_END_KEY = "shop_config.cyber_campaign_end_exclusive_utc"

    @api.constrains("x_interest_free_installments")
    def _check_interest_free_installments(self):
        for settings in self:
            if settings.x_interest_free_installments < 0:
                raise ValidationError(
                    _("La cantidad de cuotas sin interés no puede ser negativa.")
                )

    @api.constrains("x_card_surcharge_percent")
    def _check_card_surcharge_percent(self):
        for settings in self:
            if not 0 <= settings.x_card_surcharge_percent <= 100:
                raise ValidationError(
                    _("El recargo de tarjeta debe estar entre 0 y 100 %.")
                )

    @api.model
    def get_values(self):
        values = super().get_values()
        params = self.env["ir.config_parameter"].sudo()
        values.update(
            x_cyber_campaign_start_local=self._cyber_utc_to_local(
                params.get_param(self._CYBER_START_KEY, "2026-11-02T03:00:00Z")
            ),
            x_cyber_campaign_end_exclusive_local=self._cyber_utc_to_local(
                params.get_param(self._CYBER_END_KEY, "2026-11-05T03:00:00Z")
            ),
        )
        return values

    def set_values(self):
        for settings in self:
            start_utc = self._cyber_local_to_utc(
                settings.x_cyber_campaign_start_local, _("el inicio")
            )
            end_utc = self._cyber_local_to_utc(
                settings.x_cyber_campaign_end_exclusive_local,
                _("el fin exclusivo"),
            )
            if end_utc <= start_utc:
                raise ValidationError(
                    _("El fin exclusivo debe ser posterior al inicio de la campaña.")
                )
            self._validate_cyber_destination(settings.x_cyber_campaign_destination_url)
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", settings.x_cyber_campaign_id or ""):
                raise ValidationError(
                    _("El identificador de campaña solo puede usar letras, números, guiones y guiones bajos.")
                )

        super().set_values()
        params = self.env["ir.config_parameter"].sudo()
        for settings in self:
            params.set_param(
                self._CYBER_START_KEY,
                self._cyber_local_to_utc(settings.x_cyber_campaign_start_local, _("el inicio")),
            )
            params.set_param(
                self._CYBER_END_KEY,
                self._cyber_local_to_utc(
                    settings.x_cyber_campaign_end_exclusive_local,
                    _("el fin exclusivo"),
                ),
            )

    @api.model
    def _cyber_local_to_utc(self, value, label):
        try:
            local = datetime.strptime(value or "", "%Y-%m-%d %H:%M").replace(
                tzinfo=self._CYBER_TIMEZONE
            )
        except ValueError as error:
            raise ValidationError(
                _("Ingresá %(label)s con el formato YYYY-MM-DD HH:MM en horario argentino.", label=label)
            ) from error
        return local.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        )

    @api.model
    def _cyber_utc_to_local(self, value):
        try:
            utc_value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if utc_value.tzinfo is None:
                utc_value = utc_value.replace(tzinfo=timezone.utc)
            return utc_value.astimezone(self._CYBER_TIMEZONE).strftime("%Y-%m-%d %H:%M")
        except (AttributeError, ValueError):
            return ""

    @api.model
    def _validate_cyber_destination(self, value):
        value = (value or "").strip()
        parsed = urlsplit(value)
        is_local_path = value.startswith("/") and not value.startswith("//")
        is_web_url = parsed.scheme in ("http", "https") and bool(parsed.netloc)
        if not (is_local_path or is_web_url):
            raise ValidationError(
                _("El destino de las ofertas debe ser una ruta local o una URL HTTP/HTTPS.")
            )
