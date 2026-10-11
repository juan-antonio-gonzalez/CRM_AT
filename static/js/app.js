(() => {
  'use strict';

  // ── XSS-safe HTML escape ──
  function escapeHtml(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(String(str)));
    return div.innerHTML;
  }

  // ── Safe DOM insertion (replaces innerHTML for user-content) ──
  function setHTML(element, html, ...safeValues) {
    let safe = html;
    safeValues.forEach(val => {
      safe = safe.replace('%s', escapeHtml(val));
    });
    element.innerHTML = safe;
  }

  // ── Toast Notification System ──
  function showToast(message, type = 'success', duration = 4000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const icons = { success: 'check_circle', error: 'error', warning: 'warning', info: 'info' };
    const colorMap = {
      success: 'bg-emerald-50 bg-emerald-900/30 border-emerald-200 border-emerald-800 text-emerald-700 text-emerald-300',
      error: 'bg-red-50 bg-red-900/30 border-red-200 border-red-800 text-red-700 text-red-300',
      warning: 'bg-amber-50 bg-amber-900/30 border-amber-200 border-amber-800 text-amber-700 text-amber-300',
      info: 'bg-blue-50 bg-blue-900/30 border-blue-200 border-blue-800 text-blue-700 text-blue-300',
    };
    const iconColors = { success: 'text-emerald-500', error: 'text-red-500', warning: 'text-amber-500', info: 'text-blue-500' };

    const toast = document.createElement('div');
    toast.className = `pointer-events-auto flex items-center gap-3 px-5 py-4 rounded-2xl border shadow-xl backdrop-blur-sm ${colorMap[type] || colorMap.info} animate-fade-in translate-y-0`;
    toast.style.minWidth = '300px';
    toast.style.maxWidth = '450px';

    toast.innerHTML = `
      <span class="material-symbols-rounded ${iconColors[type] || iconColors.info}">${icons[type] || icons.info}</span>
      <p class="text-sm font-semibold flex-1">${escapeHtml(message)}</p>
      <button class="p-1 hover:opacity-70 transition-opacity shrink-0 toast-close">
        <span class="material-symbols-rounded text-lg">close</span>
      </button>`;

    toast.querySelector('.toast-close').addEventListener('click', () => toast.remove());

    container.appendChild(toast);

    setTimeout(() => {
      toast.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  // ── Controlador único de modales ──
  //
  // Antes cada pantalla tenía su propio par de funciones (17 en total), cada una
  // tocando `hidden` y `flex` a mano. Eso hacía que algunos modales no se
  // cerraran con Escape, que el foco quedara detrás del diálogo y que el fondo
  // no bloqueara el desplazamiento.
  //
  // Todo modal ahora se abre con `data-modal-open="<id>"` y se cierra con
  // `data-modal-close="<id>"`. El componente está en templates/_ui.html.
  let modalConFoco = null;

  function abrirModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modalConFoco = document.activeElement;
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    document.body.style.overflow = 'hidden';
    // El foco entra al diálogo para que el teclado no siga navegando el fondo.
    const primero = modal.querySelector(
      'input:not([type="hidden"]), select, textarea, button, [href]');
    if (primero) primero.focus({ preventScroll: true });
  }

  function cerrarModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    // Si no queda ningún modal abierto, se libera el desplazamiento.
    if (!document.querySelector('[role="dialog"]:not(.hidden)')) {
      document.body.style.overflow = '';
    }
    if (modalConFoco && typeof modalConFoco.focus === 'function') {
      modalConFoco.focus({ preventScroll: true });
      modalConFoco = null;
    }
  }

  function initModales() {
    // Apertura y cierre por delegación: alcanza con marcar el elemento, sin
    // escribir una función nueva por cada modal.
    document.addEventListener('click', (e) => {
      const abrir = e.target.closest('[data-modal-open]');
      if (abrir) {
        e.preventDefault();
        abrirModal(abrir.dataset.modalOpen);
        return;
      }
      const cerrar = e.target.closest('[data-modal-close]');
      if (cerrar) {
        e.preventDefault();
        cerrarModal(cerrar.dataset.modalClose);
        return;
      }
      // Clic en el fondo oscuro (fuera del panel) cierra el modal.
      if (e.target.matches('[role="dialog"]')) {
        cerrarModal(e.target.id);
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      const abierto = Array.from(document.querySelectorAll('[role="dialog"]:not(.hidden)')).pop();
      if (abierto) cerrarModal(abierto.id);
    });
  }

  // ── Confirm Modal ──
  let currentFormToSubmit = null;
  let currentConfirmCallback = null;

  function showConfirmModal(form, message, options = {}) {
    currentFormToSubmit = form;
    currentConfirmCallback = typeof options.onConfirm === 'function' ? options.onConfirm : null;
    const title = options.title || '¿Confirmar Acción?';
    const buttonText = options.buttonText || 'Confirmar';
    const type = options.type || 'danger';
    const icon = options.icon || (type === 'danger' ? 'warning' : 'check_circle');

    document.getElementById('confirmModalTitle').textContent = title;
    document.getElementById('confirmModalMessage').textContent = message;

    const actionBtn = document.getElementById('confirmModalAction');
    actionBtn.textContent = buttonText;

    const iconContainer = document.getElementById('confirmModalIconContainer');
    document.getElementById('confirmModalIcon').textContent = icon;

    actionBtn.className = 'flex-1 px-4 py-2 rounded-md text-white text-sm font-semibold transition-colors';
    iconContainer.className = 'size-12 rounded-md flex items-center justify-center';

    if (type === 'danger') {
      actionBtn.classList.add('bg-peligro-500', 'hover:bg-peligro-600');
      iconContainer.classList.add('bg-peligro-50', 'text-peligro-500');
    } else {
      actionBtn.classList.add('bg-primary-600', 'hover:bg-primary-700');
      iconContainer.classList.add('bg-primary-50', 'text-primary-600');
    }

    abrirModal('confirmModal');
  }

  function closeConfirmModal() {
    cerrarModal('confirmModal');
    currentFormToSubmit = null;
    currentConfirmCallback = null;
  }

  // ── Tema ──
  // El modo oscuro se retiró: duplicaba cada componente y no se usaba. Se quita
  // también la clase residual del documento, porque una sesión anterior pudo
  // haberla guardado en localStorage y dejaría la interfaz a medio pintar.
  function initTheme() {
    document.documentElement.classList.remove('dark');
    try {
      localStorage.removeItem('theme');
    } catch (e) {
      /* almacenamiento no disponible: no es crítico */
    }
  }

  // ── Sidebar ──
  function toggleSidebar() {
    const sidebar = document.getElementById('sidebarNav');
    const overlay = document.getElementById('sidebarOverlay');
    if (!sidebar || !overlay) return;
    const isOpen = !sidebar.classList.contains('-translate-x-full');
    if (isOpen) {
      sidebar.classList.add('-translate-x-full');
      overlay.classList.add('hidden');
    } else {
      sidebar.classList.remove('-translate-x-full');
      overlay.classList.remove('hidden');
    }
  }

  // ── Form Validation ──
  function setupFormValidation(formSelector) {
    const form = typeof formSelector === 'string' ? document.querySelector(formSelector) : formSelector;
    if (!form) return;

    const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');

    inputs.forEach(input => {
      input.addEventListener('blur', () => validateField(input));
      input.addEventListener('input', () => {
        if (input.classList.contains('field-invalid')) validateField(input);
      });
    });

    form.addEventListener('submit', (e) => {
      let valid = true;
      inputs.forEach(input => {
        if (!validateField(input)) valid = false;
      });
      if (!valid) {
        e.preventDefault();
        const firstInvalid = form.querySelector('.field-invalid');
        if (firstInvalid) firstInvalid.focus();
        showToast('Corrige los campos marcados en rojo antes de continuar', 'error');
      }
    });
  }

  function validateField(input) {
    const isValid = input.checkValidity();
    if (isValid) {
      input.classList.remove('field-invalid', 'border-red-300', 'border-red-700', 'bg-red-50', 'bg-red-900/10');
      input.classList.add('border-emerald-300', 'border-emerald-700');
      return true;
    }
    input.classList.remove('border-emerald-300', 'border-emerald-700');
    input.classList.add('field-invalid', 'border-red-300', 'border-red-700', 'bg-red-50', 'bg-red-900/10');
    return false;
  }

  // ── Get CSRF token from meta tag ──
  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }

  // ── CSRF Auto-inject into all forms ──
  function injectCSRF() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (!meta) return;
    const token = meta.getAttribute('content');
    document.querySelectorAll('form[method="POST"], form[method="post"]').forEach(form => {
      let input = form.querySelector('input[name="csrf_token"]');
      if (!input) {
        input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'csrf_token';
        form.appendChild(input);
      }
      input.value = token;
    });
  }

  // ── Safe DOM creation (replaces innerHTML for dynamic rows) ──
  function createMaterialRow() {
    const tr = document.createElement('tr');
    tr.className = 'hover:bg-slate-50/50 hover:bg-slate-800/30 transition-colors material-row';
    const td1 = document.createElement('td');
    td1.className = 'px-6 py-4 relative';
    const inp1 = document.createElement('input');
    inp1.name = 'material_et';
    inp1.className = 'et-input w-full bg-transparent border-none focus:ring-0 p-0 text-sm font-bold';
    inp1.placeholder = 'ET-001...';
    inp1.type = 'text';
    inp1.autocomplete = 'off';
    td1.appendChild(inp1);
    const pred = document.createElement('div');
    pred.className = 'predictions-container absolute left-0 right-0 top-full mt-1 bg-white bg-slate-800 border border-slate-200 border-slate-700 rounded-lg shadow-xl z-50 hidden max-h-48 overflow-y-auto';
    td1.appendChild(pred);
    tr.appendChild(td1);
    for (const [name, cls, placeholder] of [['material_desc', 'desc-input', 'Descripción...'], ['material_tipo', 'mat-input', 'Material...'], ['material_obs', '', 'Notas...']]) {
      const td = document.createElement('td');
      td.className = 'px-6 py-4';
      const inp = document.createElement('input');
      inp.name = name;
      inp.className = (cls ? cls + ' ' : '') + 'w-full bg-transparent border-none focus:ring-0 p-0 text-sm font-bold';
      inp.placeholder = placeholder;
      inp.type = 'text';
      td.appendChild(inp);
      tr.appendChild(td);
    }
    const tdAction = document.createElement('td');
    tdAction.className = 'px-6 py-4 text-center';
    const divAction = document.createElement('div');
    divAction.className = 'flex items-center justify-center gap-2 action-container';
    const delBtn = document.createElement('button');
    delBtn.type = 'button';
    delBtn.className = 'text-slate-300 hover:text-red-500 transition-colors';
    delBtn.innerHTML = '<span class="material-symbols-rounded text-sm">delete</span>';
    divAction.appendChild(delBtn);
    tdAction.appendChild(divAction);
    tr.appendChild(tdAction);
    return tr;
  }

  function createTeamRow() {
    const tr = document.createElement('tr');
    const fields = [
      { name: 'team_name', placeholder: 'Nombre...' },
      { name: 'team_role', placeholder: 'Cargo...' },
      { name: 'team_obs', placeholder: 'Observaciones...' },
    ];
    for (const f of fields) {
      const td = document.createElement('td');
      td.className = 'px-4 py-2';
      const inp = document.createElement('input');
      inp.name = f.name;
      inp.className = 'w-full bg-transparent border-none text-xs font-semibold focus:ring-0 p-0';
      inp.placeholder = f.placeholder;
      inp.type = 'text';
      td.appendChild(inp);
      tr.appendChild(td);
    }
    const tdAct = document.createElement('td');
    tdAct.className = 'px-4 py-2 text-center';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'p-2 text-slate-300 hover:text-red-500 transition-colors';
    btn.innerHTML = '<span class="material-symbols-rounded text-[20px]">delete_sweep</span>';
    tdAct.appendChild(btn);
    tr.appendChild(tdAct);
    return tr;
  }

  // ── Global confirmation bridge for [data-confirm] ──
  // Any <form data-confirm="...">, or any anchor/button carrying data-confirm,
  // is routed through the single global confirm modal. Previously each page
  // hand-rolled its own delete modal (or bound a per-class submit handler), and
  // four templates used data-confirm with nothing listening for it at all — so
  // those destructive actions fired with no confirmation.
  function initConfirmBridge() {
    const confirmMessageFor = (el) => el.getAttribute('data-confirm');

    // Form submission: intercept in the capture phase, before any inline
    // handler can submit the form.
    document.addEventListener('submit', (e) => {
      const form = e.target && e.target.closest ? e.target.closest('form[data-confirm]') : null;
      if (!form) return;
      // Skip when the submission was already approved by the modal.
      if (form.dataset.confirmed === 'true') return;
      e.preventDefault();
      e.stopPropagation();
      showConfirmModal(form, confirmMessageFor(form), { title: 'Confirmar acción' });
    }, true);

    // Anchor/button that is not the submitter of a data-confirm form.
    document.addEventListener('click', (e) => {
      const el = e.target && e.target.closest ? e.target.closest('[data-confirm]') : null;
      if (!el || el.tagName === 'FORM') return;
      if (el.tagName !== 'A' && el.tagName !== 'BUTTON') return;
      const form = el.form || (el.closest ? el.closest('form') : null);
      if (form && form.hasAttribute('data-confirm')) return; // the submit listener owns it
      e.preventDefault();
      showConfirmModal(null, confirmMessageFor(el), {
        title: 'Confirmar acción',
        onConfirm: () => {
          if (form) {
            form.dataset.confirmed = 'true';
            form.submit();
          } else if (el.tagName === 'A' && el.getAttribute('href')) {
            window.location.href = el.getAttribute('href');
          }
        },
      });
    });
  }

  // ── Keep the mobile nav trigger's expanded state in sync ──
  function initMobileNavState() {
    const btn = document.getElementById('btnMobileMenu');
    const sidebar = document.getElementById('sidebarNav');
    if (!btn || !sidebar) return;
    const sync = () => {
      btn.setAttribute(
        'aria-expanded',
        sidebar.classList.contains('-translate-x-full') ? 'false' : 'true'
      );
    };
    if (window.MutationObserver) {
      new MutationObserver(sync).observe(sidebar, { attributes: true, attributeFilter: ['class'] });
    }
    sync();
  }

  // ── Migrate inline onclicks to listeners ──
  function initEventDelegation() {
    // Close modal via Esc key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        const modal = document.getElementById('confirmModal');
        if (modal && !modal.classList.contains('hidden')) closeConfirmModal();
      }
    });

    // Confirm modal action
    document.getElementById('confirmModalAction')?.addEventListener('click', () => {
      if (currentConfirmCallback) {
        const cb = currentConfirmCallback;
        closeConfirmModal();
        cb();
        return;
      }
      if (currentFormToSubmit) {
        const form = currentFormToSubmit;
        // Mark as approved so the [data-confirm] capture listener lets this
        // submission through, then clear it so a later attempt asks again.
        form.dataset.confirmed = 'true';
        closeConfirmModal();
        form.submit();
        setTimeout(() => { delete form.dataset.confirmed; }, 0);
      }
    });

    // Close modal on overlay click
    document.getElementById('confirmModal')?.addEventListener('click', (e) => {
      if (e.target === e.currentTarget) closeConfirmModal();
    });

    // Sidebar overlay click
    document.getElementById('sidebarOverlay')?.addEventListener('click', toggleSidebar);

    // ── Event delegation for relevamiento.html ──
    document.addEventListener('change', (e) => {
      // Station logic triggers
      const stationTriggers = ['e1-centerline', 'e1-requires-sqt', 'e2-centerline', 'e2-requires-sqt', 'e3-requires-sqt'];
      const stationCheckbox = e.target.closest('input[type="checkbox"]');
      if (stationCheckbox && stationTriggers.includes(stationCheckbox.id)) {
        const num = stationCheckbox.id.match(/\d+/)?.[0];
        if (num) handleStationLogic(parseInt(num));
        return;
      }
      // Radio buttons for station criticidad
      const criticidadRadio = e.target.closest('input[type="radio"]');
      if (criticidadRadio && criticidadRadio.name?.startsWith('criticidad_e')) {
        const num = criticidadRadio.name.match(/\d+/)?.[0];
        if (num) handleStationLogic(parseInt(num));
        return;
      }
      // Station select triggers (e2-tipo-formado, e2-cierre-inferior, e3-tipo-cierre)
      const stationSelects = ['e2-tipo-formado', 'e2-cierre-inferior', 'e3-tipo-cierre'];
      const sel = e.target.closest('select');
      if (sel && stationSelects.includes(sel.id)) {
        const num = sel.id.match(/\d+/)?.[0];
        if (num) handleStationLogic(parseInt(num));
        return;
      }
      // Client cascading selects
      if (e.target.id === 'relev_cliente') { relevLoadPlants(e.target.value); return; }
      if (e.target.id === 'relev_planta') { relevLoadLines(e.target.value); return; }
      if (e.target.id === 'relev_linea') { relevLoadMachines(e.target.value); return; }
      // Material ET search on blur
      if (e.target.closest('.et-input')) { searchMaterial(e.target); return; }
    });

    document.addEventListener('input', (e) => {
      // ET input autocomplete
      if (e.target.closest('.et-input')) { handleEtInput(e.target); return; }
      // Temperature input for station 3
      if (e.target.id === 'e3_temp') { handleStationLogic(3); return; }
    });

    document.addEventListener('click', (e) => {
      // Tree toggle button
      const treeBtn = e.target.closest('button[data-tree-toggle]');
      if (treeBtn) { toggleTree(treeBtn.dataset.treeToggle); e.preventDefault(); return; }
      // Add material row
      if (e.target.closest('#add-material-row')) {
        const tbody = document.getElementById('materials-body');
        if (tbody) tbody.appendChild(createMaterialRow());
        return;
      }
      // Add team row
      const addTeamBtn = e.target.closest('#add-team-row');
      if (addTeamBtn) {
        const tbody = document.querySelector('#teamTable tbody');
        if (tbody) tbody.appendChild(createTeamRow());
        return;
      }
      // Remove row (material or team)
      const delBtn = e.target.closest('.material-row button, #teamTable button');
      if (delBtn) {
        const row = delBtn.closest('tr');
        if (row) {
          if (row.closest('#teamTable')) {
            row.remove();
          } else {
            const tbody = row.closest('tbody');
            if (tbody && tbody.rows.length > 1) {
              row.remove();
            } else {
              row.querySelectorAll('input').forEach(i => i.value = '');
            }
          }
        }
        return;
      }
      // Save to library
      const libBtn = e.target.closest('.add-to-lib-btn');
      if (libBtn) { saveToLibrary(libBtn.closest('tr')); return; }
      // Submit survey (Finalizar / Guardar Borrador)
      const submitBtn = e.target.closest('[data-submit-survey]');
      if (submitBtn) {
        const finalize = submitBtn.dataset.submitSurvey === 'true';
        if (finalize) {
          showConfirmModal(
            null,
            '¿Estás seguro de que deseas finalizar el relevamiento? Una vez finalizado no podrás editarlo sin autorización.',
            {
              title: 'Finalizar Relevamiento',
              buttonText: 'Sí, Finalizar',
              type: 'danger',
              icon: 'warning'
            }
          );
          // Override confirm action for this specific case
          const origAction = document.getElementById('confirmModalAction').onclick;
          document.getElementById('confirmModalAction').onclick = null;
          document.getElementById('confirmModalAction').addEventListener('click', function doFinalize() {
            document.getElementById('finalizeInput').value = 'true';
            document.getElementById('surveyForm').submit();
            closeConfirmModal();
            this.removeEventListener('click', doFinalize);
          });
        } else {
          document.getElementById('finalizeInput').value = 'false';
          document.getElementById('surveyForm').submit();
        }
        return;
      }
      // Preview button
      const previewBtn = e.target.closest('[data-preview-survey]');
      if (previewBtn) { openRelevamientoPreview(); return; }
      // Predictions mousedown
      const predItem = e.target.closest('[data-prediction]');
      if (predItem) {
        selectPrediction(predItem, predItem.dataset.et, predItem.dataset.desc, predItem.dataset.mat);
        return;
      }
    });
  }

  // ── Initialize ──
  document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initModales();
    initEventDelegation();
    initConfirmBridge();
    initMobileNavState();

    // Confirm modal cancel button (CSP-safe)
    document.getElementById('btnCancelConfirm')?.addEventListener('click', closeConfirmModal);
    document.getElementById('btnMobileMenu')?.addEventListener('click', toggleSidebar);
  });

  // ── Global exports ──
  window.showToast = showToast;
  window.showConfirmModal = showConfirmModal;
  window.closeConfirmModal = closeConfirmModal;
  window.abrirModal = abrirModal;
  window.cerrarModal = cerrarModal;
  window.toggleSidebar = toggleSidebar;
  window.escapeHtml = escapeHtml;
  window.setHTML = setHTML;
  window.setupFormValidation = setupFormValidation;
  window.validateField = validateField;
  window.getCsrfToken = getCsrfToken;
  window.injectCSRF = injectCSRF;
  window.createMaterialRow = createMaterialRow;
  window.createTeamRow = createTeamRow;
})();
