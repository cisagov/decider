FROM python:3.8-bullseye

COPY ./requirements.txt /requirements.txt
RUN pip install --no-cache-dir --requirement /requirements.txt

COPY . /app
WORKDIR /app
RUN rm -rf .env user.json init.sql 
# TODO: user.json is in a different location actually

ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]
