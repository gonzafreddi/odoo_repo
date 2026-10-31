# Suplex Shop Config

This addon adds the online shop's shipping, payment, and Cyber Suplex settings to Sales configuration. It stores public storefront settings in `ir.config_parameter`; the NestJS backend reads and filters them through XML-RPC, so Odoo credentials are never sent to Next.js.

Cyber campaign start and exclusive end are entered as `YYYY-MM-DD HH:MM` in `America/Argentina/Buenos_Aires`. The addon converts these values to explicit UTC instants before saving. The end is exclusive, so the configured campaign remains active through the preceding minute.
