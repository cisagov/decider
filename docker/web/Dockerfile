FROM python:3.8-bullseye

COPY ./requirements.txt /requirements.txt
RUN pip install --no-cache-dir --requirement /requirements.txt

COPY ./app /app
COPY ./docker/web/root_files/* /
COPY ./decider.py /decider.py

ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
