import { patch } from "@web/core/utils/patch";
import { ProductCard } from "@point_of_sale/app/components/product_card/product_card";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";

const PRODUCT_VIEW_MODE_KEY = "shop_customer_auth.product_view_mode";
const PRODUCT_VIEW_MODES = new Set(["grid", "list"]);

patch(ProductCard, {
    props: {
        ...ProductCard.props,
        price: { type: String, optional: true },
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
