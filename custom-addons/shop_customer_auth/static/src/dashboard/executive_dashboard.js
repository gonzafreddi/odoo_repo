/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

function localISO(date) {
    const offset = date.getTimezoneOffset() * 60000;
    return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}

export class ExecutiveDashboard extends Component {
    static template = "shop_customer_auth.ExecutiveDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        const today = new Date();
        this.state = useState({
            dateFrom: localISO(new Date(today.getFullYear(), today.getMonth(), 1)),
            dateTo: localISO(today),
            preset: "month",
            loading: true,
            error: null,
            data: null,
            view: "overview",
            dailyLoading: false,
            dailyError: null,
            dailyData: null,
        });
        onWillStart(() => this.load());
    }

    async load() {
        if (!this.state.dateFrom || !this.state.dateTo || this.state.dateFrom > this.state.dateTo) {
            this.state.error = "La fecha desde debe ser anterior o igual a la fecha hasta.";
            return;
        }
        this.state.loading = true;
        this.state.error = null;
        try {
            this.state.data = await this.orm.call(
                "shop.executive.dashboard",
                "get_dashboard_data",
                [],
                { date_from: this.state.dateFrom, date_to: this.state.dateTo }
            );
        } catch (error) {
            this.state.error = error.data?.message || error.message || "No se pudo cargar el tablero.";
        } finally {
            this.state.loading = false;
        }
    }

    applyPreset(preset) {
        const today = new Date();
        let start;
        if (preset === "month") {
            start = new Date(today.getFullYear(), today.getMonth(), 1);
        } else if (preset === "quarter") {
            start = new Date(today.getFullYear(), Math.floor(today.getMonth() / 3) * 3, 1);
        } else {
            start = new Date(today.getFullYear(), 0, 1);
        }
        this.state.preset = preset;
        this.state.dateFrom = localISO(start);
        this.state.dateTo = localISO(today);
        return this.refresh();
    }

    onDateFrom(event) {
        this.state.dateFrom = event.target.value;
        this.state.preset = "manual";
    }

    onDateTo(event) {
        this.state.dateTo = event.target.value;
        this.state.preset = "manual";
    }

    refresh() {
        return this.state.view === "daily" ? this.loadDaily(1) : this.load();
    }

    async setView(view) {
        this.state.view = view;
        if (view === "daily") {
            await this.loadDaily(1);
        }
    }

    async loadDaily(page = 1) {
        if (!this.state.dateFrom || !this.state.dateTo || this.state.dateFrom > this.state.dateTo) {
            this.state.dailyError = "La fecha desde debe ser anterior o igual a la fecha hasta.";
            return;
        }
        this.state.dailyLoading = true;
        this.state.dailyError = null;
        try {
            this.state.dailyData = await this.orm.call(
                "shop.executive.dashboard",
                "get_daily_sales_summary",
                [],
                {
                    date_from: this.state.dateFrom,
                    date_to: this.state.dateTo,
                    page,
                    page_size: 15,
                }
            );
        } catch (error) {
            this.state.dailyError = error.data?.message || error.message || "No se pudo cargar el resumen diario.";
        } finally {
            this.state.dailyLoading = false;
        }
    }

    formatDate(value) {
        return new Intl.DateTimeFormat(undefined, {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
        }).format(new Date(`${value}T00:00:00`));
    }

    formatMoney(value) {
        if (!this.state.data) {
            return "—";
        }
        return new Intl.NumberFormat(undefined, {
            style: "currency",
            currency: this.state.data.currency.name,
            maximumFractionDigits: this.state.data.currency.decimal_places,
        }).format(value || 0);
    }

    formatNumber(value) {
        return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value || 0);
    }

    formatPercent(value, total) {
        if (!total) {
            return "0%";
        }
        return `${(value / total * 100).toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
    }

    comparison(value) {
        if (value === null || value === undefined) {
            return "Sin base anterior";
        }
        const sign = value > 0 ? "+" : "";
        return `${sign}${value.toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
    }

    comparisonClass(value, inverse = false) {
        if (value === null || value === undefined || value === 0) {
            return "is-neutral";
        }
        const positive = inverse ? value < 0 : value > 0;
        return positive ? "is-positive" : "is-negative";
    }

    get kpis() {
        const metrics = this.state.data?.metrics || {};
        const comparisons = this.state.data?.comparisons || {};
        return [
            { key: "sales", label: "Ventas", value: this.formatMoney(metrics.sales), comparison: comparisons.sales },
            { key: "expenses", label: "Gastos registrados", value: this.formatMoney(metrics.expenses), comparison: comparisons.expenses, inverse: true, action: "expenses" },
            { key: "purchases", label: "Compras / inversión", value: this.formatMoney(metrics.purchases), comparison: comparisons.purchases, inverse: true, action: "purchases" },
            { key: "stock", label: "Stock a precio de venta", value: this.formatMoney(metrics.stock_value), snapshot: true, action: "stock" },
            { key: "result", label: "Resultado operativo estimado", value: this.formatMoney(metrics.operating_result), comparison: comparisons.operating_result },
            { key: "ticket", label: "Ticket promedio", value: this.formatMoney(metrics.average_ticket), comparison: comparisons.average_ticket },
            { key: "documents", label: "Operaciones de venta", value: this.formatNumber(metrics.document_count), comparison: comparisons.document_count },
            { key: "units", label: "Unidades vendidas", value: this.formatNumber(metrics.units_sold), comparison: comparisons.units_sold },
            { key: "alerts", label: "Productos con stock ≤ 5", value: this.formatNumber(metrics.low_stock_count), action: "low_stock", alert: metrics.low_stock_count > 0 },
        ];
    }

    barWidth(value, rows, field) {
        const maximum = Math.max(...rows.map((row) => Math.abs(row[field] || 0)), 1);
        return `${Math.max(2, Math.abs(value || 0) / maximum * 100)}%`;
    }

    openRecords(kind) {
        const ids = this.state.data.record_ids[kind] || [];
        const actions = {
            sales: { name: "Comprobantes de venta", res_model: "account.move", views: [[false, "list"], [false, "form"]] },
            expenses: { name: "Gastos registrados", res_model: "hr.expense", views: [[false, "list"], [false, "form"]] },
            purchases: { name: "Órdenes de compra", res_model: "purchase.order", views: [[false, "list"], [false, "form"]] },
            stock: { name: "Productos almacenables", res_model: "product.product", views: [[false, "list"], [false, "form"]] },
            low_stock: { name: "Productos con stock bajo", res_model: "product.product", views: [[false, "list"], [false, "form"]] },
            pos_sales: { name: "Ventas de Point of Sale", res_model: "pos.order", views: [[false, "list"], [false, "form"]] },
            store_sales: { name: "Ventas de la tienda web", res_model: "sale.order", views: [[false, "list"], [false, "form"]] },
            other_sales: { name: "Otras ventas facturadas", res_model: "account.move", views: [[false, "list"], [false, "form"]] },
        };
        if (!ids.length) {
            this.notification.add("No hay registros relacionados para abrir.", { type: "info" });
            return;
        }
        return this.action.doAction({ type: "ir.actions.act_window", domain: [["id", "in", ids]], target: "current", ...actions[kind] });
    }

    openProduct(productId) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "product.product",
            res_id: productId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("shop_customer_auth.executive_dashboard", ExecutiveDashboard);
