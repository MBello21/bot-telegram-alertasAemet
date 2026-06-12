#!/usr/bin/env python3
"""
Script de envio por Telethon.
- Alertas CAP oficiales: siempre se envian, agrupadas por nivel
- Alertas internas: se evaluan todos los parametros no cubiertos por CAP
  y se envian si superan el umbral de bloques consecutivos
"""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
from telethon import TelegramClient

from aemet import AemetClient, PROVINCIAS, NIVEL_CAP_A_CAT, _fenomeno_a_columnas
from categorias import (
    CATEGORIA_MINIMA_ALERTA, NOMBRES, COLORES,
    _cat_temperatura, _cat_viento, _cat_precipitacion, calcular_categoria
)

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

# ── Destinatarios por nivel ───────────────────────────────────────────────────
def _split(v): return [t.strip() for t in v.split(",") if t.strip()]

TEL_DEFAULT      = _split(os.environ.get("TEL_DEFAULT", ""))
TEL_CAPATACES    = _split(os.environ.get("TEL_CAPATACES", ""))
TEL_JEFES_UNIDAD = _split(os.environ.get("TEL_JEFES_UNIDAD", ""))
TEL_JEFE_COEX    = _split(os.environ.get("TEL_JEFE_COEX", ""))

DESTINATARIOS_POR_CAT = {
    2: TEL_DEFAULT,
    3: list(set(TEL_DEFAULT + TEL_CAPATACES)),
    4: list(set(TEL_DEFAULT + TEL_CAPATACES + TEL_JEFES_UNIDAD)),
    5: list(set(TEL_DEFAULT + TEL_CAPATACES + TEL_JEFES_UNIDAD + TEL_JEFE_COEX)),
}

# ── Umbral de bloques consecutivos para alertas internas ─────────────────────
BLOQUES_MINIMOS = {2: 3, 3: 2, 4: 1, 5: 1}

# ── URLs de recomendaciones ───────────────────────────────────────────────────
URLS = {
    "temperatura": {
        1: os.environ.get("URL_TEMP_I",   ""),
        2: os.environ.get("URL_TEMP_II",  ""),
        3: os.environ.get("URL_TEMP_III", ""),
        4: os.environ.get("URL_TEMP_IV",  ""),
        5: os.environ.get("URL_TEMP_V",   ""),
    },
    "viento": {
        1: os.environ.get("URL_VIENTO_I",   ""),
        2: os.environ.get("URL_VIENTO_II",  ""),
        3: os.environ.get("URL_VIENTO_III", ""),
        4: os.environ.get("URL_VIENTO_IV",  ""),
        5: os.environ.get("URL_VIENTO_V",   ""),
    },
    "precipitacion": {
        1: os.environ.get("URL_PRECIP_I",   ""),
        2: os.environ.get("URL_PRECIP_II",  ""),
        3: os.environ.get("URL_PRECIP_III", ""),
        4: os.environ.get("URL_PRECIP_IV",  ""),
        5: os.environ.get("URL_PRECIP_V",   ""),
    },
}

DESCRIPCIONES = {
    "temperatura": {
        5: "El Ingeniero Jefe-COEX, ante temperaturas extremadamente altas, paralizara todas las actuaciones previstas en exterior, salvo las vigilancias, comunicando esta circunstancia a los Jefes de las Unidades Productivas.",
        4: "Los Jefes de las Unidades Productivas informaran a los Capataces de las recomendaciones especificas ante temperaturas muy altas, segun el documento de gestion preventiva en vigor.",
        3: "Los Capataces informaran a los Jefes de Equipo de las recomendaciones ante temperaturas altas, segun el documento de gestion preventiva, para la prevencion de golpe de calor e insolacion.",
        2: "Los Capataces informaran a los operarios de las recomendaciones adecuadas ante temperaturas medias, segun el documento de gestion preventiva, para la prevencion de insolacion.",
        1: "Todo el personal seguira las recomendaciones estandar ante temperaturas moderadas para la prevencion de fatiga por alta exposicion.",
    },
    "viento": {
        5: "El Ingeniero Jefe-COEX, ante vientos de intensidad extremadamente alta, paralizara todas las actuaciones previstas en exterior, salvo las vigilancias, comunicando esta circunstancia a los Jefes de las Unidades Productivas.",
        4: "Los Jefes de las Unidades Productivas informaran a los Capataces de las recomendaciones ante vientos de intensidad muy alta, segun el documento de gestion preventiva.",
        3: "Los Capataces informaran a los Jefes de Equipo de las recomendaciones ante vientos de intensidad alta, segun el documento de gestion preventiva en vigor.",
        2: "Los Capataces informaran a los operarios de las recomendaciones adecuadas ante vientos de intensidad media, segun el documento de gestion preventiva en vigor.",
        1: "Todo el personal seguira las recomendaciones estandar ante vientos moderados, segun el documento de gestion preventiva en vigor.",
    },
    "precipitacion": {
        5: "El Ingeniero Jefe-COEX, ante lluvias de intensidad extremadamente alta, paralizara todas las actuaciones previstas en exterior, salvo las vigilancias, comunicando esta circunstancia a los Jefes de las Unidades Productivas.",
        4: "Los Jefes de las Unidades Productivas informaran a los Capataces de las recomendaciones ante lluvias de intensidad muy alta, segun el documento de gestion preventiva.",
        3: "Los Capataces informaran a los Jefes de Equipo de las recomendaciones ante lluvias de intensidad alta, segun el documento de gestion preventiva en vigor.",
        2: "Los Capataces informaran a los operarios de las recomendaciones adecuadas ante lluvias de intensidad media, segun el documento de gestion preventiva en vigor.",
        1: "Todo el personal seguira las recomendaciones estandar ante lluvias moderadas, segun el documento de gestion preventiva en vigor.",
    },
}

