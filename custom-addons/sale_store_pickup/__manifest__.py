{
    "name": "Sale Store Pickup",
    "version": "19.0.1.0.0",
    "category": "Sales/Sales",
    "summary": "Identify sale orders that are collected at the store",
    "description": "Adds a store-pickup flag to quotations and sale orders.",
    "author": "Suplex",
    "depends": [
        "delivery",
        "sale_stock",
    ],
    "data": [
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
