/** @type {import('tailwindcss').Config} */
//
// Sistema de diseño del CRM-AT.
//
// La identidad de la aplicación es el azul marino #00205b y el celeste #08b2ff.
// Sobre esa base se construyó una escala funcional, porque el celeste de marca
// sobre blanco da 2.38:1 y no se puede usar para texto.
//
// Los colores semánticos están elegidos para pasar WCAG AA (4.5:1) sobre blanco.
// Antes se usaban emerald-500 (2.54:1), amber-500 (2.15:1) y slate-400 (2.56:1)
// para las cifras de los indicadores: los números más mirados eran justo los
// menos legibles.
//
// Cada decisión está anotada para que se entienda y no se deshaga sola.
module.exports = {
  // Sin modo oscuro: se retiró por decisión del usuario (duplicaba cada
  // componente y no se usaba).
  //
  // OJO: `darkMode: false` NO desactiva el modo oscuro. En Tailwind v3 esa
  // opción se interpreta como `media`, así que las clases `dark:` se generan
  // dentro de `@media (prefers-color-scheme: dark)` y la interfaz se ve a medio
  // pintar en cualquier equipo con el sistema en oscuro (comprobado). Con
  // `'class'` las reglas quedan atadas al elemento `.dark`, que ya no existe en
  // ningún lado: son inertes. Las que queden en las plantillas no hacen nada.
  darkMode: "class",
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js",
  ],
  // Tailwind busca nombres de clase literales en el código. Cuando una clase se
  // arma con una interpolación de Jinja, como
  //
  //     class="peer-checked:border-{{ color }}-500"
  //
  // el nombre final (`peer-checked:border-exito-500`) nunca aparece en el fuente,
  // así que Tailwind no genera la regla y el color no se aplica. Eso rompía el
  // selector de criticidad del relevamiento.
  //
  // Se listan sólo las clases que de verdad se interpolan: `color` toma los
  // valores exito, alerta y peligro. Un patrón amplio generaba 756 KB de CSS en
  // lugar de 52 KB.
  safelist: [
    ...[
      "text-{{c}}-600", "text-{{c}}-500", "border-{{c}}-500", "bg-{{c}}-50",
      "peer-checked:border-{{c}}-500", "peer-checked:bg-{{c}}-50",
      "peer-checked:text-{{c}}-500",
    ].flatMap((t) => ["exito", "alerta", "peligro"].map((c) => t.replace("{{c}}", c))),
  ],
  theme: {
    extend: {
      colors: {
        // ── Marca ────────────────────────────────────────────────────────────
        brand: {
          navy: "#00205b",   // base de la identidad
          sky: "#08b2ff",    // acento de la identidad
        },

        // ── Primario: escala derivada del navy ───────────────────────────────
        // DEFAULT conserva el azul de ACCIÓN para las ~980 clases que la
        // aplicación ya usa sin sufijo (bg-primary, text-primary, ring-primary,
        // shadow-primary). Sin esta clave, redefinir `primary` como escala deja
        // esas clases sin color y la interfaz se ve en blanco.
        //
        // 600 (#0b3d91) es el azul de ACCIÓN: 10.04:1 sobre blanco, así que
        // sirve para botones, enlaces y texto con contraste de sobra.
        // 700 (#00205b) es el ancla de marca, para acentos fuertes.
        // 50-200 son fondos suaves; 300-400, bordes.
        primary: {
          DEFAULT: "#0b3d91",
          // Los tonos claros son azules de verdad, no el navy aclarado con
          // blanco: eso daba grises azulados con 3% de saturación y los fondos
          // tintados se veían blancos.
          50: "#eef4fd",
          100: "#d8e6fa",
          200: "#b3cdf4",
          300: "#85abe8",
          400: "#5583d4",
          500: "#2f5fb5",
          600: "#0b3d91",
          700: "#00205b",
          800: "#001844",
          900: "#001232",
        },

        // Se conserva el nombre viejo porque dos plantillas todavía lo usan.
        "background-light": "#f7f8fa",

        // ── Semánticos ───────────────────────────────────────────────────────
        // Escalas completas para poder reemplazar los colores sueltos de
        // Tailwind (red-500, emerald-500...) por el nombre del sistema.
        //
        // El tono 500 de cada familia es el ANCLA y está elegido para pasar
        // WCAG AA sobre blanco, que es lo que fallaba antes:
        //   exito-500   #047857  5.48:1   (antes emerald-500, 2.54:1)
        //   alerta-500  #b45309  5.02:1   (antes amber-500,   2.15:1)
        //   peligro-500 #b91c1c  6.47:1   (antes red-500,     3.76:1)
        //   info-500    #0369a1  5.93:1
        exito: {
          50: "#ecfdf5", 100: "#d1fae5", 200: "#a7f3d0", 300: "#6ee7b7",
          400: "#34d399", 500: "#047857", 600: "#065f46", 700: "#064e3b",
          800: "#053f2e", 900: "#04291f",
        },
        alerta: {
          50: "#fffbeb", 100: "#fef3c7", 200: "#fde68a", 300: "#fcd34d",
          400: "#fbbf24", 500: "#b45309", 600: "#92400e", 700: "#78350f",
          800: "#5c2a0c", 900: "#451f08",
        },
        peligro: {
          50: "#fef2f2", 100: "#fee2e2", 200: "#fecaca", 300: "#fca5a5",
          400: "#f87171", 500: "#b91c1c", 600: "#991b1b", 700: "#7f1d1d",
          800: "#651717", 900: "#4c1111",
        },
        info: {
          50: "#f0f9ff", 100: "#e0f2fe", 200: "#bae6fd", 300: "#7dd3fc",
          400: "#38bdf8", 500: "#0369a1", 600: "#075985", 700: "#0c4a6e",
          800: "#0a3a56", 900: "#082c42",
        },

        // ── Superficies y texto ──────────────────────────────────────────────
        // Un solo juego de grises para toda la aplicación.
        superficie: {
          base: "#eef1f7",   // fondo de la aplicación (antes #f7f8fa, casi blanco)
          card: "#ffffff",   // tarjetas
          suave: "#f1f3f6",  // cabeceras de tabla, bloques secundarios
          borde: "#e2e5eb",  // bordes
          fuerte: "#cbd2dd", // bordes marcados
        },
        texto: {
          fuerte: "#0f172a", // títulos (17.85:1)
          base: "#334155",   // cuerpo (10.35:1)
          suave: "#5b6b82",  // secundario (5.43:1)
          // El tono más claro tiene que pasar AA igual: #7b8798 daba 3.65:1 y
          // quedaba por debajo del mínimo, que es justo el problema que se
          // estaba corrigiendo.
          tenue: "#6f7684",  // terciario (4.56:1)
        },
      },

      // ── Tipografía ─────────────────────────────────────────────────────────
      // Escala con PISO DE 12px. Antes había 13 tamaños distintos y 780 usos por
      // debajo de 12px (el más frecuente era 9px), incluidos 10 valores
      // arbitrarios como text-[8px]. Nada de eso entra en esta escala.
      fontSize: {
        "2xs": ["0.75rem", { lineHeight: "1rem" }],      // 12px — mínimo absoluto
        xs: ["0.8125rem", { lineHeight: "1.125rem" }],   // 13px
        sm: ["0.875rem", { lineHeight: "1.25rem" }],     // 14px
        base: ["0.9375rem", { lineHeight: "1.5rem" }],   // 15px
        lg: ["1.0625rem", { lineHeight: "1.625rem" }],   // 17px
        xl: ["1.25rem", { lineHeight: "1.75rem" }],      // 20px
        "2xl": ["1.5rem", { lineHeight: "2rem" }],       // 24px
        "3xl": ["1.875rem", { lineHeight: "2.25rem" }],  // 30px — cifras de indicador
        "4xl": ["2.25rem", { lineHeight: "2.5rem" }],    // 36px
      },

      // ── Radios: dos, no cuatro ─────────────────────────────────────────────
      // Antes convivían rounded-lg (340), xl (465), 2xl (129) y 3xl (37) para
      // los mismos elementos.
      borderRadius: {
        md: "0.5rem",    // controles: inputs, botones chicos
        lg: "0.75rem",   // tarjetas y botones
        full: "9999px",  // píldoras de estado
      },

      // ── Sombras: dos, no cinco ─────────────────────────────────────────────
      boxShadow: {
        card: "0 1px 2px 0 rgb(15 23 42 / 0.04), 0 1px 3px 0 rgb(15 23 42 / 0.06)",
        pop: "0 10px 24px -6px rgb(15 23 42 / 0.16), 0 4px 8px -4px rgb(15 23 42 / 0.08)",
      },

      fontFamily: {
        display: ["Inter", "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [
    require("@tailwindcss/forms")({ strategy: "class" }),
    require("@tailwindcss/container-queries"),
  ],
};
