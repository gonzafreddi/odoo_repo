from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare


class ShopQuickStockAdjustment(models.AbstractModel):
    _name = "shop.quick.stock.adjustment"
    _description = "Quick Stock Adjustment"

    @api.model
    def _check_access(self):
        if not self.env.user.has_group("stock.group_stock_manager"):
            raise AccessError(_("Only inventory managers can adjust stock."))

    @api.model
    def _get_location(self, location_id):
        location = self.env["stock.location"].browse(int(location_id or 0)).exists()
        if (
            not location
            or location.usage != "internal"
            or (location.company_id and location.company_id != self.env.company)
        ):
            raise ValidationError(_("Select a valid internal location."))
        return location

    @api.model
    def get_setup_data(self):
        self._check_access()
        company = self.env.company
        locations = self.env["stock.location"].search([
            ("usage", "=", "internal"),
            ("company_id", "in", (False, company.id)),
        ], order="complete_name")
        default_location = self.env["stock.warehouse"].search(
            [("company_id", "=", company.id)], limit=1
        ).lot_stock_id
        return {
            "company_name": company.display_name,
            "default_location_id": default_location.id,
            "locations": [
                {"id": location.id, "name": location.complete_name}
                for location in locations
            ],
        }

    @api.model
    def search_products(self, query, location_id, limit=12):
        self._check_access()
        location = self._get_location(location_id)
        query = (query or "").strip()
        if not query:
            return []
        products = self.env["product.product"].search([
            ("active", "=", True),
            ("is_storable", "=", True),
            "|", "|",
            ("barcode", "ilike", query),
            ("default_code", "ilike", query),
            ("name", "ilike", query),
        ], limit=min(max(int(limit or 12), 1), 20))
        exact = products.filtered(
            lambda product: query in (product.barcode, product.default_code)
        )
        products = exact + (products - exact)
        return [
            self._serialize_product(product, location)
            for product in products
        ]

    @api.model
    def get_product(self, product_id, location_id):
        self._check_access()
        location = self._get_location(location_id)
        product = self.env["product.product"].browse(int(product_id or 0)).exists()
        if not product or not product.active or not product.is_storable:
            raise ValidationError(_("Select a valid storable product."))
        return self._serialize_product(product, location)

    @api.model
    def _serialize_product(self, product, location):
        quants = self.env["stock.quant"].search([
            ("product_id", "=", product.id),
            ("location_id", "=", location.id),
        ])
        quantity = sum(quants.mapped("quantity"))
        complex_quants = quants.filtered(
            lambda quant: quant.lot_id or quant.package_id or quant.owner_id
        )
        quick_adjustable = product.tracking == "none" and not complex_quants
        if product.tracking != "none":
            blocker = _(
                "This product requires a lot or serial number. Use the standard inventory count."
            )
        elif complex_quants:
            blocker = _(
                "This stock is separated by package or owner. Use the standard inventory count."
            )
        else:
            blocker = ""
        return {
            "id": product.id,
            "name": product.display_name,
            "barcode": product.barcode or "",
            "default_code": product.default_code or "",
            "tracking": product.tracking,
            "tracking_label": dict(product._fields["tracking"]._description_selection(self.env)).get(
                product.tracking, product.tracking
            ),
            "quick_adjustable": quick_adjustable,
            "blocker": blocker,
            "quantity": quantity,
            "uom_name": product.uom_id.display_name,
            "image_url": f"/web/image/product.product/{product.id}/image_128",
        }

    @api.model
    def apply_adjustment(
        self, product_id, location_id, counted_quantity, expected_quantity
    ):
        self._check_access()
        location = self._get_location(location_id)
        product = self.env["product.product"].browse(int(product_id or 0)).exists()
        if not product or not product.active or not product.is_storable:
            raise ValidationError(_("Select a valid storable product."))
        if product.tracking != "none":
            raise UserError(_(
                "This quick adjustment does not support products tracked by lot "
                "or serial number yet. Use the standard inventory count for this product."
            ))
        complex_quants = self.env["stock.quant"].search_count([
            ("product_id", "=", product.id),
            ("location_id", "=", location.id),
            "|", "|",
            ("lot_id", "!=", False),
            ("package_id", "!=", False),
            ("owner_id", "!=", False),
        ])
        if complex_quants:
            raise UserError(_(
                "This stock is separated by package or owner. Use the standard inventory count."
            ))
        try:
            counted_quantity = float(counted_quantity)
            expected_quantity = float(expected_quantity)
        except (TypeError, ValueError):
            raise ValidationError(_("Enter a valid counted quantity.")) from None
        if float_compare(
            counted_quantity, 0, precision_rounding=product.uom_id.rounding
        ) < 0:
            raise ValidationError(_("The counted quantity cannot be negative."))

        Quant = self.env["stock.quant"].with_context(inventory_mode=True)
        quant = Quant.search([
            ("product_id", "=", product.id),
            ("location_id", "=", location.id),
            ("lot_id", "=", False),
            ("package_id", "=", False),
            ("owner_id", "=", False),
        ], limit=1)
        current_quantity = quant.quantity if quant else 0.0
        if float_compare(
            current_quantity,
            expected_quantity,
            precision_rounding=product.uom_id.rounding,
        ):
            raise UserError(_(
                "The stock changed after you opened the product. Refresh it before applying the count."
            ))
        if quant and quant.inventory_quantity_set:
            raise UserError(_(
                "This product already has a pending inventory count in this location."
            ))

        if quant:
            quant.inventory_quantity = counted_quantity
        else:
            quant = Quant.create({
                "product_id": product.id,
                "location_id": location.id,
                "inventory_quantity": counted_quantity,
            })
        result = quant.action_apply_inventory()
        if result:
            quant.action_clear_inventory_quantity()
            raise UserError(_(
                "Odoo detected an inventory conflict. Refresh the product and try again."
            ))
        difference = counted_quantity - current_quantity
        return {
            "product_id": product.id,
            "product_name": product.display_name,
            "location_name": location.complete_name,
            "previous_quantity": current_quantity,
            "counted_quantity": counted_quantity,
            "difference": difference,
            "uom_name": product.uom_id.display_name,
            "applied_at": fields.Datetime.to_string(fields.Datetime.now()),
        }
