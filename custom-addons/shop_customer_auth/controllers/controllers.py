# from odoo import http


# class ShopCustomerAuth(http.Controller):
#     @http.route('/shop_customer_auth/shop_customer_auth', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/shop_customer_auth/shop_customer_auth/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('shop_customer_auth.listing', {
#             'root': '/shop_customer_auth/shop_customer_auth',
#             'objects': http.request.env['shop_customer_auth.shop_customer_auth'].search([]),
#         })

#     @http.route('/shop_customer_auth/shop_customer_auth/objects/<model("shop_customer_auth.shop_customer_auth"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('shop_customer_auth.object', {
#             'object': obj
#         })

