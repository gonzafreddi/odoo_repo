{
    "name": "Suplex Shop Objectives",
    "version": "19.0.1.0.0",
    "category": "Sales/Sales",
    "summary": "Objetivos comerciales (colecciones editoriales de productos) para la tienda online",
    "description": "Modela objetivos ('Ganar masa muscular', 'Definir', ...) con líneas ordenadas de "
                   "product.template, gestionables desde Odoo y consumidos por NestJS/Next.js.",
    "author": "Suplex",
    "depends": ["sale_management"],
    "data": [
        "security/ir.model.access.csv",
        "data/shop_product_objective_data.xml",
        "views/shop_product_objective_views.xml",
        "views/product_template_views.xml",
        "views/shop_product_objective_menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "shop_objectives/static/src/scss/shop_objective_form.scss",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
