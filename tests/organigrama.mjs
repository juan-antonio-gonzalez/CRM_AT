// Pruebas de la lógica del organigrama.
//
//   node tests/organigrama.mjs
//
// El organigrama arma el árbol en el navegador a partir del equipo del cliente
// (guardado como JSON). Estas pruebas ejecutan el JavaScript real de la
// plantilla con un DOM mínimo, para cubrir los casos que rompían la vista:
// nombres repetidos, ciclos, jefes de otro sector y datos con HTML.
import { readFileSync } from 'node:fs';

import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

// Prueba directamente el JavaScript de la plantilla, que es el que corre en el
// navegador. Se ejecuta desde la raíz del repo o desde tests/.
const AQUI = dirname(fileURLToPath(import.meta.url));
const RAIZ = AQUI.endsWith('tests') ? dirname(AQUI) : AQUI;
const ruta = join(RAIZ, 'templates/organigrama.html');

function extraer(ruta) {
    const html = readFileSync(ruta, 'utf8');
    const m = html.match(/<script nonce="\{\{ request\.state\.script_nonce \}\}">([\s\S]*?)<\/script>/);
    // El borrador es JavaScript suelto; la plantilla tiene el bloque <script>.
    return m ? m[1] : html;
}

const contenedores = {};
const documentoFalso = {
    getElementById: (id) => {
        if (!contenedores[id]) {
            contenedores[id] = {
                innerHTML: '',
                classList: { add() {}, remove() {} },
                addEventListener() {},
            };
        }
        return contenedores[id];
    },
};

// Se concatena con + y no con un template literal: el código probado tiene sus
// propios acentos graves y se rompería.
const epilogo = [
    'return {',
    '  renderOrgChart, getInitials,',
    '  construirArbol: typeof construirArbol === "function" ? construirArbol : undefined,',
    '  buildTree: typeof buildTree === "function" ? buildTree : undefined,',
    '  renderRama: typeof renderRama === "function" ? renderRama : undefined,',
    '  renderTree: typeof renderTree === "function" ? renderTree : undefined',
    '};',
].join('\n');
const fabrica = new Function('document', extraer(ruta) + '\n' + epilogo);
const F = fabrica(documentoFalso);
const construir = F.construirArbol || F.buildTree;
const render = F.renderRama || F.renderTree;

let fallos = 0;
function chk(etiqueta, ok, detalle = '') {
    console.log(`  ${ok ? 'OK   ' : 'FALLA'} ${etiqueta}${detalle ? ' -> ' + detalle : ''}`);
    if (!ok) fallos++;
}
function nombres(nodos, acc = []) {
    for (const n of nodos || []) { acc.push(n.name); nombres(n.children, acc); }
    return acc;
}
// Detecta identidades repetidas: con el map por nombre, una persona se perdía.
function identidades(nodos, acc = []) {
    for (const n of nodos || []) { acc.push(n); identidades(n.children, acc); }
    return acc;
}

console.log(`Probando: ${ruta}`);
console.log();

console.log('=== 1. Dos personas con el mismo nombre y sector ===');
{
    const team = [
        { name: 'Juan Pérez', role: 'Gerente', reports_to: '', sector: 'PRODUCCIÓN' },
        { name: 'Juan Pérez', role: 'Operario', reports_to: '', sector: 'PRODUCCIÓN' },
    ];
    const arbol = construir(team);
    const nodos = identidades(arbol.raices);
    chk('se muestran los dos, sin descartar a ninguno', nodos.length === 2,
        `se muestran ${nodos.length}`);
    chk('con cargos distintos', new Set(nodos.map(n => n.role)).size === 2);
    chk('se avisa que el nombre está repetido', (arbol.avisos || []).length > 0);
}

console.log();
console.log('=== 2. Jefe del mismo sector ===');
{
    const team = [
        { name: 'Jefa', role: 'Gerente', reports_to: '', sector: 'S' },
        { name: 'Empleado', role: 'Op', reports_to: 'Jefa', sector: 'S' },
        { name: 'Ayudante', role: 'Op', reports_to: 'Empleado', sector: 'S' },
    ];
    const arbol = construir(team);
    chk('un solo árbol', arbol.raices.length === 1, `${arbol.raices.length} raíces`);
    chk('el jefe es la raíz', arbol.raices[0].name === 'Jefa');
    chk('cuelga en dos niveles', arbol.raices[0].children[0].children[0].name === 'Ayudante');
    chk('se muestran los tres', identidades(arbol.raices).length === 3);
}

console.log();
console.log('=== 3. Jefe de otro sector ===');
{
    const team = [
        { name: 'Ana Jefa', role: 'Gerente', reports_to: '', sector: 'PRODUCCIÓN' },
        { name: 'Luis', role: 'Operario', reports_to: 'Ana Jefa', sector: 'MANTENIMIENTO' },
    ];
    const arbol = construir(team);
    const todos = identidades(arbol.raices);
    chk('nadie se pierde', todos.length === 2, `se muestran ${todos.length}`);
    const luis = todos.find(n => n.name === 'Luis');
    chk('Luis cuelga de su jefe real', luis && luis.parent === arbol.raices[0].id);
    chk('se muestra la dependencia entre sectores',
        luis && /PRODUCCIÓN/.test(luis.aviso), luis ? luis.aviso : '');
}

