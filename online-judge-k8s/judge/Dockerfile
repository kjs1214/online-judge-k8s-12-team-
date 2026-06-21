FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY judge.py /app/
COPY problems /app/problems
COPY submission.py /app/

RUN mkdir -p /work && chmod 777 /work

ENV APPDIR=/app
ENV WORKDIR=/work
ENV TIME_LIMIT_SEC=2

CMD ["python", "/app/judge.py"]