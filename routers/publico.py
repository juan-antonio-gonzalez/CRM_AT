"""Las páginas que se sirven sin sesión, para que el dominio se entienda.

Por qué existe
--------------
La aplicación tenía **una sola** página pública: el formulario de login. Todo lo
demás redirigía ahí. Visto desde afuera —y sobre todo desde el robot de un filtro
web corporativo— el dominio era un dominio nuevo cuya única página es un login.

Eso es exactamente el perfil que los filtros clasifican como «sin categorizar», y
varios directamente como sospechoso, porque es la forma que tienen las páginas de
phishing. El resultado: la aplicación queda bloqueada en las redes corporativas
aunque no tenga nada de malo.

Estas tres respuestas —la presentación, `robots.txt` y `sitemap.xml`— son las
señales mínimas de un sitio legítimo. No destraban por sí solas un bloqueo
explícito, pero le dan a quien tenga que categorizarlo algo con qué hacerlo.
"""

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, Response
from templating import templates

router = APIRouter(tags=["publico"])

# Lo que el sitio es, en una línea. Se repite en el `robots.txt` y en el JSON-LD
# de la presentación: los tres tienen que decir lo mismo.
DESCRIPCION = ("CRM de asistencia técnica industrial: clientes, visitas técnicas, "
               "máquinas, productos, relevamientos, minutas, KPIs y control de "
               "asignaciones AT.")


@router.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
async def robots(request: Request):
    """Permite el rastreo y apunta al sitemap.

    Un `robots.txt` que **prohíbe** el rastreo dejaría al filtro sin forma de
    categorizar el sitio, que es lo contrario de lo que hace falta acá. La
    aplicación no tiene nada que esconder: lo que hay detrás del login no se indexa
    porque no hay enlaces que lleguen sin sesión, no porque se lo prohíba.
    """
    base = str(request.base_url).rstrip("/")
    return PlainTextResponse(
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        f"# {DESCRIPCION}\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap(request: Request):
    """Las dos direcciones públicas: la presentación y el acceso."""
    base = str(request.base_url).rstrip("/")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{base}/</loc><changefreq>monthly</changefreq>"
        "<priority>1.0</priority></url>\n"
        f"  <url><loc>{base}/auth/login</loc><changefreq>monthly</changefreq>"
        "<priority>0.5</priority></url>\n"
        "</urlset>\n"
    )
    return Response(content=xml, media_type="application/xml")
