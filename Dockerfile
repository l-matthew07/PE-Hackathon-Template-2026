FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir uv
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN uv sync

COPY . .

EXPOSE 5000

ENV PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc
RUN mkdir -p /tmp/prometheus_multiproc

CMD ["uv", "run", "gunicorn", "-w", "1", "-k", "gthread", "--threads", "8", "-b", "0.0.0.0:5000", "wsgi:app", "--timeout", "60"]
