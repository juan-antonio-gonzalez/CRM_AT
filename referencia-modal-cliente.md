# Modal de Registro de Cliente — Referencia

## Estructura general

```html
<!-- Botón que abre el modal -->
<button type="button" id="btn-nuevo-cliente">
    <span class="material-symbols-rounded text-sm">person_add</span>
    Nuevo Cliente
</button>

<!-- Modal overlay -->
<div id="nuevoClienteModal" class="hidden fixed inset-0 z-[100] flex ... bg-slate-900/60 backdrop-blur-sm overflow-y-auto">
    <div class="bg-white dark:bg-slate-900 w-full max-w-6xl rounded-3xl shadow-2xl ... my-8">
        <!-- Header -->
        <div class="flex items-center justify-between p-6 border-b ...">
            <div class="flex items-center gap-3">
                <span class="material-symbols-rounded text-primary">person_add</span>
                <h3 class="text-lg font-black ...">Registro de Cuenta</h3>
            </div>
            <button type="button" id="btn-close-nuevo-cliente" class="size-10 rounded-xl ...">
                <span class="material-symbols-rounded">close</span>
            </button>
        </div>

        <!-- Formulario -->
        <form action="/nuevo-cliente" method="POST" class="p-6 space-y-6 max-h-[calc(100vh-16rem)] overflow-y-auto">
            <input type="hidden" name="csrf_token" value="{{ request.state.csrf_token or '' }}">
            <!-- Campos del formulario -->
        </form>
    </div>
</div>
```

## Características implementadas

### 1. Modal overlay
- `hidden` + `fixed inset-0 z-[100]` con `backdrop-blur-sm`
- Scroll interno en el formulario: `max-h-[calc(100vh-16rem)] overflow-y-auto`
- Cierre al hacer clic fuera (`e.target === this`)

### 2. Select con creación inline
Cada `<select>` de tabla auxiliar tiene un botón `+` a la derecha:

```html
<div class="relative">
    <div class="flex gap-1.5">
        <div class="flex-1">
            <select name="industry_sector" class="w-full ...">...</select>
        </div>
        <button type="button" class="quick-add-btn size-9 shrink-0 rounded-xl ..."
                data-entity="sector" data-select="industry_sector">
            <span class="material-symbols-rounded text-lg">add</span>
        </button>
    </div>
    <!-- Popover -->
    <div class="quick-add-popover hidden absolute right-0 top-full mt-1 z-50 ...">
        <div class="flex gap-2">
            <input type="text" class="quick-add-input ..." placeholder="Nuevo...">
            <button type="button" class="quick-add-confirm ...">Crear</button>
        </div>
    </div>
</div>
```

**Mapping entity → select:**
| Entity | data-entity | data-select |
|--------|-------------|-------------|
| Sector Industrial | `sector` | `industry_sector` |
| Asesor Comercial | `commercial` | `assigned_commercial` |
| Asistente Técnico | `advisor` | `technical_advisor` |
| Diseñador | `designer` | `designer` |

**Endpoint:** `POST /configuracion/add/{entity}` con `name` + `csrf_token` (form-urlencoded).  
El endpoint acepta `Accept: application/json` para devolver JSON en vez de redirect.

### 3. Uppercase automático
Todos los inputs `type="text"` dentro del modal:
- Clase Tailwind `uppercase` (visual)
- Listener `input` → `this.value.toUpperCase()` (valor real)

```javascript
document.querySelectorAll('#nuevoClienteModal input[type="text"]').forEach(input => {
    input.addEventListener('input', function() {
        this.value = this.value.toUpperCase();
    });
});
```

Para filas agregadas dinámicamente (equipo), el listener se asigna tras crear el nodo.

### 4. Deduplicación de selects
Al cargar, elimina opciones duplicadas en todos los `<select>` del modal:

```javascript
document.querySelectorAll('#nuevoClienteModal select').forEach(select => {
    const seen = new Set();
    Array.from(select.options).forEach(opt => {
        const val = opt.value.trim().toLowerCase();
        if (val && seen.has(val)) opt.remove();
        else if (val) seen.add(val);
    });
});
```

### 5. Backend: datos para dropdowns
El endpoint de la página debe pasar las listas de tablas auxiliares:

```python
return templates.TemplateResponse("pagina.html", {
    "request": request,
    "advisors": db.query(models.TechnicalAdvisor).order_by(models.TechnicalAdvisor.name).all(),
    "designers": db.query(models.Designer).order_by(models.Designer.name).all(),
    "commercials": db.query(models.CommercialAdvisor).order_by(models.CommercialAdvisor.name).all(),
    "sectors": db.query(models.IndustrialSector).order_by(models.IndustrialSector.name).all(),
})
```

### 6. JS del modal (open/close)

```javascript
const modal = document.getElementById('nuevoClienteModal');

function openModal() {
    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closeModal() {
    modal.classList.add('hidden');
    document.body.style.overflow = '';
}

modal.addEventListener('click', function(e) {
    if (e.target === this) closeModal();
});
```

## CSP Compliance
- Todos los handlers via `addEventListener` (sin inline `onclick`)
- Todos los `<script>` llevan `nonce="{{ request.state.script_nonce }}"`
- `getCsrfToken()` disponible globalmente desde `app.js`
