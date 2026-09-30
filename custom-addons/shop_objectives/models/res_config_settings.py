from odoo import api, fields, models

ENABLED_PARAM = "shop_objectives.enabled"


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    x_objectives_enabled = fields.Boolean(
        string="Mostrar sección Objetivos",
        help="Si está desactivado, la tienda online oculta la sección 'Elegí según tu objetivo' "
        "del home y las páginas de cada objetivo.",
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        # Sin parámetro = activo (instalaciones existentes siguen mostrando la sección).
        res["x_objectives_enabled"] = self.env["shop.product.objective"]._objectives_enabled()
        return res

    def set_values(self):
        super().set_values()
        # Se guarda "1"/"0" explícito: Odoo borra los parámetros booleanos en falso.
        self.env["ir.config_parameter"].sudo().set_param(
            ENABLED_PARAM, "1" if self.x_objectives_enabled else "0"
        )
