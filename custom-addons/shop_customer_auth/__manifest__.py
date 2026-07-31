{
    'name': "shop_customer_auth",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '19.0.1.0.0',

    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'sale_management',
        'purchase',
        'stock',
        'account',
        'hr_expense',
        'point_of_sale',
    ],

    'assets': {
        'point_of_sale._assets_pos': [
            'shop_customer_auth/static/src/pos/product_screen.js',
            'shop_customer_auth/static/src/pos/product_screen.xml',
            'shop_customer_auth/static/src/pos/combo_configurator.xml',
            'shop_customer_auth/static/src/pos/pos_product_list.scss',
        ],
        'web.assets_backend': [
            'shop_customer_auth/static/src/dashboard/executive_dashboard.js',
            'shop_customer_auth/static/src/dashboard/executive_dashboard.xml',
            'shop_customer_auth/static/src/dashboard/executive_dashboard.scss',
            'shop_customer_auth/static/src/stock/quick_stock_adjustment.js',
            'shop_customer_auth/static/src/stock/quick_stock_adjustment.xml',
            'shop_customer_auth/static/src/stock/quick_stock_adjustment.scss',
        ],
    },

    # always loaded
    'data': [
        'security/password_reset_security.xml',
        'security/ir.model.access.csv',
        'data/password_reset_cron.xml',
        'views/executive_dashboard_views.xml',
        'views/quick_stock_adjustment_views.xml',
        'views/product_template_views.xml',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
