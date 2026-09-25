import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

patch(PaymentScreen.prototype, {
    get cardSurchargePercent() {
        return this.pos.config.shop_card_surcharge_percent || 0;
    },

    /** Líneas con precio: en combos el precio lo llevan los componentes. */
    get cardSurchargeLines() {
        return this.currentOrder.lines.filter(
            (line) => line.getUnitPrice() > 0 || line.shop_card_surcharge_base > 0
        );
    },

    get isCardSurchargeApplied() {
        const lines = this.cardSurchargeLines;
        return lines.length > 0 && lines.every((line) => line.shop_card_surcharge_base > 0);
    },

    /**
     * Aplica el recargo a las líneas que todavía no lo tienen (p. ej. productos
     * agregados después) o, si ya está en todas, lo quita volviendo al precio base.
     */
    toggleCardSurcharge() {
        const remove = this.isCardSurchargeApplied;
        for (const line of this.cardSurchargeLines) {
            if (remove) {
                line.setUnitPrice(line.shop_card_surcharge_base);
                line.shop_card_surcharge_base = 0;
            } else if (!(line.shop_card_surcharge_base > 0)) {
                const base = line.getUnitPrice();
                line.shop_card_surcharge_base = base;
                line.setUnitPrice(base * (1 + this.cardSurchargePercent / 100));
                // Que un cambio de cantidad no recalcule el precio y pierda el recargo.
                line.price_type = "manual";
            }
        }
        this.currentOrder.recomputeOrderData();
    },
});
