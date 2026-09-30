import base64
import io

from PIL import Image

from odoo.tests import HttpCase, tagged


def _png(color):
    buffer = io.BytesIO()
    Image.new("RGB", (40, 60), color).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue())


@tagged("post_install", "-at_install")
class TestShopObjectiveImage(HttpCase):
    def _create_objective(self, slug, **values):
        return self.env["shop.product.objective"].create({
            "name": slug,
            "slug": slug,
            **values,
        })

    def test_public_visitor_gets_active_objective_image(self):
        objective = self._create_objective("imagen-publica", image=_png("red"))

        response = self.url_open(f"/shop_objectives/image/{objective.id}")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["Content-Type"].startswith("image/"))
        self.assertIn("public", response.headers.get("Cache-Control", ""))

    def test_missing_image_and_archived_objective_are_not_found(self):
        without_image = self._create_objective("sin-imagen")
        archived = self._create_objective(
            "archivado", image=_png("blue"), active=False,
        )

        for objective in (without_image, archived):
            response = self.url_open(f"/shop_objectives/image/{objective.id}")
            self.assertEqual(response.status_code, 404)

    def test_rpc_exposes_image_version_only_when_there_is_an_image(self):
        with_image = self._create_objective("con-version", image=_png("green"))
        without_image = self._create_objective("sin-version")

        self.assertTrue(with_image.get_by_slug("con-version")["image_version"])
        self.assertIs(
            without_image.get_by_slug("sin-version")["image_version"], False,
        )
        versions = {
            objective["slug"]: objective["image_version"]
            for objective in self.env["shop.product.objective"].list_active()
        }
        self.assertEqual(
            versions["con-version"],
            with_image.get_by_slug("con-version")["image_version"],
        )
        self.assertIs(versions["sin-version"], False)

    def test_versioned_url_is_cached_long_term(self):
        objective = self._create_objective("imagen-versionada", image=_png("red"))

        response = self.url_open(f"/shop_objectives/image/{objective.id}?v=1")

        self.assertEqual(response.status_code, 200)
        self.assertIn("immutable", response.headers.get("Cache-Control", ""))
