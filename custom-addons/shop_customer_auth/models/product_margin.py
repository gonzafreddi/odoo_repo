from odoo import _, api, models
from odoo.exceptions import AccessError


class ShopProductMargin(models.AbstractModel):
    _name = "shop.product.margin"
    _description = "Márgenes de productos"

    _ALLOWED_GROUPS = (
        "sales_team.group_sale_manager",
        "purchase.group_purchase_manager",
        "account.group_account_manager",
        "base.group_system",
    )

    @api.model
    def _check_margin_access(self):
        if not any(self.env.user.has_group(group) for group in self._ALLOWED_GROUPS):
            raise AccessError(_("No tenés acceso a los márgenes de productos."))

    @api.model
    def get_margin_data(self):
        self._check_margin_access()
        company = self.env.company
        products = self.env["product.template"].with_company(company).search([
            ("sale_ok", "=", True),
            ("active", "=", True),
            ("company_id", "in", [company.id, False]),
        ])
        # Batch-read variant costs before processing rows to avoid a query per template.
        products.product_variant_ids.with_company(company).mapped("standard_price")
        rows = []
        margins = []
        negative_count = no_cost_count = 0
        for product in products:
            cost = product._shop_margin_cost()
            list_price = product.list_price
            offer_active = bool(product.offer_active)
            price = product._shop_margin_price()
            profit = price - cost
            margin = profit / price if price else None
            has_cost = cost > 0
            no_cost_count += not has_cost
            negative_count += profit < 0
            if price > 0 and has_cost:
                margins.append(margin)
            rows.append({
                "id": product.id,
                "name": product.display_name,
                "default_code": product.default_code or "",
                "category": product.categ_id.display_name or "",
                "is_combo": product.type == "combo",
                "variant_count": len(product.product_variant_ids.filtered("active")),
                "image_url": f"/web/image/product.template/{product.id}/image_128",
                "cost": cost,
                "has_cost": has_cost,
                "list_price": list_price,
                "price": price,
                "offer_active": offer_active,
                "profit": profit,
                "margin": margin,
            })
        currency = company.currency_id
        return {
            "currency": {
                "symbol": currency.symbol,
                "position": currency.position,
                "decimals": currency.decimal_places,
            },
            "company_name": company.display_name,
            "rows": rows,
            "summary": {
                "count": len(rows),
                "avg_margin": sum(margins) / len(margins) if margins else None,
                "negative_count": negative_count,
                "no_cost_count": no_cost_count,
            },
        }
