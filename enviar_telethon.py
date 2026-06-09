#!/usr/bin/env python3
"""
Script de envio por Telethon.
Envia alertas meteorologicas a numeros de telefono segun el nivel de categoria.
Reutiliza la logica de aemet.py y categorias.py sin modificarlas.
"""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
from telethon import TelegramClient

from aemet import AemetClient, PROVINCIAS
from categorias import CATEGORIA_MINIMA_ALERTA

load_dotenv()

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ── Credenciales Telethon ─────────────────────────────────────────────────────
API_ID       = int(os.environ["TELETHON_API_ID"])
API_HASH     = os.environ["TELETHON_API_HASH"]
PHONE_NUMBER = os.environ["TELETHON_PHONE"]

# ── AEMET ─────────────────────────────────────────────────────────────────────
AEMET_API_KEY    = os.environ["AEMET_API_KEY"]
PROVINCIA_CODIGO = os.environ.get("PROVINCIA_CODIGO", "11")
MUNICIPIO_CODIGO = os.environ.get("MUNICIPIO_CODIGO", "11012")
NOMBRE_PROV      = PROVINCIAS.get(PROVINCIA_CODIGO, PROVINCIA_CODIGO)

# ── Destinatarios por nivel de categoria ─────────────────────────────────────
# Rellenar con los numeros de telefono reales (con codigo de pais)
TELEFONOS_DEFAULT      = os.environ.get("TEL_DEFAULT", "").split(",")
TELEFONOS_CAPATACES    = os.environ.get("TEL_CAPATACES", "").split(",")
TELEFONOS_JEFES_UNIDAD = os.environ.get("TEL_JEFES_UNIDAD", "").split(",")
TELEFONOS_JEFE_COEX    = os.environ.get("TEL_JEFE_COEX", "").split(",")

TELEFONOS_BY_NIVEL = {
    0: TELEFONOS_DEFAULT,
    1: TELEFONOS_DEFAULT,
    2: TELEFONOS_CAPATACES,
    3: TELEFONOS_CAPATACES,
    4: TELEFONOS_JEFES_UNIDAD + TELEFONOS_JEFE_COEX,
    5: TELEFONOS_JEFE_COEX,
}

# ── URLs de recomendaciones (pendiente BBDD) ──────────────────────────────────
URLS_TEMPERATURA = {
    "CAT_V":   os.environ.get("URL_TEMP_V",   ""),
    "CAT_IV":  os.environ.get("URL_TEMP_IV",  ""),
    "CAT_III": os.environ.get("URL_TEMP_III", ""),
    "CAT_II":  os.environ.get("URL_TEMP_II",  ""),
    "CAT_I":   os.environ.get("URL_TEMP_I",   ""),
    "CAT_0":   "",
}

URLS_PRECIPITACION = {
    "CAT_V":   os.environ.get("URL_PRECIP_V",   ""),
    "CAT_IV":  os.environ.get("URL_PRECIP_IV",  ""),
    "CAT_III": os.environ.get("URL_PRECIP_III", ""),
    "CAT_II":  os.environ.get("URL_PRECIP_II",  ""),
    "CAT_I":   os.environ.get("URL_PRECIP_I",   ""),
    "CAT_0":   "",
}

URLS_VIENTO = {
    "CAT_V":   os.environ.get("URL_VIENTO_V",   ""),
    "CAT_IV":  os.environ.get("URL_VIENTO_IV",  ""),
    "CAT_III": os.environ.get("URL_VIENTO_III", ""),
    "CAT_II":  os.environ.get("URL_VIENTO_II",  ""),
    "CAT_I":   os.environ.get("URL_VIENTO_I",   ""),
    "CAT_0":   "",
}

# ── Descripciones por fenomeno y categoria ────────────────────────────────────
DESCRIPCIONES_TEMPERATURA = {
    5: "El Ingeniero Jefe-COEX, ante temperaturas extremadamente altas, paralizara todas las actuaciones previstas en exterior, salvo las vigilancias, comunicando esta circunstancia a los Jefes de las Unidades Productivas para que lo hagan extensivo a todo el personal. Riesgo muy alto.",
    4: "Los Jefes de las Unidades Productivas informaran a los Capataces (debiendo indicar que estos trasladen a los Jefes de Equipo, y a su vez estos al resto de operarios que tengan previsto realizar trabajo en exteriores) las recomendaciones especificas ante temperaturas muy altas, segun el documento de gestion preventiva en vigor, o incluso realizar los cambios funcionales y de ubicacion necesarios para la prevencion de golpe de calor e insolacion grave. Riesgo alto.",
    3: "Los Capataces informaran a los Jefes de Equipo (debiendo indicar que estos trasladen al resto de operarios que tengan previsto realizar trabajo en exteriores) de las recomendaciones concretas ante temperaturas altas, segun el documento de gestion preventiva en vigor, para la prevencion de sintomas de golpe de calor e insolacion. Riesgo medio.",
    2: "Los Capataces informaran a los operarios que tengan previsto realizar trabajo en exteriores de las recomendaciones adecuadas ante temperaturas medias, segun el documento de gestion preventiva en vigor, para la prevencion de insolacion. Riesgo bajo.",
    1: "Todo el personal sera informado que debe seguir las recomendaciones estandar ante temperaturas moderadas, segun el documento de gestion preventiva en vigor, para la prevencion de la fatiga por alta exposicion y actividad fisica. Riesgo muy bajo.",
}

