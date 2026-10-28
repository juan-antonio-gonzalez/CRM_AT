# Íconos

La aplicación usa Material Symbols Rounded. Los íconos se dibujan por **ligadura**:
el `<span>` contiene el *nombre* del ícono y la fuente lo reemplaza por el glifo.

```html
<span class="material-symbols-rounded">diversity_3</span>
```

Eso tiene una consecuencia que hay que tener presente todo el tiempo: **si el glifo
no está en la fuente, no hay ningún error**. Se imprime el nombre. En el menú
lateral, un ícono que falta se ve como un título enorme en mayúsculas con guiones
bajos ocupando el lugar de la opción.

Así apareció «DIVERSITY_3» en el menú, en lugar del ícono de Equipos.

## La fuente es un subset

La fuente completa pesa 5,3 MB para ~118 íconos: el 99% del peso de la primera
carga. `deploy/subset-iconos.sh` le pide a Google Fonts un subset con exactamente
los íconos usados y lo deja vendorizado en `static/fonts/`, así el navegador no
depende de ningún CDN.

```
bash deploy/subset-iconos.sh
```

El script hace tres cosas:

1. Saca los nombres de ícono de las plantillas y del JavaScript con
   `deploy/iconos.py`.
2. Le pide el subset a Google Fonts y guarda el `.woff2`.
3. Le pone a la `url()` de cada fuente en `fonts.css` la **huella de su archivo**.

## Las dos formas de romperlo

Las dos son silenciosas. Ninguna da error, ninguna rompe una prueba que no exista
para eso, y las dos se descubren mirando la pantalla.

### 1. Un nombre inválido o mal extraído

Google descarta los nombres inválidos sin avisar. La fuente se genera igual, sin
ese glifo, y el ícono se imprime como texto.

Los nombres no se sacan con una búsqueda de texto suelta porque un ícono
condicional se escribe de dos formas y las dos se leían mal:

```jinja
{{ 'group' if clave == 'clientes' else 'precision_manufacturing' }}
{% if sort == 'fecha_desc' %}expand_more{% else %}expand_less{% endif %}
```

- Buscar todas las cadenas entrecomilladas metía **`clientes`**, que es un valor de
  comparación, y también `fecha_desc` de un ordenamiento.
- En la forma con `{% if %}` no se encontraba **ninguno**, porque los nombres van
  sin comillas.

Y `{{ icono }}` es una *variable*: su nombre no es un ícono.

`deploy/iconos.py` saca la condición y mira sólo las ramas. Tiene pruebas en
`tests/test_iconos.py` porque es la parte que se equivoca en silencio.

### 2. La caché de la fuente

`fonts.css` se pide con `?v=<huella de todo lo estático>`, pero **la caché de
fuentes va por URL**: la `url()` de adentro apuntaba a una ruta fija, así que el
navegador seguía usando la fuente vieja para siempre.

Por eso `diversity_3` se siguió viendo como «DIVERSITY_3» **después** de agregar el
ícono y regenerar la fuente. En una máquina limpia se veía bien; en la del usuario,
que ya tenía la fuente vieja, no.

Ahora el paso 3 del script le pone la huella de cada archivo a su `url()`. Cuando
la fuente cambia, cambia la URL, y el navegador la vuelve a pedir.

## Cómo se verifica

`tests/iconos_subset.py` dibuja **todos** los íconos del subset y mide el ancho de
cada uno desde JavaScript. Un glifo ocupa alrededor de un cuadro; un nombre que no
se reemplazó ocupa el ancho del texto, varias veces más. Comparando contra la
mediana los que faltan se delatan solos.

```bash
python3 tests/iconos_subset.py             # verifica
python3 tests/iconos_subset.py --captura   # además deja la lámina para mirar
```

Se corre en la suite como `test_todos_los_iconos_del_subset_tienen_glifo`, y se
saltea sola si no hay Chrome.

`tests/test_iconos.py` cubre además que la lista en disco esté al día: si una
plantilla estrena un ícono y nadie regenera la fuente, la prueba falla y lo dice.
Es la única forma de que un ícono nuevo no se descubra en pantalla.

## Para capturar una pantalla

`tests/captura.py` arma una página autocontenida con el CSS y las fuentes reales
embebidas, y la fotografía con Chrome. Sirve para mirar cómo queda una pantalla sin
depender del servidor.

```bash
python3 tests/captura.py pagina.html salida.png 1400
```

Las fuentes van como data URI a propósito: desde un archivo temporal, las rutas
`/static/...` no existen y **todos** los íconos saldrían como texto, que es
justamente lo que se quiere ver bien.

## Si un ícono se ve como texto

1. Mirá si el nombre es un ícono real de Material Symbols.
2. Si lo es, corré `bash deploy/subset-iconos.sh` y después
   `python3 tests/iconos_subset.py`.
3. Si el nombre está mal, corregilo en la plantilla y volvé al paso 2.
4. Si el ícono se ve bien en tu máquina pero mal en otra, es caché: verificá que la
   `url()` en `fonts.css` tenga `?v=`.
