FROM node:22-slim AS frontend

WORKDIR /src
COPY package.json package-lock.json* ./
RUN npm install
COPY index.html vite.config.js ./
COPY src/ ./src/
COPY public/ ./public/
RUN npm run build

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    SR_DB_PATH=/data/organicsr.db

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/
COPY --from=frontend /src/dist/ /app/spa/

# SQLite lives on a mounted volume
VOLUME ["/data"]
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