DESCRIPCIONES_PRECIPITACION = {
    5: "El Ingeniero Jefe-COEX, ante lluvias de intensidad extremadamente alta, paralizara todas las actuaciones previstas en exterior, salvo las vigilancias, comunicando esta circunstancia a los Jefes de las Unidades Productivas para que lo hagan extensivo a todo el personal. Riesgo muy alto.",
    4: "Los Jefes de las Unidades Productivas informaran a los Capataces (debiendo indicar que estos trasladen a los Jefes de Equipo, y a su vez estos al resto de operarios que tengan previsto realizar trabajo en exteriores) de las recomendaciones concretas ante lluvias de intensidad muy alta, segun el documento de gestion preventiva en vigor, o incluso realizar los cambios funcionales y de ubicacion necesarios para la prevencion de accidentes en relacion a actuaciones a cielo abierto. Riesgo alto.",
    3: "Los Capataces informaran a los Jefes de Equipo (debiendo indicar que estos trasladen al resto de operarios que tengan previsto realizar trabajo en exteriores) de las recomendaciones concretas ante lluvias de intensidad alta, segun el documento de gestion preventiva en vigor, para la prevencion de accidentes en relacion a actuaciones a cielo abierto. Riesgo medio.",
    2: "Los Capataces informaran a los operarios que tengan previsto realizar trabajo en exteriores de las recomendaciones adecuadas ante lluvias de intensidad media, segun el documento de gestion preventiva en vigor, para la prevencion de accidentes en relacion a actuaciones a cielo abierto. Riesgo bajo.",
    1: "Todo el personal sera informado que debe seguir las recomendaciones estandar ante lluvias de intensidad moderada, segun el documento de gestion preventiva, para la prevencion de accidentes en relacion a actuaciones a cielo abierto. Riesgo muy bajo.",
}

