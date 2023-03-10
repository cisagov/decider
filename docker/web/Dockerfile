FROM python:3.8-bullseye

COPY ./requirements.txt /requirements.txt
RUN pip install --no-cache-dir --requirement /requirements.txt

COPY . /app
WORKDIR /app

ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]
