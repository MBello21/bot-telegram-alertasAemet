#!/usr/bin/env python3
"""
Bot interactivo de Telegram.
/alertas  -> solo texto de alertas
/tiempo   -> solo foto con la tabla
/info     -> configuracion
"""

import logging
import io
import os
import sys

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from aemet import AemetClient, PROVINCIAS
from categorias import CATEGORIA_MINIMA_ALERTA, NOMBRES, COLORES

load_dotenv()

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
CHAT_ID          = os.environ["CHAT_ID"]
AEMET_API_KEY    = os.environ["AEMET_API_KEY"]
PROVINCIA_CODIGO = os.environ.get("PROVINCIA_CODIGO", "11")
MUNICIPIO_CODIGO = os.environ.get("MUNICIPIO_CODIGO", "11012")
NOMBRE_PROV      = PROVINCIAS.get(PROVINCIA_CODIGO, PROVINCIA_CODIGO)


def _client() -> AemetClient:
    return AemetClient(AEMET_API_KEY)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 *Bot de alertas AEMET*\n\n"
        "• /alertas    — Alertas activas ahora\n"
        "• /tiempo     — Tabla de prediccion hoy\n"
        "• /prediccion — Prediccion 4 dias\n"
        "• /info       — Configuracion del bot\n\n"
        "Las alertas oficiales de AEMET prevalecen siempre.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_alertas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Consultando AEMET...")
    _, mensaje = await _client().obtener_solo_alertas(
        MUNICIPIO_CODIGO, PROVINCIA_CODIGO
    )
    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)


async def cmd_tiempo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Consultando prediccion...")
    imagen = await _client().obtener_imagen_tiempo(MUNICIPIO_CODIGO, NOMBRE_PROV)
    if imagen:
        await update.message.reply_photo(photo=io.BytesIO(imagen))
    else:
        await update.message.reply_text("No se pudo obtener la prediccion.")


async def cmd_prediccion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Consultando prediccion 4 dias...")
    imagen = await _client().obtener_imagen_prediccion(MUNICIPIO_CODIGO, PROVINCIA_CODIGO)
    if imagen:
        await update.message.reply_photo(photo=io.BytesIO(imagen))
    else:
        await update.message.reply_text("No se pudo obtener la prediccion.")


async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "ℹ️ *Configuracion del bot*\n\n"
        f"• Provincia: *{NOMBRE_PROV}* (codigo {PROVINCIA_CODIGO})\n"
        f"• Municipio: codigo {MUNICIPIO_CODIGO}\n"
        f"• Umbral alerta interna: *{NOMBRES[CATEGORIA_MINIMA_ALERTA]}* "
        f"{COLORES[CATEGORIA_MINIMA_ALERTA]} o superior\n"
        f"• Resumen automatico: *07:00h* (cron LXC)\n"
        f"• Fuente: AEMET OpenData API horaria\n\n"
        "Las alertas oficiales AEMET prevalecen siempre.",
        parse_mode=ParseMode.MARKDOWN,
    )


def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("alertas",    cmd_alertas))
    app.add_handler(CommandHandler("tiempo",     cmd_tiempo))
    app.add_handler(CommandHandler("prediccion", cmd_prediccion))
    app.add_handler(CommandHandler("info",       cmd_info))
    logger.info("Bot iniciado — escuchando comandos...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
