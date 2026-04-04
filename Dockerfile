FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir uv
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN uv sync

COPY . .

EXPOSE 5000

CMD ["uv", "run", "run.py"]
