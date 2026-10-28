/**
 * Pagina el informe de clientes en hojas A4.
 *
 * Por qué existe
 * --------------
 * El informe nació como una hoja única: la plantilla dibuja «una hoja» con
 * `min-height` de A4 y un pie que decía «Página 1 de 1» escrito a mano. Cuando el
 * cliente tiene veinte máquinas y treinta visitas, el contenido no entra, el
 * navegador corta por donde puede y el pie sigue diciendo «1 de 1».
 *
 * Dejarlo al navegador tampoco alcanza. El informe es una columna `flex`, y un
 * ítem de flex no se parte: si la tabla de contactos no entra en lo que queda de
 * la hoja, se va entera a la siguiente y deja media hoja en blanco. Peor: las
 * tarjetas de máquina sí se parten, y quedan con su título en una hoja y su número
 * de serie en la otra.
 *
 * Qué hace
 * --------
 * Reparte el contenido en hojas de A4 exactas y le pone a cada una su número. La
 * hoja es la caja que se mide: como el alto está fijado, lo que se mide es lo que
 * se imprime, y no hay que adivinar dónde va a cortar el navegador.
 *
 * Cómo
 * ----
 * Se sacan los hijos del informe como «piezas» en orden, se van metiendo en la
 * hoja y, cuando la hoja se desborda, se corta la pieza que no entró y la
 * continuación abre la hoja siguiente. Cada tipo de contenido sabe cortarse:
 * las tablas por filas, las rejillas por tarjetas, y el texto por palabras.
 *
 * Si algo falla, el informe queda como vino: sin paginar se imprime peor, pero se
 * imprime.
 */