DESCRIPCIONES_VIENTO = {
    5: "El Ingeniero Jefe-COEX, ante vientos de intensidad extremadamente alta, paralizara todas las actuaciones previstas en exterior, salvo las vigilancias, comunicando esta circunstancia a los Jefes de las Unidades Productivas para que lo hagan extensivo a todo el personal. Riesgo muy alto.",
    4: "Los Jefes de las Unidades Productivas informaran a los Capataces (debiendo indicar que estos trasladen a los Jefes de Equipo, y a su vez estos al resto de operarios que tengan previsto realizar trabajo en exteriores) de las recomendaciones concretas ante vientos de intensidad muy alta, segun el documento de gestion preventiva en vigor, o incluso realizar los cambios funcionales y de ubicacion necesarios para la prevencion de accidentes. Riesgo alto.",
    3: "Los Capataces informaran a los Jefes de Equipo (debiendo indicar que estos trasladen al resto de operarios que tengan previsto realizar trabajo en exteriores) de las recomendaciones concretas ante vientos de intensidad alta, segun el documento de gestion preventiva en vigor. Riesgo medio.",
    2: "Los Capataces informaran a los operarios que tengan previsto realizar trabajo en exteriores de las recomendaciones adecuadas ante vientos de intensidad media, segun el documento de gestion preventiva en vigor. Riesgo bajo.",
    1: "Todo el personal sera informado que debe seguir las recomendaciones estandar ante vientos moderados, segun el documento de gestion preventiva en vigor. Riesgo muy bajo.",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clave_cat(categoria: int) -> str:
    return f"CAT_{['0','I','II','III','IV','V'][categoria]}"


def _obtener_url(fenomeno: str, categoria: int) -> str:
    clave = _clave_cat(categoria)
    fenomeno_lower = fenomeno.lower()
    if "temperatura" in fenomeno_lower:
        return URLS_TEMPERATURA.get(clave, "")
    elif "viento" in fenomeno_lower:
        return URLS_VIENTO.get(clave, "")
    elif "precipit" in fenomeno_lower or "lluvia" in fenomeno_lower:
        return URLS_PRECIPITACION.get(clave, "")
    return ""


def _obtener_descripcion(fenomeno: str, categoria: int) -> str:
    fenomeno_lower = fenomeno.lower()
    if "temperatura" in fenomeno_lower:
        return DESCRIPCIONES_TEMPERATURA.get(categoria, "")
    elif "viento" in fenomeno_lower:
        return DESCRIPCIONES_VIENTO.get(categoria, "")
    elif "precipit" in fenomeno_lower or "lluvia" in fenomeno_lower:
        return DESCRIPCIONES_PRECIPITACION.get(categoria, "")
    return ""


def _destinatarios(nivel: int) -> list[str]:
    telefonos = TELEFONOS_BY_NIVEL.get(nivel, TELEFONOS_DEFAULT)
    return [t.strip() for t in telefonos if t.strip()]


def _construir_mensaje(alerta: dict) -> str:
    """Construye el mensaje para un destinatario dado una alerta."""
    interna  = alerta.get("interna", False)
    tipo     = "Alerta Interna" if interna else "Alerta AEMET"
    zona     = alerta.get("zona", NOMBRE_PROV)
    fenomeno = alerta.get("parametro", "")
    nivel    = alerta.get("nivelAviso", "")
    inicio   = alerta.get("inicio", "")
    fin      = alerta.get("fin", "")

    cat_obj  = alerta.get("cat")
    cat_num  = cat_obj.categoria if cat_obj else 0
    color    = cat_obj.color if cat_obj else ""

    descripcion = _obtener_descripcion(fenomeno, cat_num)
    url         = _obtener_url(fenomeno, cat_num)

    lineas = [
        f"{color} {tipo} — {zona}",
        f"{fenomeno} — {nivel.capitalize()}",
        f"🕐 {inicio} — {fin}",
        "",
        descripcion,
    ]

    if url:
        lineas += ["", f"📋 Recomendaciones: {url}"]

    return "\n".join(lineas)


# ── Envio por Telethon ────────────────────────────────────────────────────────

async def enviar_alertas_telethon(alertas: list[dict], nivel_max: int) -> None:
    """Envia cada alerta a los destinatarios correspondientes via Telethon."""

    destinatarios = _destinatarios(nivel_max)
    if not destinatarios:
        logger.warning(f"No hay destinatarios configurados para nivel {nivel_max}.")
        return

    async with TelegramClient("sesion_aemet", API_ID, API_HASH) as client:
        await client.start(phone=PHONE_NUMBER)

        for alerta in alertas:
            mensaje = _construir_mensaje(alerta)
            for telefono in destinatarios:
                try:
                    await client.send_message(telefono, mensaje)
                    logger.info(f"Mensaje enviado a {telefono} — {alerta.get('parametro','')}")
                except Exception as e:
                    logger.error(f"Error enviando a {telefono}: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    client_aemet = AemetClient(AEMET_API_KEY)

    _, maximos, filas = await client_aemet.obtener_tabla_y_maximos(
        MUNICIPIO_CODIGO, NOMBRE_PROV
    )

    if not maximos:
        logger.error("No se pudieron obtener datos de AEMET.")
        return

    from categorias import calcular_categoria, ResultadoCategoria
    hay_cap, alertas_cap = await client_aemet.obtener_alertas_cap(PROVINCIA_CODIGO)

    cat = calcular_categoria(
        sens_termica_max = maximos.get("st_max"),
        temperatura_max  = maximos.get("temp_max"),
        viento_max       = maximos.get("viento_max"),
        precip_max_hora  = maximos.get("precip_max"),
    )

    if hay_cap:
        alertas   = alertas_cap
        nivel_max = 3  # Minimo amarillo para alertas CAP
        # Intentar obtener el nivel real del primer aviso CAP
        for a in alertas_cap:
            nivel_str = a.get("nivelAviso", "").lower()
            if "rojo" in nivel_str:
                nivel_max = 5; break
            elif "naranja" in nivel_str:
                nivel_max = 4; break
            elif "amarillo" in nivel_str:
                nivel_max = 3; break
    elif cat.debe_alertar:
        alertas   = client_aemet._alertas_internas(filas, NOMBRE_PROV)
        nivel_max = cat.categoria
    else:
        logger.info("Sin alertas que enviar por Telethon.")
        return

    await enviar_alertas_telethon(alertas, nivel_max)


if __name__ == "__main__":
    asyncio.run(main())
