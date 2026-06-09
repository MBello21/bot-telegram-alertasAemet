#!/usr/bin/env python3
"""
Script one-shot para el cron de las 07:00.
Envia texto de alertas + foto tabla si hay alerta CAP o categoria >= CAT. II.
"""

import asyncio
import io
import logging
import os
import sys

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


async def main() -> None:
    client = AemetClient(AEMET_API_KEY)
    bot    = Bot(token=TELEGRAM_TOKEN)

    debe_enviar, texto_alertas, imagen = await client.evaluar_y_formatear(
        MUNICIPIO_CODIGO, PROVINCIA_CODIGO
    )

    if debe_enviar:
        # 1. Texto de alertas
        await bot.send_message(
            chat_id    = CHAT_ID,
            text       = texto_alertas,
            parse_mode = ParseMode.MARKDOWN,
        )
        # 2. Foto con la tabla
        if imagen:
            await bot.send_photo(
                chat_id = CHAT_ID,
                photo   = io.BytesIO(imagen),
            )
        logger.info("Alerta enviada.")
    else:
        logger.info("Sin alertas (CAT. 0 o I) — no se envia nada.")


if __name__ == "__main__":
    asyncio.run(main())