(function () {
    'use strict';

    // Tope de vueltas por pieza. Cortar una tabla de mil filas de a una necesita
    // muchas, pero no infinitas: si algo se traba, se corta y se sigue.
    var MAX_VUELTAS = 400;

    function desborda(cuerpo) {
        return cuerpo.scrollHeight > cuerpo.clientHeight + 1;
    }

    /** Abre una hoja nueva al final del contenedor y la devuelve. */
    function abrirHoja(contenedor, modelo) {
        var hoja = modelo.cloneNode(true);
        hoja.querySelector('[data-hoja-cuerpo]').innerHTML = '';
        contenedor.appendChild(hoja);
        return hoja;
    }

    /** Marca el título de una continuación, sin repetir la marca si ya la tenía. */
    function marcarContinuacion(copia) {
        var titulo = copia.querySelector('h3, h4');
        if (titulo) {
            titulo.textContent = titulo.textContent.replace(/\s*\(continúa\)\s*$/, '') +
                ' (continúa)';
        }
        return copia;
    }

    /**
     * Corta una tabla por filas.
     *
     * Saca filas del final hasta que la sección entre y devuelve una sección nueva
     * —con el mismo `thead`— para la hoja siguiente. Que el encabezado se repita es
     * lo que hace que la hoja dos se entienda sola.
     */
    function cortarPorFilas(seccion, cuerpo) {
        var tabla = seccion.querySelector('table');
        var filas = tabla && tabla.tBodies[0];
        if (!filas || filas.rows.length < 2) return null;

        var sacadas = [];
        while (desborda(cuerpo) && filas.rows.length > 1) {
            // Se sacan de abajo hacia arriba y se guardan al principio, para
            // conservar el orden.
            sacadas.unshift(filas.removeChild(filas.rows[filas.rows.length - 1]));
        }
        if (!sacadas.length) {
            sacadas.forEach(function (f) { filas.appendChild(f); });
            return null;
        }

        var copia = marcarContinuacion(seccion.cloneNode(true));
        var destino = copia.querySelector('table');
        var cuerpoCopia = destino.tBodies[0];
        while (cuerpoCopia.rows.length) cuerpoCopia.removeChild(cuerpoCopia.rows[0]);
        sacadas.forEach(function (f) { cuerpoCopia.appendChild(f); });
        return copia;
    }

    /** Corta una rejilla de tarjetas: ninguna tarjeta queda partida al medio. */
    function cortarPorTarjetas(seccion, cuerpo) {
        var rejilla = seccion.querySelector('[data-partible="tarjetas"]');
        if (!rejilla || rejilla.children.length < 2) return null;

        var sacadas = [];
        while (desborda(cuerpo) && rejilla.children.length > 1) {
            sacadas.unshift(rejilla.removeChild(rejilla.children[rejilla.children.length - 1]));
        }
        if (!sacadas.length) {
            sacadas.forEach(function (t) { rejilla.appendChild(t); });
            return null;
        }

        var copia = marcarContinuacion(seccion.cloneNode(true));
        var destino = copia.querySelector('[data-partible="tarjetas"]');
        destino.innerHTML = '';
        sacadas.forEach(function (t) { destino.appendChild(t); });
        return copia;
    }

    /**
     * Corta un bloque de texto por palabras.
     *
     * Es el último recurso: las observaciones son un solo nodo de texto largo, sin
     * filas ni tarjetas, y sin esto una observación de tres páginas se recortaría.
     */
    function cortarPorTexto(seccion, cuerpo) {
        var bloque = seccion.querySelector('[data-partible="texto"]');
        if (!bloque) return null;

        var original = bloque.textContent;
        var palabras = original.split(/(\s+)/);
        if (palabras.length < 40) return null;

        // Se van sacando las últimas palabras hasta que entre. Se corta de a poco
        // para no hacer cientos de reflows con un texto enorme.
        var sacadas = [];
        var paso = Math.max(1, Math.floor(palabras.length / 50));
        while (desborda(cuerpo) && palabras.length > 40) {
            var desde = Math.max(0, palabras.length - paso);
            sacadas = palabras.slice(desde).concat(sacadas);
            palabras = palabras.slice(0, desde);
            bloque.textContent = palabras.join('');
        }
        if (!sacadas.length) {
            bloque.textContent = original;
            return null;
        }

        var copia = marcarContinuacion(seccion.cloneNode(true));
        var destino = copia.querySelector('[data-partible="texto"]');
        // `trim` sólo del principio: el espacio inicial pertenece a la separación
        // entre las dos hojas.
        destino.textContent = sacadas.join('').replace(/^\s+/, '');
        return copia;
    }

    function cortar(seccion, cuerpo) {
        return cortarPorFilas(seccion, cuerpo) ||
               cortarPorTarjetas(seccion, cuerpo) ||
               cortarPorTexto(seccion, cuerpo);
    }

    function paginar(contenedor) {
        var plantilla = contenedor.querySelector('template[data-hoja-modelo]');
        if (!plantilla) return false;
        var modelo = plantilla.content.firstElementChild;
        if (!modelo) return false;

        // Las piezas se sacan del informe ya renderizado, en orden.
        var piezas = [];
        Array.prototype.forEach.call(contenedor.children, function (hijo) {
            if (hijo.tagName === 'TEMPLATE') return;
            piezas.push(hijo);
        });
        if (!piezas.length) return false;

        contenedor.innerHTML = '';
        var hojas = [abrirHoja(contenedor, modelo)];
        var cuerpo = hojas[0].querySelector('[data-hoja-cuerpo]');

        function siguienteHoja() {
            hojas.push(abrirHoja(contenedor, modelo));
            cuerpo = hojas[hojas.length - 1].querySelector('[data-hoja-cuerpo]');
        }

        piezas.forEach(function (pieza) {
            cuerpo.appendChild(pieza);

            // Un bucle porque una pieza puede necesitar varias hojas: treinta
            // visitas no entran en una sola ni cortando una vez.
            var restante = pieza;
            var vueltas = 0;
            while (desborda(cuerpo) && vueltas < MAX_VUELTAS) {
                vueltas += 1;
                var continuacion = cortar(restante, cuerpo);
                if (!continuacion) break;   // no se puede cortar más: se deja
                siguienteHoja();
                cuerpo.appendChild(continuacion);
                restante = continuacion;
            }
        });

        var total = hojas.length;
        hojas.forEach(function (hoja, i) {
            var numero = hoja.querySelector('[data-hoja-numero]');
            if (numero) numero.textContent = 'Página ' + (i + 1) + ' de ' + total;
        });

        contenedor.setAttribute('data-hojas', String(total));
        return true;
    }

    function iniciar() {
        var contenedor = document.querySelector('[data-informe-paginado]');
        if (!contenedor || contenedor.getAttribute('data-hojas')) return;
        try {
            paginar(contenedor);
        } catch (e) {
            // Si falla, se deja el informe como vino. Queda una hoja vacía al
            // principio, así que se limpia.
            if (window.console && console.warn) {
                console.warn('No se pudo paginar el informe:', e);
            }
            var vacias = contenedor.querySelectorAll('[data-hoja]');
            Array.prototype.forEach.call(vacias, function (h) { h.remove(); });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', iniciar);
    } else {
        iniciar();
    }
})();
