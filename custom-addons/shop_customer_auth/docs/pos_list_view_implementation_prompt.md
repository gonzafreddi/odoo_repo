# Implementación de vista lista en el Punto de Venta

Trabajá en el repositorio:

`/home/suplex/odoo_suplex/odoo_repo`

Implementá una vista lista para los productos del Punto de Venta de Odoo 19.

## Condiciones

- Hacé todas las modificaciones exclusivamente dentro de `custom-addons/shop_customer_auth`.
- No modifiques archivos originales de `addons/point_of_sale`.
- Conservá todos los cambios existentes del usuario.
- Usá extensiones OWL, `t-inherit`, `patch` y assets del POS.
- Inspeccioná primero los archivos actuales para confirmar los puntos de extensión.
- Implementá y validá el resultado; no te limites a presentar un plan.

## 1. Pantalla principal del POS

Agregar un selector con dos botones:

- Vista cuadrícula.
- Vista lista.

La vista inicial debe ser cuadrícula. La elección debe persistirse en `localStorage` para que el navegador recuerde la última vista seleccionada.

En vista lista:

- Un producto por fila.
- Fotografía a la izquierda.
- Imagen de aproximadamente 72 × 72 px.
- Usar `object-fit: cover`.
- La imagen nunca debe tapar el texto.
- Nombre a la derecha, permitiendo hasta tres líneas.
- Mantener el clic, pulsación larga, cantidad en carrito y demás comportamiento original.
- Adaptarlo para celulares y pantallas táctiles.

## 2. Configurador de combos

Los productos del popup `point_of_sale.ComboConfiguratorPopup` deben mostrarse siempre como lista, independientemente de la vista principal.

Cada opción debe tener:

- Fotografía a la izquierda.
- Nombre completo a la derecha.
- Precio adicional visible.
- Controles de cantidad funcionando.
- Estado seleccionado funcionando.
- Una fila por opción.
- Diseño responsive.

## 3. Implementación esperada

Modificar `custom-addons/shop_customer_auth/__manifest__.py`:

- Agregar `point_of_sale` a `depends`.
- Registrar los nuevos archivos en `point_of_sale._assets_pos`.

Crear archivos dentro de una estructura similar a:

```text
custom-addons/shop_customer_auth/static/src/pos/
├── product_screen.js
├── product_screen.xml
├── combo_configurator.xml
└── pos_product_list.scss
```

### JavaScript

- Importar `ProductScreen`.
- Usar `patch(ProductScreen.prototype, {...})`.
- Extender `setup()` llamando primero a `super.setup(...arguments)`.
- Añadir `state.productViewMode`.
- Leer y guardar la opción en `localStorage`.
- Aceptar únicamente `grid` o `list`.
- Manejar de forma segura la indisponibilidad de `localStorage`.

### XML

- Extender `point_of_sale.ProductScreen` con `t-inherit-mode="extension"`.
- Agregar los botones de vista.
- Aplicar clases dinámicas al contenedor y a `ProductCard`.
- Extender `point_of_sale.ComboConfiguratorPopup`.
- Aplicar clases de lista a su `product-list` y sus `ProductCard`.
- No copiar completas las plantillas originales.

### SCSS

- Forzar una sola columna en modo lista.
- Anular correctamente el comportamiento de Bootstrap `.ratio` en las imágenes horizontales.
- Usar tamaños fijos y `min-width` para impedir que la imagen invada el texto.
- Mantener bordes redondeados.
- Adaptar los tamaños en pantallas pequeñas.
- Evitar selectores globales que alteren otras pantallas del POS.

## Archivos originales relevantes

- `addons/point_of_sale/static/src/app/screens/product_screen/product_screen.js`
- `addons/point_of_sale/static/src/app/screens/product_screen/product_screen.xml`
- `addons/point_of_sale/static/src/app/components/product_card/product_card.xml`
- `addons/point_of_sale/static/src/app/components/product_card/product_card.scss`
- `addons/point_of_sale/static/src/app/components/popups/combo_configurator_popup/combo_configurator_popup.xml`
- `addons/point_of_sale/static/src/app/components/popups/combo_configurator_popup/combo_configurator_popup.scss`

## Validación requerida

- Validar sintaxis XML.
- Revisar el manifest.
- Revisar imports y sintaxis JavaScript.
- Comprobar los XPath contra las plantillas originales.
- Ejecutar las pruebas o validaciones disponibles que sean pertinentes.
- Mostrar al final los archivos modificados y explicar cómo actualizar el módulo y limpiar o reconstruir los assets del POS.
- No iniciar ni desplegar el servidor salvo que sea necesario y esté autorizado.
