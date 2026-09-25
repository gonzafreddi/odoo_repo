import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

patch(PaymentScreen.prototype, {
    get cashDiscountPercent() {
        return this.pos.config.shop_cash_discount_percent || 0;
    },

    /** Líneas con precio: en combos el precio lo llevan los componentes. */
    get cashDiscountLines() {
        return this.currentOrder.lines.filter((line) => line.getUnitPrice() > 0);
    },

    get isCashDiscountApplied() {
        const lines = this.cashDiscountLines;
        return (
            lines.length > 0 &&
            lines.every((line) => line.getDiscount() === this.cashDiscountPercent)
        );
    },

    toggleCashDiscount() {
        const discount = this.isCashDiscountApplied ? 0 : this.cashDiscountPercent;
        for (const line of this.cashDiscountLines) {
            line.setDiscount(discount);
        }
    },
});
