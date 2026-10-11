/** @type {import('tailwindcss').Config} */
//
// Sistema de diseño del CRM-AT.
//
// La identidad sale del logo oficial de AplicacionAT: azul marino #00205b y
// celeste #08b2ff. Sobre esa base se construyó una escala funcional, porque el
// celeste de marca sobre blanco da 2.38:1 y no se puede usar para texto.
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
  theme: {
    extend: {
      colors: {
        // ── Marca ────────────────────────────────────────────────────────────
        brand: {
          navy: "#00205b",   // oficial, tomado del logo
          sky: "#08b2ff",    // oficial, tomado del logo
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
          50: "#f1f4f9",
          100: "#e3e9f3",
          200: "#c4d0e4",
          300: "#96aacb",
          400: "#5c78a8",
          500: "#2d4f8a",
          600: "#0b3d91",
          700: "#00205b",
          800: "#001844",
          900: "#001232",
        },

        // Se conserva el nombre viejo porque dos plantillas todavía lo usan.
        "background-light": "#f7f8fa",

        // ── Semánticos (pasan AA sobre blanco) ───────────────────────────────
        // Para estados y para las cifras de los indicadores.
        exito: { 50: "#ecfdf5", 100: "#d1fae5", 500: "#047857", 600: "#065f46", 700: "#064e3b" },
        alerta: { 50: "#fffbeb", 100: "#fef3c7", 500: "#b45309", 600: "#92400e", 700: "#78350f" },
        peligro: { 50: "#fef2f2", 100: "#fee2e2", 500: "#b91c1c", 600: "#991b1b", 700: "#7f1d1d" },
        info: { 50: "#f0f9ff", 100: "#e0f2fe", 500: "#0369a1", 600: "#075985", 700: "#0c4a6e" },

        // ── Superficies y texto ──────────────────────────────────────────────
        // Un solo juego de grises para toda la aplicación.
        superficie: {
          base: "#f7f8fa",   // fondo de la aplicación
          card: "#ffffff",   // tarjetas
          suave: "#f1f3f6",  // cabeceras de tabla, bloques secundarios
          borde: "#e2e5eb",  // bordes
          fuerte: "#cbd2dd", // bordes marcados
        },
        texto: {
          fuerte: "#0f172a", // títulos
          base: "#334155",   // cuerpo
          suave: "#5b6b82",  // secundario (5.1:1 sobre blanco: pasa AA)
          tenue: "#7b8798",  // solo para texto >= 14px que no sea crítico
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
