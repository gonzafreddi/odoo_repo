{
    "name": "Suplex Shop Config",
    "version": "19.0.1.0.0",
    "category": "Sales/Sales",
    "summary": "Store-front configuration (free-shipping threshold) shared with the online shop",
    "description": "Adds free-shipping threshold / default shipping cost settings, consumed by the Suplex online shop.",
    "author": "Suplex",
    "depends": ["sale_management"],
    "data": [
        "data/ir_config_parameter.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
