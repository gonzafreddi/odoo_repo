from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_done(self, cancel_backorder=False):
        moves = super()._action_done(cancel_backorder=cancel_backorder)
        for move in moves:
            line = move.purchase_line_id
            if not line or not move.product_id or not (move.is_in or move.is_dropship):
                continue
            product = move.product_id.with_company(move.company_id)
            new_cost = line.product_uom_id._compute_price(
                line.price_unit, product.uom_id
            )
            new_cost = line.currency_id._convert(
                new_cost,
                move.company_id.currency_id,
                move.company_id,
                fields.Date.context_today(move),
            )
            if new_cost and new_cost != product.standard_price:
                product.standard_price = new_cost
        return moves
