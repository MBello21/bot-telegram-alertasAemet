#!/usr/bin/env python3
"""
Script one-shot para el cron de las 06:30.
Solo envia si hay alerta CAP oficial o categoria interna >= CAT. II.
Usa un flag en /tmp para evitar reenvios si el cron se ejecuta varias veces.
"""

import asyncio
import io
import logging
import os
import sys
from datetime import date

from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode

from aemet import AemetClient

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

FLAG_PATH = f"/tmp/aemet_enviado_{date.today().isoformat()}.flag"


async def main() -> None:
    # Comprobar si ya se envio hoy
    if os.path.exists(FLAG_PATH):
        logger.info("Ya enviado hoy, omitiendo.")
        return

    client = AemetClient(AEMET_API_KEY)
    bot    = Bot(token=TELEGRAM_TOKEN)

    debe_enviar, texto_alertas, imagen = await client.evaluar_y_formatear(
        MUNICIPIO_CODIGO, PROVINCIA_CODIGO
    )

    if debe_enviar:
        await bot.send_message(
            chat_id    = CHAT_ID,
            text       = texto_alertas,
            parse_mode = ParseMode.MARKDOWN,
        )
        if imagen:
            await bot.send_photo(
                chat_id = CHAT_ID,
                photo   = io.BytesIO(imagen),
            )
        # Crear flag para evitar reenvios
        open(FLAG_PATH, "w").close()
        logger.info("Alerta enviada.")
    else:
        # Tambien marcamos flag si no hay alertas para no reintentar
        open(FLAG_PATH, "w").close()
        logger.info("Sin alertas (CAT. 0 o I) — no se envia nada.")


if __name__ == "__main__":
    asyncio.run(main())
