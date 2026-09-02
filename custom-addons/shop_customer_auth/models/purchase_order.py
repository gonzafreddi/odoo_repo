from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def button_confirm(self):
        result = super().button_confirm()
        for order in self:
            for line in order.order_line:
                if not line.product_id or line.display_type:
                    continue
                product = line.product_id.with_company(order.company_id)
                new_cost = line.product_uom_id._compute_price(
                    line.price_unit, product.uom_id
                )
                new_cost = line.currency_id._convert(
                    new_cost,
                    order.company_id.currency_id,
                    order.company_id,
                    fields.Date.context_today(order),
                )
                if new_cost and new_cost != product.standard_price:
                    product.standard_price = new_cost
        return result
