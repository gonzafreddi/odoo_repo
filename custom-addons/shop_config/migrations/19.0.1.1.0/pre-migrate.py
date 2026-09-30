"""Los parámetros pasan a sembrarse una sola vez (noupdate) y a no pisar lo cargado en Ajustes.

Antes los registros eran noupdate="0": cada -u reseteaba umbral, recargo y pausa de MP a
su valor semilla. Además, un parámetro ya guardado desde Ajustes que todavía no tenía su
xmlid (recargo de tarjeta, pausa de MP) hacía fallar la actualización con clave duplicada.
Acá se adopta cada parámetro existente con su xmlid y se marca noupdate.
"""

PARAMS = {
    "param_free_shipping_threshold": "shop_config.free_shipping_threshold",
    "param_default_shipping_cost": "shop_config.default_shipping_cost",
    "param_free_shipping_enabled": "shop_config.free_shipping_enabled",
    "param_mercadopago_paused": "shop_config.mercadopago_paused",
    "param_card_surcharge_percent": "shop_config.card_surcharge_percent",
}


def migrate(cr, version):
    for xmlid, key in PARAMS.items():
        cr.execute("SELECT id FROM ir_config_parameter WHERE key = %s", (key,))
        row = cr.fetchone()
        if not row:
            continue
        cr.execute(
            "SELECT id FROM ir_model_data WHERE module = 'shop_config' AND name = %s",
            (xmlid,),
        )
        if cr.fetchone():
            cr.execute(
                "UPDATE ir_model_data SET noupdate = TRUE"
                " WHERE module = 'shop_config' AND name = %s",
                (xmlid,),
            )
        else:
            cr.execute(
                "INSERT INTO ir_model_data (module, name, model, res_id, noupdate)"
                " VALUES ('shop_config', %s, 'ir.config_parameter', %s, TRUE)",
                (xmlid, row[0]),
            )
