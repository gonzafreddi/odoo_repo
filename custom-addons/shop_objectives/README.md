# Suplex Shop Objectives

This addon models the online shop's editorial product collections by commercial objective, such as gaining muscle mass or defining.

- `shop.product.objective` stores each objective and its descriptive content.
- `shop.product.objective.line` orders the `product.template` records associated with an objective.

Vistas de administración y carga de objetivos iniciales: ver tarea OBJ-03.

## Exposición vía XML-RPC para NestJS (OBJ-04)

Dos métodos RPC en `shop.product.objective`, llamables por `execute_kw` como cualquier método de Odoo
(primer argumento de `args` = lista de ids vacía). Requieren un usuario autenticado con acceso de lectura
al modelo (grupo `base.group_user`, ya otorgado en `security/ir.model.access.csv`); un usuario sin ese
acceso recibe `AccessError`. No se expone el campo `image` — Nest arma la URL pública
(`/web/image/shop.product.objective/<id>/image`) solo con el `id`, igual que ya hace con productos.

Ejemplo real, capturado contra `suplex_test` (2026-09-14):

```python
common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")

models.execute_kw(db, uid, password, "shop.product.objective", "list_active", [[]])
```

```json
[
  {
    "id": 22,
    "name": "Ganar masa muscular",
    "slug": "ganar-masa",
    "short_description": "Proteínas, creatina y carbohidratos para sumar volumen y fuerza.",
    "sequence": 10
  },
  { "id": 23, "name": "Definir", "slug": "definir", "short_description": "...", "sequence": 20 },
  { "id": 24, "name": "Tener más energía", "slug": "energia", "short_description": "...", "sequence": 30 },
  { "id": 25, "name": "Mejorar recuperación", "slug": "recuperacion", "short_description": "...", "sequence": 40 }
]
```

```python
models.execute_kw(db, uid, password, "shop.product.objective", "get_by_slug", [[], "ganar-masa"])
```

```json
{
  "id": 22,
  "name": "Ganar masa muscular",
  "slug": "ganar-masa",
  "short_description": "Proteínas, creatina y carbohidratos para sumar volumen y fuerza.",
  "description": "<p>Elegí los productos pensados para ganar masa muscular: ...</p>",
  "sequence": 10,
  "lines": [
    { "product_tmpl_id": 162, "sequence": 10, "featured": true },
    { "product_tmpl_id": 166, "sequence": 20, "featured": true },
    { "product_tmpl_id": 173, "sequence": 30, "featured": true },
    { "product_tmpl_id": 186, "sequence": 40, "featured": false },
    { "product_tmpl_id": 177, "sequence": 50, "featured": false }
  ]
}
```

`get_by_slug` con un slug inexistente o de un objetivo archivado devuelve `false` (Python `False`); un
objetivo activo sin líneas devuelve el dict con `"lines": []`.
