# Sale Store Pickup

Agrega el campo booleano almacenado e indexado `x_is_store_pickup` a
`sale.order` y datos simples de envío almacenados directamente en la venta:
teléfono, calle, número, piso/departamento, localidad, provincia, código
postal, referencias y costo real cotizado. El cliente de la orden es el
destinatario, por lo que no se duplica ese dato.

El módulo no usa lógica vinculada con `carrier_id`. El costo real del envío
se completa manualmente después de cotizarlo. Provincia, localidad y código
postal permiten búsquedas y métricas geográficas.

El campo `x_logistics_status` mantiene un seguimiento logístico independiente
del estado comercial estándar de Odoo. Sus valores son pendiente, en
preparación, enviado, listo para retirar, entregado y cancelado.

## Instalación y actualización

Incluya `custom-addons` en el `addons_path` de Odoo y ejecute:

```bash
./odoo-bin -d <base_de_datos> -i sale_store_pickup --stop-after-init
```

Para actualizar una instalación existente:

```bash
./odoo-bin -d <base_de_datos> -u sale_store_pickup --stop-after-init
```

## XML-RPC

El usuario de integración debe tener acceso de creación, lectura y escritura
sobre pedidos de venta (por ejemplo, el grupo estándar Usuario: solo documentos
propios de Ventas). El valor se envía directamente en `sale.order.create`:

```python
order_id = models.execute_kw(
    db,
    uid,
    password,
    "sale.order",
    "create",
    [{
        "partner_id": partner_id,
        "x_is_store_pickup": True,
    }],
)
```

Puede verificarse el contrato externo con:

```python
models.execute_kw(
    db,
    uid,
    password,
    "sale.order",
    "fields_get",
    [["x_is_store_pickup"]],
    {"attributes": ["type", "string", "required", "readonly"]},
)
```

El dominio para obtener exclusivamente retiros es:

```python
[("x_is_store_pickup", "=", True)]
```
