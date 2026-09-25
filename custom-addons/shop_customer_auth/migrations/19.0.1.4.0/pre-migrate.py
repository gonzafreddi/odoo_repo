"""Adopta como medio fijo un "Mercado Pago" creado antes a mano o por la API."""


def migrate(cr, version):
    cr.execute("""
        SELECT 1 FROM ir_model_data
         WHERE module = 'shop_customer_auth' AND name = 'payment_method_mercadopago'
    """)
    if cr.fetchone():
        return
    cr.execute("""
        SELECT res_id FROM ir_model_data
         WHERE module = 'base' AND name = 'main_company'
    """)
    row = cr.fetchone()
    if not row:
        return
    cr.execute("""
        SELECT method.id
          FROM shop_sale_payment_method method
         WHERE method.company_id = %s
           AND EXISTS (
               SELECT 1 FROM jsonb_each_text(method.name) AS translation
                WHERE translation.value ILIKE 'mercado pago'
           )
         ORDER BY method.active DESC, method.id
         LIMIT 1
    """, (row[0],))
    method = cr.fetchone()
    if not method:
        return
    cr.execute("""
        UPDATE shop_sale_payment_method
           SET active = TRUE, reference_required = TRUE
         WHERE id = %s
    """, (method[0],))
    cr.execute("""
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
        VALUES ('shop_customer_auth', 'payment_method_mercadopago',
                'shop.sale.payment.method', %s, TRUE)
    """, (method[0],))
