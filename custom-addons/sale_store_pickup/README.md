# Sale Store Pickup

Agrega el campo booleano almacenado e indexado `x_is_store_pickup` a
`sale.order` y datos de envío almacenados directamente en la venta: teléfono,
calle, número, piso/departamento, localidad, provincia, código postal,
referencias, costo real cotizado y detalle de bultos. El cliente de la orden es
el destinatario, por lo que no se duplica ese dato. Provincia, localidad y
código postal permiten búsquedas y métricas geográficas.

Al pasar un envío al estado `shipped`, el módulo genera y adjunta un remito PDF
operativo sin precios ni costos. También puede imprimirse manualmente desde la
orden con el botón **Imprimir remito**.

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

## Correo Argentino MiCorreo

La activación, usuario, contraseña, ID de cliente y código postal de origen se
configuran en **Ajustes → Ventas → Correo Argentino MiCorreo**. La contraseña
guardada no vuelve a mostrarse: dejá el campo vacío para conservarla o marcá
**Eliminar contraseña guardada** para borrarla. Odoo impide activar la
integración si falta algún dato requerido.

El usuario XML-RPC configurado en Nest necesita el grupo **Integración API de
Correo Argentino** (en **Integraciones Suplex**) para consultar los parámetros mínimos de ejecución. Asigná ese
grupo al mismo usuario técnico que usa Nest; no le da permisos administrativos
generales. Nest conserva únicamente la URL técnica de la API, timeout y conexión
de la base de cotizaciones.

Las cajas se mantienen en **Ventas → Configuración → Cajas de envío**. Para cada
caja cargá las medidas internas (para acomodar productos), externas (para
Correo Argentino), el peso de la caja y embalaje, y el peso máximo bruto. En la
ficha del producto, pestaña **Envío**, cargá peso y medidas por unidad. El
empaquetador asigna las unidades a una o más cajas, suma el peso de los productos
y agrega la tara de cada caja. El pedido guarda el detalle de cada bulto y el
peso total.

El precio que paga el cliente es el **Precio fijo** configurado en el
transportista de Correo Argentino. La tarifa agregada de MiCorreo se conserva
como costo real informativo del pedido.

Nest guarda las cotizaciones temporales en PostgreSQL, en la base indicada por
`SHIPPING_DATABASE_URL`. Crea la tabla y el índice al guardar o recuperar la
primera cotización; no requiere ejecutar una migración manual.