console.log();
console.log('=== 4. Ciclo entre dos personas ===');
{
    const team = [
        { name: 'A', role: '', reports_to: 'B', sector: 'S' },
        { name: 'B', role: '', reports_to: 'A', sector: 'S' },
    ];
    const arbol = construir(team);
    const todos = identidades(arbol.raices);
    chk('el organigrama NO queda vacío', arbol.raices.length > 0,
        `${arbol.raices.length} raíces`);
    chk('se muestran los dos', todos.length === 2, `se muestran ${todos.length}`);
    chk('se avisa del ciclo', (arbol.avisos || []).some(a => /circular/i.test(a)),
        (arbol.avisos || []).join(' | '));
    let html = '';
    try { html = render(arbol.raices); } catch (e) { html = 'EXCEPCION: ' + e.message; }
    chk('el render no se cuelga', !html.startsWith('EXCEPCION'), html.slice(0, 60));
}

console.log();
console.log('=== 5. Una persona que se reporta a sí misma ===');
{
    const team = [{ name: 'Solo', role: '', reports_to: 'Solo', sector: 'S' }];
    const arbol = construir(team);
    chk('queda como raíz', arbol.raices.length === 1 && arbol.raices[0].name === 'Solo');
    chk('se avisa', /sí mismo/i.test(arbol.raices[0].aviso || ''), arbol.raices[0].aviso);
    let html = '';
    try { html = render(arbol.raices); } catch (e) { html = 'EXCEPCION: ' + e.message; }
    chk('el render no se cuelga', !html.startsWith('EXCEPCION'));
}

console.log();
console.log('=== 6. Espacios y mayúsculas en reports_to ===');
{
    const team = [
        { name: 'Jefa', role: '', reports_to: '', sector: 'S' },
        { name: 'Empleado', role: '', reports_to: '  jefa  ', sector: 'S' },
    ];
    const arbol = construir(team);
    chk('reconoce al jefe', arbol.raices.length === 1,
        `${arbol.raices.length} raíz(ces): ${nombres(arbol.raices).join(', ')}`);
}

console.log();
console.log('=== 7. Jefe inexistente ===');
{
    const team = [{ name: 'Huerfano', role: '', reports_to: 'Nadie', sector: 'S' }];
    const arbol = construir(team);
    chk('queda como raíz', arbol.raices.length === 1);
    chk('se avisa que no se encontró', /No se encontró/i.test(arbol.raices[0].aviso || ''),
        arbol.raices[0].aviso);
}

console.log();
console.log('=== 8. Escapado de HTML ===');
{
    const team = [{ name: '<img src=x onerror=alert(1)>', role: '<b>rol</b>',
                    phone: '"><script>alert(2)</script>', reports_to: '', sector: '<i>S</i>' }];
    const arbol = construir(team);
    const html = render(arbol.raices);
    chk('no se inyecta HTML en el nombre', !html.includes('<img src=x'));
    chk('no se inyecta HTML en el cargo', !html.includes('<b>rol</b>'));
    chk('no se inyecta HTML en el teléfono', !html.includes('<script>'));
    chk('el texto igual se ve', html.includes('&lt;img src=x'));
}

console.log();
console.log('=== 9. Iniciales ===');
{
    chk('nombre y apellido', F.getInitials('Ana Gómez') === 'AG', F.getInitials('Ana Gómez'));
    chk('un solo nombre', F.getInitials('Ana') === 'A', F.getInitials('Ana'));
    chk('vacío', F.getInitials('') === '??', F.getInitials(''));
    chk('espacios sobrantes', F.getInitials('  ana   gomez  ') === 'AG', F.getInitials('  ana   gomez  '));
    chk('con acentos', F.getInitials('Ángel Íñiguez') === 'ÁÍ', F.getInitials('Ángel Íñiguez'));
}

console.log();
console.log('=== 10. Equipo vacío o inválido ===');
{
    for (const caso of [[], null, undefined, [{ name: '   ' }]]) {
        const arbol = construir(caso);
        chk(`no rompe con ${JSON.stringify(caso)}`, Array.isArray(arbol.raices),
            `${arbol.raices.length} raíces`);
    }
}

console.log();
console.log('=== 11. renderOrgChart completo ===');
{
    const team = [
        { name: 'Jefa', role: 'Gerente', reports_to: '', sector: 'PRODUCCIÓN' },
        { name: 'Operario', role: 'Op', reports_to: 'Jefa', sector: 'PRODUCCIÓN' },
        { name: 'Técnico', role: 'T', reports_to: '', sector: 'MANTENIMIENTO' },
    ];
    let err = '';
    try { F.renderOrgChart(team); } catch (e) { err = e.message; }
    const html = contenedores['orgContent'] ? contenedores['orgContent'].innerHTML : '';
    chk('no lanza excepción', !err, err);
    chk('agrupa por sector', html.includes('PRODUCCIÓN') && html.includes('MANTENIMIENTO'));
    chk('cuenta los miembros por sector', html.includes('2 miembros') && html.includes('1 miembro'));
    chk('muestra los nombres', html.includes('Jefa') && html.includes('Operario'));
    chk('la jerarquía se dibuja con lista anidada', html.includes('<ul') && html.includes('<li>'));
    chk('sin padding acumulado en línea', !/padding-left:\s*\d+px/.test(html));

    F.renderOrgChart([]);
    chk('equipo vacío muestra el mensaje', /no tiene equipo registrado/i.test(
        contenedores['orgContent'].innerHTML));
}

console.log();
console.log(fallos ? `RESULTADO: ${fallos} fallo(s)` : 'RESULTADO: todo bien');
process.exit(fallos ? 1 : 0);
