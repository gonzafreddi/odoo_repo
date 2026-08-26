/** @odoo-module */

import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { SelectPartnerButton } from "@point_of_sale/app/screens/product_screen/control_buttons/select_partner_button/select_partner_button";

patch(OrderPaymentValidation.prototype, {
  async isOrderValid(isForceValidate) {
    const customerAccountPayments = this.order.payment_ids.filter(
      (payment) =>
        payment.payment_method_id.is_customer_account &&
        !this.pos.currency.isZero(payment.amount),
    );
    if (customerAccountPayments.length) {
      const partner = this.order.getPartner();
      if (!partner) {
        this.pos.dialog.add(AlertDialog, {
          title: _t("Cliente requerido"),
          body: _t(
            "Debés seleccionar un cliente para utilizar Cuenta Corriente.",
          ),
        });
        return false;
      }

      const newDebt = customerAccountPayments.reduce(
        (total, payment) => total + Math.max(payment.amount, 0),
        0,
      );
      const balance = partner.current_account_balance || 0;
      const limit = partner.credit_limit || 0;
      if (
        limit > 0 &&
        !this.pos.currency.isZero(newDebt) &&
        balance + newDebt > limit + this.pos.currency.rounding / 2
      ) {
        const available = limit - balance;
        this.pos.dialog.add(AlertDialog, {
          title: _t("Límite de crédito excedido"),
          body: _t(
            "Saldo actual: %(balance)s\nNueva deuda: %(debt)s\n" +
              "Límite: %(limit)s\nDisponible: %(available)s",
            {
                            balance: this.pos.env.utils.formatCurrency(balance),
                            debt: this.pos.env.utils.formatCurrency(newDebt),
                            limit: this.pos.env.utils.formatCurrency(limit),
                            available: this.pos.env.utils.formatCurrency(available),
            },
          ),
        });
        return false;
      }
    }
    return super.isOrderValid(...arguments);
  },
});

patch(SelectPartnerButton.prototype, {
  formatCustomerAccountAmount(amount) {
    return this.env.utils.formatCurrency(amount || 0);
  },
});
