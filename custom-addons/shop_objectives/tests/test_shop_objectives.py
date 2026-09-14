from psycopg2 import IntegrityError

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestShopObjectives(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Objective = cls.env["shop.product.objective"]
        cls.Line = cls.env["shop.product.objective.line"]
        cls.product = cls.env["product.template"].create({
            "name": "Proteína de prueba",
        })
        cls.other_product = cls.env["product.template"].create({
            "name": "Creatina de prueba",
        })

    def _create_objective(self, **values):
        return self.Objective.create({
            "name": "Ganar masa muscular",
            "slug": "ganar-masa-muscular",
            **values,
        })

    def test_objective_lines_can_be_ordered_and_objective_archived(self):
        objective = self._create_objective()
        first_line = self.Line.create({
            "objective_id": objective.id,
            "product_tmpl_id": self.product.id,
            "sequence": 20,
        })
        second_line = self.Line.create({
            "objective_id": objective.id,
            "product_tmpl_id": self.other_product.id,
            "sequence": 10,
        })

        self.assertEqual(objective.line_ids, second_line | first_line)
        first_line.write({"sequence": 5})
        self.assertEqual(objective.line_ids, first_line | second_line)
        objective.write({"active": False})
        self.assertFalse(objective.active)

    def test_product_can_belong_to_multiple_objectives(self):
        first_objective = self._create_objective(slug="ganar-masa-muscular")
        second_objective = self._create_objective(
            name="Definir",
            slug="definir-prueba",
        )

        first_line = self.Line.create({
            "objective_id": first_objective.id,
            "product_tmpl_id": self.product.id,
        })
        second_line = self.Line.create({
            "objective_id": second_objective.id,
            "product_tmpl_id": self.product.id,
        })

        self.assertEqual(self.product.objective_line_ids, first_line | second_line)

    def test_slug_must_be_unique(self):
        self._create_objective()

        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self._create_objective(name="Otro objetivo")

    def test_product_cannot_be_repeated_in_an_objective(self):
        objective = self._create_objective()
        self.Line.create({
            "objective_id": objective.id,
            "product_tmpl_id": self.product.id,
        })

        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.Line.create({
                "objective_id": objective.id,
                "product_tmpl_id": self.product.id,
            })

    def test_internal_user_can_read_but_cannot_modify_objectives(self):
        objective = self._create_objective()
        internal_user = new_test_user(
            self.env,
            login="shop_objectives_internal_user",
            groups="base.group_user",
        )
        objective_as_user = objective.with_user(internal_user)

        self.assertEqual(objective_as_user.read(["name"])[0]["name"], objective.name)
        with self.assertRaises(AccessError):
            objective_as_user.write({"name": "No autorizado"})
        with self.assertRaises(AccessError):
            self.Objective.with_user(internal_user).create({
                "name": "No autorizado",
                "slug": "no-autorizado",
            })
        with self.assertRaises(AccessError):
            objective_as_user.unlink()

    def test_seeded_objectives_have_active_curated_lines_and_feature_limit(self):
        """Protect the business seed: each public objective stays usable."""
        for slug in ("ganar-masa", "definir", "energia", "recuperacion"):
            objective = self.Objective.search([("slug", "=", slug)])
            self.assertEqual(len(objective), 1, "Missing seeded objective: %s" % slug)
            self.assertTrue(objective.active)
            active_lines = objective.line_ids.filtered("active")
            self.assertGreaterEqual(len(active_lines), 3)
            self.assertLessEqual(len(active_lines.filtered("featured")), 3)

    def test_list_active_returns_ordered_seeded_objectives_without_archived_ones(self):
        archived_objective = self._create_objective(
            name="Objetivo archivado RPC",
            slug="objetivo-archivado-rpc",
            sequence=5,
            active=False,
        )

        objectives = self.Objective.list_active()

        self.assertEqual(
            [(objective["slug"], objective["sequence"]) for objective in objectives],
            [
                ("ganar-masa", 10),
                ("definir", 20),
                ("energia", 30),
                ("recuperacion", 40),
            ],
        )
        self.assertNotIn(archived_objective.id, [objective["id"] for objective in objectives])

    def test_get_by_slug_returns_active_lines_and_featured_state(self):
        objective = self.Objective.get_by_slug("ganar-masa")

        self.assertEqual(objective["slug"], "ganar-masa")
        self.assertTrue(objective["lines"])
        self.assertTrue(any(line["featured"] for line in objective["lines"]))
        self.assertEqual(
            [line["sequence"] for line in objective["lines"]],
            sorted(line["sequence"] for line in objective["lines"]),
        )

    def test_get_by_slug_returns_false_for_an_unknown_slug(self):
        self.assertFalse(self.Objective.get_by_slug("no-existe-este-slug"))

    def test_get_by_slug_returns_false_for_an_archived_objective(self):
        objective = self._create_objective(
            name="Objetivo archivado RPC",
            slug="objetivo-archivado-rpc",
            active=False,
        )

        self.assertFalse(self.Objective.get_by_slug(objective.slug))

    def test_get_by_slug_returns_empty_lines_for_an_active_objective_without_lines(self):
        objective = self._create_objective(
            name="Objetivo vacío RPC",
            slug="objetivo-vacio-rpc",
        )

        result = self.Objective.get_by_slug(objective.slug)

        self.assertEqual(result["id"], objective.id)
        self.assertEqual(result["lines"], [])

    def test_rpc_methods_require_objective_read_access(self):
        internal_user = new_test_user(
            self.env,
            login="shop_objectives_rpc_internal_user",
            groups="base.group_user",
        )
        portal_user = new_test_user(
            self.env,
            login="shop_objectives_rpc_portal_user",
            groups="base.group_portal",
        )

        self.assertEqual(
            len(self.Objective.with_user(internal_user).list_active()),
            4,
        )
        self.assertEqual(
            self.Objective.with_user(internal_user).get_by_slug("ganar-masa")["slug"],
            "ganar-masa",
        )
        with self.assertRaises(AccessError):
            self.Objective.with_user(portal_user).list_active()
        with self.assertRaises(AccessError):
            self.Objective.with_user(portal_user).get_by_slug("ganar-masa")
