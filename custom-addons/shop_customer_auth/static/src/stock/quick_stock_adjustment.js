/** @odoo-module **/

import { registry } from "@web/core/registry";
import { scanBarcode } from "@web/core/barcode/barcode_dialog";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillStart, useRef, useState } from "@odoo/owl";

export class QuickStockAdjustment extends Component {
    static template = "shop_customer_auth.QuickStockAdjustment";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.searchInput = useRef("searchInput");
        this.searchTimer = null;
        this.state = useState({
            loading: true,
            saving: false,
            error: null,
            companyName: "",
            locations: [],
            locationId: null,
            query: "",
            searching: false,
            results: [],
            product: null,
            countedQuantity: "",
            history: [],
        });
        onWillStart(() => this.loadSetup());
        onMounted(() => this.focusSearch());
    }

    async loadSetup() {
        try {
            const data = await this.orm.call(
                "shop.quick.stock.adjustment",
                "get_setup_data",
                []
            );
            this.state.companyName = data.company_name;
            this.state.locations = data.locations;
            this.state.locationId = data.default_location_id || data.locations[0]?.id || null;
            if (!this.state.locationId) {
                this.state.error = "No hay ubicaciones internas disponibles.";
            }
        } catch (error) {
            this.state.error = this.errorMessage(error);
        } finally {
            this.state.loading = false;
        }
    }

    errorMessage(error) {
        return error.data?.message || error.message || "No se pudo completar la operación.";
    }

    focusSearch() {
        requestAnimationFrame(() => this.searchInput.el?.focus());
    }

    onQueryInput(event) {
        this.state.query = event.target.value;
        clearTimeout(this.searchTimer);
        if (!this.state.query.trim()) {
            this.state.results = [];
            return;
        }
        this.searchTimer = setTimeout(() => this.searchProducts(), 260);
    }

    async searchProducts({ selectExact = false } = {}) {
        const query = this.state.query.trim();
        if (!query || !this.state.locationId) {
            return;
        }
        this.state.searching = true;
        this.state.error = null;
        try {
            const results = await this.orm.call(
                "shop.quick.stock.adjustment",
                "search_products",
                [],
                { query, location_id: this.state.locationId, limit: 12 }
            );
            this.state.results = results;
            const exact = results.find(
                (product) => product.barcode === query || product.default_code === query
            );
            if (exact || (selectExact && results.length === 1)) {
                this.selectProduct(exact || results[0]);
                this.vibrate(80);
            } else if (selectExact && !results.length) {
                this.notification.add("No se encontró un producto con ese código.", {
                    type: "warning",
                });
                this.vibrate([60, 50, 60]);
            }
        } catch (error) {
            this.state.error = this.errorMessage(error);
        } finally {
            this.state.searching = false;
        }
    }

    onSearchKeydown(event) {
        if (event.key === "Enter") {
            event.preventDefault();
            clearTimeout(this.searchTimer);
            this.searchProducts({ selectExact: true });
        }
    }

    async scanWithCamera() {
        try {
            const barcode = await scanBarcode(this.env, "environment");
            if (barcode) {
                this.state.query = barcode;
                await this.searchProducts({ selectExact: true });
            }
        } catch (error) {
            this.notification.add(this.errorMessage(error), { type: "warning" });
        }
    }

    selectProduct(product) {
        this.state.product = product;
        this.state.countedQuantity = String(product.quantity);
        this.state.query = "";
        this.state.results = [];
    }

    async onLocationChange(event) {
        this.state.locationId = Number(event.target.value);
        this.state.results = [];
        if (this.state.product) {
            try {
                this.state.product = await this.orm.call(
                    "shop.quick.stock.adjustment",
                    "get_product",
                    [],
                    {
                        product_id: this.state.product.id,
                        location_id: this.state.locationId,
                    }
                );
                this.state.countedQuantity = String(this.state.product.quantity);
            } catch (error) {
                this.state.error = this.errorMessage(error);
            }
        }
    }

    changeQuantity(step) {
        const current = Number(this.state.countedQuantity || 0);
        this.state.countedQuantity = String(Math.max(0, current + step));
    }

    get countedNumber() {
        const value = Number(this.state.countedQuantity);
        return Number.isFinite(value) ? value : 0;
    }

    get difference() {
        return this.countedNumber - (this.state.product?.quantity || 0);
    }

    differenceClass(value = this.difference) {
        if (value > 0) {
            return "is-positive";
        }
        if (value < 0) {
            return "is-negative";
        }
        return "is-neutral";
    }

    formatQuantity(value) {
        return new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 }).format(value || 0);
    }

    async applyAdjustment() {
        if (!this.state.product || this.state.countedQuantity === "") {
            return;
        }
        this.state.saving = true;
        this.state.error = null;
        try {
            const result = await this.orm.call(
                "shop.quick.stock.adjustment",
                "apply_adjustment",
                [],
                {
                    product_id: this.state.product.id,
                    location_id: this.state.locationId,
                    counted_quantity: this.countedNumber,
                    expected_quantity: this.state.product.quantity,
                }
            );
            this.state.history.unshift(result);
            this.state.history = this.state.history.slice(0, 8);
            this.notification.add("Stock actualizado correctamente.", { type: "success" });
            this.vibrate(120);
            this.clearProduct();
        } catch (error) {
            this.state.error = this.errorMessage(error);
            this.vibrate([80, 50, 80]);
        } finally {
            this.state.saving = false;
        }
    }

    clearProduct() {
        this.state.product = null;
        this.state.countedQuantity = "";
        this.state.query = "";
        this.state.results = [];
        this.focusSearch();
    }

    vibrate(pattern) {
        if ("vibrate" in navigator) {
            navigator.vibrate(pattern);
        }
    }
}

registry.category("actions").add(
    "shop_customer_auth.quick_stock_adjustment",
    QuickStockAdjustment
);
