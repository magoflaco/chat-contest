# Imagen del juez: lo minimo para correr Python y nada mas.
#
# Deliberadamente NO contiene el codigo del bot, la base de datos ni las claves.
# Aunque alguien lograra ejecutar codigo arbitrario acá adentro, se encontraria
# con un contenedor sin red, con el filesystem de solo lectura y sin nada que robar.
#
# Construir:  docker build -t chat-contest-judge:latest judge/
FROM python:3.12-slim-bookworm

# usuario sin privilegios; el contenedor ademas se lanza con --user
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin juez

# el runner es lo unico que copiamos
COPY runner.py /judge/runner.py
RUN chmod 0555 /judge/runner.py

# sin bytecode ni buffering: la salida llega completa aunque se mate el proceso
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0

USER juez
WORKDIR /work

ENTRYPOINT ["python3", "-I", "/judge/runner.py"]
