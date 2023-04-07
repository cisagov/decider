FROM python:3.8-bullseye

COPY ./requirements.txt /requirements.txt

RUN pip install --no-cache-dir pip==23.0.1 && \
    pip install --no-cache-dir setuptools==67.6.1 && \
    pip install --no-cache-dir wheel==0.40.0 && \
    pip install --no-cache-dir --requirement /requirements.txt

RUN apt-get update && \
    apt-get install dos2unix

COPY ./app /app
COPY ./docker/web/root_files/* /
COPY ./decider.py /decider.py

RUN dos2unix /entrypoint.sh

ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
