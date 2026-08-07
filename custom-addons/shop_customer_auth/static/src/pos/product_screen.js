import { patch } from "@web/core/utils/patch";
import { ProductCard } from "@point_of_sale/app/components/product_card/product_card";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { ProductTemplate } from "@point_of_sale/app/models/product_template";

const PRODUCT_VIEW_MODE_KEY = "shop_customer_auth.product_view_mode";
const PRODUCT_VIEW_MODES = new Set(["grid", "list"]);

patch(ProductCard, {
    props: {
        ...ProductCard.props,
        price: { type: String, optional: true },
        originalPrice: { type: String, optional: true },
        description: { type: [String, Boolean], optional: true },
    },
});

patch(ProductTemplate.prototype, {
    getPrice(pricelist, quantity, priceExtra = 0, recurring = false, variant = false) {
        const regularPrice = super.getPrice(pricelist, quantity, priceExtra, recurring, variant);
        if (!this.offer_active || !(this.offer_price > 0)) {
            return regularPrice;
        }
        return Math.min(regularPrice, this.offer_price + (priceExtra || 0));
    },

    getProductPrice(price = false, pricelist = false, fiscalPosition = false) {
        const regularPrice = super.getProductPrice(price, pricelist, fiscalPosition);
        if (!this.offer_active || !(this.offer_price > 0)) {
            return regularPrice;
        }
        const offerPrice = super.getProductPrice(this.offer_price, pricelist, fiscalPosition);
        return Math.min(regularPrice, offerPrice);
    },

    getOriginalProductPrice(price = false, pricelist = false, fiscalPosition = false) {
        const regularPrice = super.getPrice(pricelist, 1);
        return super.getProductPrice(regularPrice, pricelist, fiscalPosition);
    },
});

patch(ProductScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.productViewMode = this.getStoredProductViewMode();
    },

    getStoredProductViewMode() {
        try {
            const mode = window.localStorage.getItem(PRODUCT_VIEW_MODE_KEY);
            return PRODUCT_VIEW_MODES.has(mode) ? mode : "grid";
        } catch {
            return "grid";
        }
    },

    getProductOriginalPrice(product) {
        if (!product.offer_active || !(product.offer_price > 0)) {
            return undefined;
        }
        const order = this.pos.getOrder();
        const fiscalPosition = order.fiscal_position_id || this.pos.config.fiscal_position_id;
        const pricelist = order.pricelist_id || this.pos.config.pricelist_id;
        const originalPrice = product.getOriginalProductPrice(false, pricelist, fiscalPosition);
        const offerPrice = product.getProductPrice(false, pricelist, fiscalPosition);
        if (offerPrice >= originalPrice) {
            return undefined;
        }
        return this.env.utils.formatCurrency(originalPrice);
    },

    setProductViewMode(mode) {
        if (!PRODUCT_VIEW_MODES.has(mode)) {
            return;
        }
        this.state.productViewMode = mode;
        try {
            window.localStorage.setItem(PRODUCT_VIEW_MODE_KEY, mode);
        } catch {
            // The reactive state still changes when storage is unavailable.
        }
    },
});
