FROM python:3.8-bullseye

COPY ./requirements-pre.txt ./requirements.txt /

RUN pip install --no-cache-dir -r /requirements-pre.txt && \
    pip install --no-cache-dir -r /requirements.txt

COPY ./app /app
COPY ./docker/web/root_files/* /
COPY ./decider.py /decider.py

ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
