FROM python:3.12-slim

ENV TZ=Europe/Madrid
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata fonts-dejavu \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY aemet.py categorias.py bot.py enviar_resumen.py generar_preddiccion_imagen.py generar_tabla_imagen.py logo.png ./

CMD ["python", "bot.py"]
