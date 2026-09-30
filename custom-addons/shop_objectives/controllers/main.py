from odoo import http
from odoo.http import request

IMAGE_MAX_SIZE = 1024
IMAGE_MAX_AGE = 3600


class ShopObjectiveImageController(http.Controller):
    """Sirve públicamente solo la imagen de los objetivos activos.

    El modelo `shop.product.objective` no es legible por usuarios públicos ni
    portal (ver OBJ-04), así que `/web/image` devuelve el placeholder para los
    visitantes de la tienda. Esta ruta expone únicamente el campo `image`.
    """

    @http.route(
        "/shop_objectives/image/<int:objective_id>",
        type="http",
        auth="public",
        methods=["GET"],
        readonly=True,
    )
    def objective_image(self, objective_id, **kwargs):
        objective = (
            request.env["shop.product.objective"]
            .sudo()
            .search([("id", "=", objective_id)], limit=1)
        )
        if not objective or not objective.image:
            raise request.not_found()

        stream = request.env["ir.binary"]._get_image_stream_from(
            objective,
            "image",
            width=IMAGE_MAX_SIZE,
            height=IMAGE_MAX_SIZE,
        )
        stream.public = True
        if kwargs.get("v"):
            # La URL versionada cambia cada vez que se edita el objetivo.
            return stream.get_response(
                immutable=True, max_age=http.STATIC_CACHE_LONG,
            )
        return stream.get_response(max_age=IMAGE_MAX_AGE)
