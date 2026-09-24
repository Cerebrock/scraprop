# scraprop — monitor de compra de propiedades (MercadoLibre) en contenedor.
# Se corre como JOB efímero (un contenedor por pasada), invocado por el cron del
# host de la Raspberry Pi. La data persiste en el bind-mount ./data del host.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=America/Argentina/Buenos_Aires

WORKDIR /app

# tzdata para que los timestamps respeten la hora de Buenos Aires.
RUN apt-get update -qq \
    && apt-get install -y --no-install-recommends tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Dependencias Python primero (cache de capa).
COPY requirements.txt .
RUN pip install -r requirements.txt

# Chromium parcheado de patchright + sus libs de sistema (headless).
RUN patchright install --with-deps chromium

# Código de la app + config personal (searches/prompt/marcadas leídos desde ROOT).
COPY scraprop/ ./scraprop/
COPY searches*.txt prompt*.txt marcadas.txt ./

# data/ (db, csv, storage_state.json) se monta como volumen en runtime.
RUN mkdir -p /app/data

# Por defecto, una pasada de monitoreo. El cron del host sobre-escribe el comando
# (p.ej. `... python -m scraprop digest`).
CMD ["python", "-m", "scraprop", "run"]
