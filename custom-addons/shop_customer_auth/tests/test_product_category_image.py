import base64
import io

from PIL import Image

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "shop_category_image")
class TestProductCategoryImage(TransactionCase):
    def test_category_stores_image_readable_by_public(self):
        buffer = io.BytesIO()
        Image.new("RGB", (800, 600), "red").save(buffer, format="PNG")
        category = self.env["product.category"].create({
            "name": "Categoría con imagen",
            "image_1920": base64.b64encode(buffer.getvalue()),
        })
        self.assertTrue(category.image_512)
        self.assertTrue(category.image_128)
        public = self.env.ref("base.public_user")
        self.assertTrue(category.with_user(public).image_512)
