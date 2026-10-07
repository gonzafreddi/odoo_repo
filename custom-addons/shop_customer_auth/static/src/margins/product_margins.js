/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";

const normalize = (value) => (value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("es-AR");

export class ProductMargins extends Component {
    static template = "shop_customer_auth.ProductMargins";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ loading: true, error: null, data: null, search: "", category: "", kind: "all", alert: "", sort: "margin", direction: "asc" });
        this.searchTimer = null;
        onWillStart(() => this.load());
        onWillUnmount(() => clearTimeout(this.searchTimer));
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            this.state.data = await this.orm.call("shop.product.margin", "get_margin_data", []);
        } catch (error) {
            this.state.error = error.data?.message || error.message || "No se pudieron cargar los márgenes.";
        } finally {
            this.state.loading = false;
        }
    }

    onSearch(event) {
        clearTimeout(this.searchTimer);
        const value = event.target.value;
        this.searchTimer = setTimeout(() => { this.state.search = value; }, 180);
    }

    get categories() {
        return [...new Set((this.state.data?.rows || []).map((row) => row.category).filter(Boolean))].sort((a, b) => a.localeCompare(b, "es-AR"));
    }

    get rows() {
        let rows = [...(this.state.data?.rows || [])];
        const query = normalize(this.state.search);
        if (query) rows = rows.filter((row) => normalize(`${row.name} ${row.default_code}`).includes(query));
        if (this.state.category) rows = rows.filter((row) => row.category === this.state.category);
        if (this.state.kind === "products") rows = rows.filter((row) => !row.is_combo);
        if (this.state.kind === "combos") rows = rows.filter((row) => row.is_combo);
        if (this.state.alert === "negative") rows = rows.filter((row) => row.profit < 0);
        if (this.state.alert === "no_cost") rows = rows.filter((row) => !row.has_cost);
        const { sort, direction } = this.state;
        const factor = direction === "asc" ? 1 : -1;
        return rows.sort((a, b) => {
            if ((sort === "margin" || sort === "profit") && a.has_cost !== b.has_cost) return a.has_cost ? -1 : 1;
            let left = a[sort], right = b[sort];
            if (left == null || right == null) return left == null ? (right == null ? 0 : 1) : -1;
            if (typeof left === "string") return left.localeCompare(right, "es-AR") * factor;
            return (left - right) * factor;
        });
    }

    sortBy(key) {
        if (this.state.sort === key) this.state.direction = this.state.direction === "asc" ? "desc" : "asc";
        else { this.state.sort = key; this.state.direction = "asc"; }
    }

    ariaSort(key) {
        return this.state.sort !== key ? "none" : this.state.direction === "asc" ? "ascending" : "descending";
    }

    indicator(key) { return this.state.sort === key ? (this.state.direction === "asc" ? "↑" : "↓") : "↕"; }
    formatMoney(value) {
        const currency = this.state.data?.currency || { symbol: "$", position: "before", decimals: 2 };
        const number = new Intl.NumberFormat("es-AR", { minimumFractionDigits: 0, maximumFractionDigits: currency.decimals }).format(value || 0);
        return currency.position === "after" ? `${number} ${currency.symbol}` : `${currency.symbol}${number}`;
    }
    formatPercent(value) { return `${new Intl.NumberFormat("es-AR", { maximumFractionDigits: 1 }).format(value * 100)}%`; }
    marginClass(value) { return value < 0 ? "negative" : value < .2 ? "amber" : value < .4 ? "light" : "teal"; }
    marginWidth(value) { return `${Math.min(100, Math.max(0, value * 100))}%`; }
    toggleAlert(alert) { this.state.alert = this.state.alert === alert ? "" : alert; }
    openProduct(id) { return this.action.doAction({ type: "ir.actions.act_window", res_model: "product.template", res_id: id, views: [[false, "form"]], target: "current" }); }
}

registry.category("actions").add("shop_customer_auth.product_margins", ProductMargins);