NIVEL_EMOJI = {"amarillo": "🟡", "naranja": "🟠", "rojo": "🔴", "verde": "🟢"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tipo_fenomeno(parametro: str) -> str:
    p = parametro.lower()
    if any(x in p for x in ["temperatura", "calor", "frio"]):
        return "temperatura"
    if any(x in p for x in ["lluvia", "precipit", "nieve", "granizo"]):
        return "precipitacion"
    return "viento"


def _bloques_consecutivos(filas, cat_min: int, tipo: str) -> int:
    max_c, c = 0, 0
    for f in filas:
        if tipo == "temperatura":
            cat = _cat_temperatura(f.temp)
        elif tipo == "precipitacion":
            cat = _cat_precipitacion(f.precip)
        else:
            cat = _cat_viento(f.viento)
        if cat >= cat_min:
            c += 1
            max_c = max(max_c, c)
        else:
            c = 0
    return max_c


def _cat_nombre_a_nivel(cat: int) -> str:
    mapa = {1: "verde", 2: "amarillo", 3: "amarillo", 4: "naranja", 5: "rojo"}
    return mapa.get(cat, "amarillo")


# ── Construccion de mensajes ──────────────────────────────────────────────────

def _construir_mensajes_cap(alertas_cap: list, nombre_prov: str) -> dict[int, str]:
    """
    Agrupa alertas CAP por nivel. Un mensaje por nivel con todos los bloques,
    actuacion y URL al final.
    """
    # Agrupar bloques por nivel y tipo
    por_nivel: dict[int, dict] = {}

    for a in alertas_cap:
        nivel    = a.get("nivelAviso", "").lower()
        fenomeno = a.get("parametro", "")
        inicio   = a.get("inicio", "")
        fin      = a.get("fin", "")
        cat      = NIVEL_CAP_A_CAT.get(nivel, 3)
        tipo     = _tipo_fenomeno(fenomeno)

        if cat not in por_nivel:
            por_nivel[cat] = {
                "nivel":    nivel,
                "tipo":     tipo,
                "fenomeno": fenomeno,
                "bloques":  [],
            }
        por_nivel[cat]["bloques"].append({
            "fenomeno": fenomeno,
            "nivel":    nivel,
            "inicio":   inicio,
            "fin":      fin,
        })

    # Construir mensaje por nivel
    mensajes: dict[int, str] = {}
    for cat, info in por_nivel.items():
        nivel    = info["nivel"]
        tipo     = info["tipo"]
        en       = NIVEL_EMOJI.get(nivel, "⚠️")
        desc     = DESCRIPCIONES.get(tipo, {}).get(cat, "")
        url      = URLS.get(tipo, {}).get(cat, "")

        lineas = [
            f"{en} *ALERTA OFICIAL AEMET — {nombre_prov}*",
            f"━━━━━━━━━━━━━━━━━━━━━━━━",
        ]

        for i, b in enumerate(info["bloques"]):
            if i > 0:
                lineas.append("─────────────────────")
            en_b = NIVEL_EMOJI.get(b["nivel"], "⚠️")
            lineas += [
                f"📌 *Fenomeno:* {b['fenomeno']} — {b['nivel'].capitalize()}",
                f"🕐 *Periodo:* {b['inicio']} — {b['fin']}",
            ]

        lineas += [
            "━━━━━━━━━━━━━━━━━━━━━━━━",
            "📝 *Actuacion requerida:*",
            desc,
        ]
        if url:
            lineas += ["", f"🔗 *Recomendaciones:* {url}"]

        mensajes[cat] = "\n".join(lineas)

    return mensajes


def _construir_mensajes_internos(alertas_internas: list, filas, nombre_prov: str) -> dict[int, str]:
    """
    Agrupa alertas internas por nivel. Verifica bloques consecutivos.
    Un mensaje por nivel con todos los bloques, actuacion y URL al final.
    """
    por_nivel: dict[int, dict] = {}

    for a in alertas_internas:
        fenomeno = a.get("parametro", "")
        tipo     = _tipo_fenomeno(fenomeno)
        cat_obj  = a.get("cat")
        cat      = cat_obj.categoria if cat_obj else 0
        inicio   = a.get("inicio", "")
        fin      = a.get("fin", "")

        if cat < CATEGORIA_MINIMA_ALERTA:
            continue

        bloques = _bloques_consecutivos(filas, cat, tipo)
        minimo  = BLOQUES_MINIMOS.get(cat, 1)
        if bloques < minimo:
            logger.info(f"Interna {fenomeno} CAT.{cat}: {bloques}h < {minimo} requeridas, omitiendo.")
            continue

        if cat not in por_nivel:
            por_nivel[cat] = {
                "tipo":    tipo,
                "bloques": [],
            }
        por_nivel[cat]["bloques"].append({
            "fenomeno": fenomeno,
            "cat":      cat,
            "inicio":   inicio,
            "fin":      fin,
            "bloques":  bloques,
        })

    mensajes: dict[int, str] = {}
    for cat, info in por_nivel.items():
        tipo  = info["tipo"]
        nivel = _cat_nombre_a_nivel(cat)
        en    = NIVEL_EMOJI.get(nivel, "⚠️")
        desc  = DESCRIPCIONES.get(tipo, {}).get(cat, "")
        url   = URLS.get(tipo, {}).get(cat, "")

        lineas = [
            f"{en} *ALERTA INTERNA — {nombre_prov}*",
            f"━━━━━━━━━━━━━━━━━━━━━━━━",
        ]

        for i, b in enumerate(info["bloques"]):
            if i > 0:
                lineas.append("─────────────────────")
            lineas += [
                f"📌 *Fenomeno:* {b['fenomeno']} — {NOMBRES[b['cat']]}",
                f"🕐 *Periodo:* {b['inicio']} — {b['fin']}",
                f"⏱ *Horas consecutivas:* {b['bloques']}h",
            ]

        lineas += [
            "━━━━━━━━━━━━━━━━━━━━━━━━",
            "📝 *Actuacion requerida:*",
            desc,
        ]
        if url:
            lineas += ["", f"🔗 *Recomendaciones:* {url}"]

        mensajes[cat] = "\n".join(lineas)

    return mensajes


# ── Envio ─────────────────────────────────────────────────────────────────────

async def enviar_mensajes(mensajes_por_cat: dict[int, str]) -> None:
    if not mensajes_por_cat:
        logger.info("Sin mensajes que enviar por Telethon.")
        return

    async with TelegramClient("sesion_aemet", API_ID, API_HASH) as client:
        await client.start(phone=PHONE_NUMBER)
        for cat, mensaje in mensajes_por_cat.items():
            telefonos = DESTINATARIOS_POR_CAT.get(cat, TEL_DEFAULT)
            for tel in telefonos:
                try:
                    await client.send_message(tel, mensaje, parse_mode="md")
                    logger.info(f"Enviado a {tel} — CAT.{cat}")
                except Exception as e:
                    logger.error(f"Error enviando a {tel}: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    client_aemet = AemetClient(AEMET_API_KEY)

    (_, maximos, filas), (hay_cap, alertas_cap) = await asyncio.gather(
        client_aemet.obtener_tabla_y_maximos(MUNICIPIO_CODIGO, NOMBRE_PROV),
        client_aemet.obtener_alertas_cap(PROVINCIA_CODIGO),
    )

    mensajes_finales: dict[int, str] = {}

    if hay_cap:
        # 1. Mensajes por alertas CAP oficiales
        msgs_cap = _construir_mensajes_cap(alertas_cap, NOMBRE_PROV)
        mensajes_finales.update(msgs_cap)

        # 2. Evaluar internas para parametros NO cubiertos por CAP
        tipos_cap = {_tipo_fenomeno(a.get("parametro","")) for a in alertas_cap}
        alertas_internas = client_aemet._alertas_internas(filas, NOMBRE_PROV)
        alertas_no_cap   = [a for a in alertas_internas
                            if _tipo_fenomeno(a.get("parametro","")) not in tipos_cap]

        if alertas_no_cap:
            msgs_int = _construir_mensajes_internos(alertas_no_cap, filas, NOMBRE_PROV)
            for cat, msg in msgs_int.items():
                if cat not in mensajes_finales:
                    mensajes_finales[cat] = msg
                else:
                    mensajes_finales[cat] += "\n\n" + msg
    else:
        # 3. Solo alertas internas
        if not maximos:
            logger.info("Sin datos de AEMET.")
            return
        cat_global = calcular_categoria(
            sens_termica_max = maximos.get("st_max"),
            temperatura_max  = maximos.get("temp_max"),
            viento_max       = maximos.get("viento_max"),
            precip_max_hora  = maximos.get("precip_max"),
        )
        if not cat_global.debe_alertar:
            logger.info("Sin alertas que enviar.")
            return

        alertas_internas = client_aemet._alertas_internas(filas, NOMBRE_PROV)
        msgs_int = _construir_mensajes_internos(alertas_internas, filas, NOMBRE_PROV)
        mensajes_finales.update(msgs_int)

    await enviar_mensajes(mensajes_finales)


if __name__ == "__main__":
    asyncio.run(main())
