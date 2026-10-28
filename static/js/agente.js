/* ── Caty: el panel flotante ─────────────────────────────────────────────────
 *
 * Tres decisiones que valen la pena conocer:
 *
 * 1. **El texto del modelo nunca pasa por `innerHTML`.** Todo se construye con
 *    `createElement` y `textContent`. El contenido viene de un modelo de lenguaje
 *    que a su vez leyó lo que escribió el usuario: tratarlo como HTML sería abrir
 *    la puerta que todo el diseño del backend se esfuerza en cerrar.
 *
 * 2. **`fetch` en lugar de `EventSource`.** `EventSource` sólo hace GET, y el
 *    endpoint necesita POST para mandar la pregunta, el historial y el token
 *    CSRF. Así que se lee el cuerpo de la respuesta con un `ReadableStream` y se
 *    parsean los bloques SSE a mano, que es lo que hace `EventSource` por dentro.
 *
 * 3. **El hilo vive en `sessionStorage`, por pestaña.** Se recupera al recargar y
 *    se pierde al cerrar la pestaña. Sin historial entre días.
 * ─────────────────────────────────────────────────────────────────────────── */

(function () {
  "use strict";

  var raiz = document.getElementById("caty");
  if (!raiz) return;

  var panel = document.getElementById("caty-panel");
  var boton = document.getElementById("caty-boton");
  var cerrar = document.getElementById("caty-cerrar");
  var limpiar = document.getElementById("caty-limpiar");
  var form = document.getElementById("caty-form");
  var entrada = document.getElementById("caty-entrada");
  var enviar = document.getElementById("caty-enviar");
  var mensajes = document.getElementById("caty-mensajes");
  var aviso = document.getElementById("caty-aviso");
  var nombre = document.getElementById("caty-titulo").textContent.trim();

  var USUARIO = raiz.getAttribute("data-usuario") || "anonimo";
  var CLAVE_HILO = "caty:hilo:" + USUARIO;
  var MAX_HILO = 20;
  var MAX_ENTRADA = 1000;

  var hilo = [];
  var ocupada = false;
  var ultimaPregunta = "";

  // ── Utilidades ──────────────────────────────────────────────────────────

  function tokenCsrf() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  }

  function guardarHilo() {
    try {
      sessionStorage.setItem(CLAVE_HILO, JSON.stringify(hilo.slice(-MAX_HILO)));
    } catch (e) {
      /* Modo privado o cuota llena: no vale la pena molestar al usuario. */
    }
  }

  function leerHilo() {
    try {
      var crudo = sessionStorage.getItem(CLAVE_HILO);
      var datos = crudo ? JSON.parse(crudo) : [];
      return Array.isArray(datos) ? datos : [];
    } catch (e) {
      return [];
    }
  }

  // ── Markdown mínimo, sin innerHTML ──────────────────────────────────────
  //
  // Se soporta lo que el system prompt pide: negrita, cursiva, código y enlaces
  // internos. Nada más: el panel es chico y no hay encabezados.

  var ENLINEA = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;

  function nodosEnlinea(texto) {
    var fragmento = document.createDocumentFragment();
    var partes = String(texto).split(ENLINEA);
    var m;

    partes.forEach(function (parte) {
      if (!parte) return;

      if ((m = /^\*\*([^*]+)\*\*$/.exec(parte))) {
        var fuerte = document.createElement("strong");
        fuerte.textContent = m[1];
        fragmento.appendChild(fuerte);
      } else if ((m = /^\*([^*]+)\*$/.exec(parte))) {
        var cursiva = document.createElement("em");
        cursiva.textContent = m[1];
        fragmento.appendChild(cursiva);
      } else if ((m = /^`([^`]+)`$/.exec(parte))) {
        var codigo = document.createElement("code");
        codigo.textContent = m[1];
        codigo.className = "rounded bg-superficie-suave px-1 py-0.5 text-2xs text-texto-fuerte";
        fragmento.appendChild(codigo);
      } else if ((m = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(parte))) {
        fragmento.appendChild(nodoEnlace(m[1], m[2]));
      } else {
        fragmento.appendChild(document.createTextNode(parte));
      }
    });

    return fragmento;
  }

  function nodoEnlace(etiqueta, destino) {
    var href = String(destino).trim();
    // Sólo enlaces internos. Un `javascript:` o un destino externo se muestra
    // como texto: el modelo no tiene por qué mandar a nadie afuera de la app.
    if (href.charAt(0) !== "/" || href.slice(0, 2) === "//") {
      return document.createTextNode(etiqueta);
    }
    var enlace = document.createElement("a");
    enlace.href = href;
    enlace.textContent = etiqueta;
    enlace.className = "font-semibold text-primary underline hover:text-primary-700";
    return enlace;
  }

  // La cita viaja al final del texto. Se recorta mientras llega, incluso si
  // viene cortada a la mitad, para que no se vea "[fuen" antes del chip.
  //
  // La palabra no se exige exacta: el modelo escribe `[fuente: ...]` casi
  // siempre, pero a veces se le va una letra. El servidor acepta la marca
  // tolerante, así que acá se recorta igual de tolerante — si no, el marcador
  // quedaría a la vista en el globo además de aparecer como chip.
  //
  // La segunda alternativa es sólo para el marcador a medio llegar, y exige que
  // el corchete quede abierto al final. Sin esa distinción se recortaría un
  // `[nombre]` legítimo, que el modelo bien podría escribir al nombrar un campo.
  var CITA = new RegExp(
    "[ \\t]*\\[\\s*[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,14}\\s*:[^\\]]*\\]?[ \\t]*$" +
    "|[ \\t]*\\[\\s*[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{0,14}[ \\t]*$"
  );

  function sinCita(texto) {
    return String(texto).replace(CITA, "");
  }

  function pintar(destino, texto) {
    destino.textContent = "";
    var lineas = sinCita(texto).split("\n");
    var lista = null;

    lineas.forEach(function (linea) {
      var item = /^\s*[-*]\s+(.*)$/.exec(linea);
      if (item) {
        if (!lista) {
          lista = document.createElement("ul");
          lista.className = "ml-4 list-disc space-y-1";
          destino.appendChild(lista);
        }
        var li = document.createElement("li");
        li.appendChild(nodosEnlinea(item[1]));
        lista.appendChild(li);
        return;
      }
      lista = null;
      if (linea.trim()) {
        var parrafo = document.createElement("p");
        parrafo.className = "whitespace-pre-wrap";
        parrafo.appendChild(nodosEnlinea(linea));
        destino.appendChild(parrafo);
      }
    });
  }

  // ── Burbujas ────────────────────────────────────────────────────────────

  function burbuja(rol) {
    var fila = document.createElement("div");
    fila.className = rol === "user" ? "flex justify-end" : "flex justify-start";

    if (rol === "assistant") {
      var avatar = document.createElement("span");
      avatar.className = "material-symbols-rounded mr-2 mt-1 shrink-0 text-primary";
      avatar.setAttribute("aria-hidden", "true");
      avatar.textContent = "smart_toy";
      fila.appendChild(avatar);
    }

    var globo = document.createElement("div");
    globo.className = rol === "user"
      ? "max-w-[85%] rounded-lg bg-primary px-3 py-2 text-sm text-white"
      : "max-w-[85%] space-y-2 rounded-lg bg-superficie-suave px-3 py-2 text-sm text-texto-base";
    fila.appendChild(globo);

    mensajes.appendChild(fila);
    bajar();
    return globo;
  }

  function bajar() {
    mensajes.scrollTop = mensajes.scrollHeight;
  }

  function chipFuente(globo, fuente) {
    var chip = document.createElement("p");
    chip.className = "text-2xs text-texto-tenue";
    chip.textContent = "Fuente: " + fuente;
    globo.appendChild(chip);
    bajar();
  }

  function mostrarAviso(texto, conReintento) {
    aviso.textContent = "";
    aviso.classList.remove("hidden");
    aviso.appendChild(document.createTextNode(texto));

    if (conReintento) {
      var boton = document.createElement("button");
      boton.type = "button";
      boton.className = "ml-2 font-bold underline";
      boton.textContent = "Reintentar";
      boton.addEventListener("click", function () {
        ocultarAviso();
        consultar(ultimaPregunta, true);
      });
      aviso.appendChild(boton);
    }
  }

  function ocultarAviso() {
    aviso.classList.add("hidden");
    aviso.textContent = "";
  }

  // ── Llamada al servidor ─────────────────────────────────────────────────

  function consultar(pregunta, esReintento) {
    if (ocupada) return;

    var texto = String(pregunta || "").trim().slice(0, MAX_ENTRADA);
    if (!texto) return;

    ultimaPregunta = texto;
    ocupada = true;
    enviar.disabled = true;
    actualizarLimpiar();
    ocultarAviso();

    if (!esReintento) {
      pintar(burbuja("user"), texto);
      hilo.push({ rol: "user", texto: texto });
      guardarHilo();
      actualizarLimpiar();
    }

    var globo = burbuja("assistant");
    var parrafo = document.createElement("p");
    parrafo.className = "whitespace-pre-wrap";
    parrafo.appendChild(document.createTextNode(""));
    globo.appendChild(parrafo);

    var acumulado = "";
    var fuente = "";

    var cuerpo = new URLSearchParams();
    cuerpo.set("mensaje", texto);
    cuerpo.set("ruta_actual", window.location.pathname);
    cuerpo.set("csrf_token", tokenCsrf());
    cuerpo.set("historial", JSON.stringify(hilo.slice(0, -1).slice(-MAX_HILO)));

    fetch("/api/agente/chat", {
      method: "POST",
      body: cuerpo,
      credentials: "same-origin",
      headers: { "Accept": "text/event-stream" }
    }).then(function (respuesta) {
      if (respuesta.status === 401) {
        throw new Error("Se cerró tu sesión. Recargá la página para seguir.");
      }
      if (respuesta.status === 503) {
        throw new Error(nombre + " no está configurada en este servidor.");
      }
      if (respuesta.status === 403) {
        throw new Error("No se pudo validar la petición. Recargá la página.");
      }
      if (!respuesta.ok || !respuesta.body) {
        throw new Error("No se pudo contactar al servidor.");
      }
      return leerStream(respuesta, function (evento) {
        if (evento.tipo === "token") {
          acumulado += (evento.datos && evento.datos.texto) || "";
          pintar(parrafo, acumulado);
          bajar();
        } else if (evento.tipo === "cita") {
          fuente = (evento.datos && evento.datos.fuente) || "";
        } else if (evento.tipo === "reemplazo") {
          // La respuesta no pasó la verificación: se reemplaza el globo entero.
          acumulado = (evento.datos && evento.datos.texto) || "";
          pintar(parrafo, acumulado);
          globo.classList.remove("bg-superficie-suave");
          globo.classList.add("bg-alerta-50", "border", "border-alerta-200");
          bajar();
        } else if (evento.tipo === "rechazo") {
          // Un rechazo no es un error: es una respuesta de Caty. Va con el mismo
          // aspecto que las demás, y si trae pantalla, el enlace ya viene en el
          // propio texto y `pintar` lo convierte en navegable.
          acumulado = (evento.datos && evento.datos.texto) || "";
          pintar(parrafo, acumulado);
          globo.classList.add("border", "border-superficie-borde");
          bajar();
        } else if (evento.tipo === "error") {
          acumulado = (evento.datos && evento.datos.mensaje) || "No pude responder.";
          pintar(parrafo, acumulado);
          globo.classList.remove("bg-superficie-suave");
          globo.classList.add("bg-peligro-50", "border", "border-peligro-200");
          bajar();
        } else if (evento.tipo === "fin") {
          acumulado = (evento.datos && evento.datos.texto) || acumulado;
          pintar(parrafo, acumulado);
        }
      });
    }).then(function () {
      if (fuente) chipFuente(globo, fuente);
      if (acumulado) {
        hilo.push({ rol: "assistant", texto: acumulado });
        hilo = hilo.slice(-MAX_HILO);
        guardarHilo();
        actualizarLimpiar();
      }
    }).catch(function (error) {
      globo.parentNode.removeChild(globo);
      mostrarAviso(error.message || "No se pudo contactar al servidor.", true);
    }).then(function () {
      ocupada = false;
      enviar.disabled = false;
      actualizarLimpiar();
      if (abierto()) entrada.focus();
    });
  }

  function leerStream(respuesta, alEvento) {
    var lector = respuesta.body.getReader();
    var decodificador = new TextDecoder();
    var buffer = "";

    function paso() {
      return lector.read().then(function (resultado) {
        if (resultado.done) return;
        buffer += decodificador.decode(resultado.value, { stream: true });

        var corte;
        while ((corte = buffer.indexOf("\n\n")) !== -1) {
          var bloque = buffer.slice(0, corte);
          buffer = buffer.slice(corte + 2);
          var evento = interpretar(bloque);
          if (evento) alEvento(evento);
        }
        return paso();
      });
    }

    return paso();
  }

  function interpretar(bloque) {
    var tipo = "message";
    var datos = [];

    bloque.split("\n").forEach(function (linea) {
      if (linea.indexOf("event:") === 0) tipo = linea.slice(6).trim();
      else if (linea.indexOf("data:") === 0) datos.push(linea.slice(5).trim());
    });

    if (!datos.length) return null;
    try {
      return { tipo: tipo, datos: JSON.parse(datos.join("\n")) };
    } catch (e) {
      return null;
    }
  }

  // ── Abrir y cerrar ──────────────────────────────────────────────────────

  function abierto() {
    return !panel.classList.contains("hidden");
  }

  // ── El saludo y el botón de limpiar ─────────────────────────────────────

  function saludar() {
    pintar(burbuja("assistant"),
      "Hola. Soy " + nombre + " y te enseño a usar la aplicación. " +
      "Preguntame dónde está algo o cómo se hace una tarea.");
  }

  // Limpiar está deshabilitado mientras no haya nada que limpiar y mientras Caty
  // esté respondiendo: si se vaciara a mitad de una respuesta, los fragmentos que
  // siguen llegando irían a parar a una conversación nueva y quedaría un hilo
  // mezclado, sin que se entienda por qué.
  function actualizarLimpiar() {
    limpiar.disabled = ocupada || hilo.length === 0;
  }

  function limpiarConversacion() {
    if (ocupada) return;

    mensajes.textContent = "";
    hilo = [];
    guardarHilo();
    saludar();
    actualizarLimpiar();
    entrada.focus();
  }

  function abrirPanel() {
    panel.hidden = false;
    panel.classList.remove("hidden");
    boton.setAttribute("aria-expanded", "true");
    if (!hilo.length && !mensajes.querySelector("p")) {
      saludar();
    }
    actualizarLimpiar();
    entrada.focus();
  }

  function cerrarPanel() {
    panel.classList.add("hidden");
    panel.hidden = true;
    boton.setAttribute("aria-expanded", "false");
    boton.focus();
  }

  function alternar() {
    if (abierto()) cerrarPanel(); else abrirPanel();
  }

  // ── Eventos ─────────────────────────────────────────────────────────────

  boton.addEventListener("click", alternar);
  cerrar.addEventListener("click", cerrarPanel);
  limpiar.addEventListener("click", limpiarConversacion);

  form.addEventListener("submit", function (evento) {
    evento.preventDefault();
    var texto = entrada.value;
    entrada.value = "";
    ajustarAlto();
    consultar(texto, false);
  });

  entrada.addEventListener("keydown", function (evento) {
    if (evento.key === "Enter" && !evento.shiftKey) {
      evento.preventDefault();
      form.dispatchEvent(new Event("submit", { cancelable: true }));
    }
  });

  document.addEventListener("keydown", function (evento) {
    // El panel se cierra con Escape sólo si el foco está adentro. Así no compite
    // con los otros modales de la aplicación, que escuchan Escape a nivel global.
    if (evento.key === "Escape" && abierto() && panel.contains(document.activeElement)) {
      evento.stopPropagation();
      cerrarPanel();
      return;
    }
    if (evento.ctrlKey && !evento.shiftKey && !evento.altKey &&
        (evento.key === "i" || evento.key === "I")) {
      evento.preventDefault();
      alternar();
      return;
    }
    if (evento.key === "Tab" && abierto()) atraparFoco(evento);
  });

  function atraparFoco(evento) {
    var enfocables = panel.querySelectorAll(
      'button:not([disabled]), textarea, a[href], [tabindex]:not([tabindex="-1"])');
    if (!enfocables.length) return;
    var primero = enfocables[0];
    var ultimo = enfocables[enfocables.length - 1];
    if (evento.shiftKey && document.activeElement === primero) {
      evento.preventDefault();
      ultimo.focus();
    } else if (!evento.shiftKey && document.activeElement === ultimo) {
      evento.preventDefault();
      primero.focus();
    }
  }

  function ajustarAlto() {
    entrada.style.height = "auto";
    entrada.style.height = Math.min(entrada.scrollHeight, 112) + "px";
  }

  entrada.addEventListener("input", ajustarAlto);

  // ── Hilo guardado ───────────────────────────────────────────────────────

  (function restaurar() {
    var guardado = leerHilo();
    if (!guardado.length) return;
    hilo = guardado;
    guardado.forEach(function (turno) {
      pintar(burbuja(turno.rol === "assistant" ? "assistant" : "user"), turno.texto);
    });
    actualizarLimpiar();
  })();

})();
