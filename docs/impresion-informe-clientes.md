# Impresión del informe de clientes

El informe de clientes (`/cliente-reporte/{id}`, «Informe Estratégico de Cuenta») se
imprime desde el navegador. Este documento deja escrito cómo funciona la paginación
y por qué está hecha así.

## El problema

El informe nació como **una hoja única**: la plantilla dibujaba una hoja con
`min-height` de A4 y un pie que decía «Página 1 de 1» escrito a mano.

Con un cliente de veinte máquinas y treinta visitas el contenido no entra, y
aparecían tres cosas:

1. **Las tarjetas de máquina se partían al medio.** El título quedaba en una hoja y
   el número de serie en la siguiente. Se ve en el PDF: una hoja termina con
   «MARCA 13 / Modelo 013 / S/N: SN-00013» y la siguiente arranca con «Línea: Línea 13».
2. **La tabla de contactos dejaba media hoja en blanco.** El informe es una columna
   `flex`, y un ítem de flex no se parte: si la tabla no entraba en lo que quedaba de
   hoja, se iba entera a la siguiente.
3. **El pie mentía.** Decía «Página 1 de 1» con siete hojas impresas.

Y un cuarto, que no era de impresión pero impedía imprimir: **el botón «Imprimir
Reporte» no hacía nada**. Tenía `id="btn-print-customer"` y el manejador busca
`[data-print-btn]`. Los otros informes sí lo tenían.

## Cómo funciona ahora

El reparto en hojas lo hace `static/js/informe-paginado.js`.

**La hoja es la caja que se mide.** Cada hoja es un `<article class="hoja">` de
210 × 296 mm con `overflow: hidden` en el cuerpo. Como el alto está fijado, lo que
se mide en pantalla es exactamente lo que se imprime: no hay que adivinar dónde va a
cortar el navegador.

El milímetro de menos (296 en vez de 297) es a propósito: una hoja de 297 mm exactos
en una página de 297 mm roza el redondeo y termina imprimiendo una página en blanco
detrás de cada hoja.

**El paginador llena y corta.** Recorre las piezas del informe en orden, las mete en
la hoja y, cuando el cuerpo se desborda (`scrollHeight > clientHeight`), corta la
pieza que no entró y la continuación abre la hoja siguiente. Cada tipo de contenido
sabe cortarse:

| Contenido | Cómo se corta |
|---|---|
| Tablas (contactos, historial de visitas) | Por filas, repitiendo el `thead` |
| Rejilla de máquinas | Por tarjetas, para que ninguna quede al medio |
| Observaciones | Por palabras, con `data-partible="texto"` |

**El pie se llena al final**, cuando ya se sabe cuántas hojas hay: «Página 3 de 6».
La plantilla lo deja vacío a propósito — un número escrito a mano vuelve a ser
mentira en cuanto el informe pasa de una hoja.

**La última hoja no fuerza el salto**, o saldría una página en blanco al final.

**Sin JavaScript** el informe queda en una tirada larga: se imprime peor, pero se
imprime. Si el paginador falla, limpia las hojas vacías que haya dejado y deja el
informe como vino.

## Dónde está cada cosa

| Archivo | Qué hace |
|---|---|
| `templates/cliente_reporte.html` | Las piezas del informe, el `<template>` de la hoja y el CSS |
| `static/js/informe-paginado.js` | El paginador |
| `tests/pdf_cliente.py` | Imprime con Chrome y mide sobre el PDF |
| `tests/test_impresion_cliente.py` | Las pruebas |

## Cómo se verifica

`tests/pdf_cliente.py` renderiza el informe con un cliente de **24 máquinas y 30
visitas**, embebe las hojas de estilo y las fuentes reales, lo imprime con Chrome
headless y comprueba sobre el PDF:

- que el informe ocupe más de una hoja (si entrara en una, la prueba no mediría nada);
- que el número de páginas impresas **coincida** con el que declara el pie;
- que no se pierda el final: la última máquina, la última visita y la referencia;
- que ninguna tarjeta de máquina quede partida entre dos hojas;
- que el encabezado de una tabla que cruza de hoja se repita.

Las fuentes se embeben como *data URI*: si no, los íconos salen impresos como su
palabra ligadura («person», «handshake») y las alturas medidas no son las reales.

La prueba se omite sola si no hay Chrome o `pypdf`, para que la suite siga corriendo
en cualquier entorno.

## Lo que se midió

| | Antes | Después |
|---|---|---|
| Hojas del informe de prueba | 7 | 6 |
| Tarjetas partidas | 2 | 0 |
| Encabezados repetidos al cruzar de hoja | sí | sí |
| El pie dice | «Página 1 de 1» | «Página 1 de 6» … «Página 6 de 6» |
| La tabla de contactos empieza en | hoja 2 | hoja 1 |
| Botón de imprimir | no hacía nada | imprime |

Con un cliente que entra en una hoja, el resultado sigue siendo una sola hoja que
dice «Página 1 de 1».

## Los otros informes

`relevamiento_reporte.html` e `infraestructura_reporte.html` ya tenían el CSS de
impresión completo (`@page`, `thead` repetido, filas sin partir). **No se tocaron**:
el problema era sólo del informe de clientes, que era el único sin ese bloque.

Si alguna vez hay que paginar uno de esos, el paginador se puede reutilizar: espera
un contenedor con `data-informe-paginado` y una plantilla `template[data-hoja-modelo]`
cuyo contenido tenga `[data-hoja-cuerpo]` y `[data-hoja-numero]`.
