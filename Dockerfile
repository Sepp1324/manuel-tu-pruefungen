FROM node:22-slim AS frontend

WORKDIR /src
COPY package.json package-lock.json* ./
RUN npm install

# Cache-Bust: Der Git-SHA aendert sich bei JEDEM Commit und invalidiert damit alle
# folgenden Layer. Das erzwingt einen frischen `npm run build` gegen den tatsaechlich
# ausgecheckten Quellstand. Ohne das hat ein veralteter Layer-Cache auf dem
# self-hosted Runner ein altes dist/ ins Image gebacken -> Deploy "gruen", aber die
# ausgelieferte UI blieb auf einem alten Stand haengen (siehe #54/#55).
ARG GIT_SHA=dev
COPY index.html vite.config.js ./
COPY src/ ./src/
COPY public/ ./public/
RUN npm run build && printf '%s' "$GIT_SHA" > dist/build-id.txt

FROM python:3.12-slim

ARG GIT_SHA=dev
ENV PYTHONUNBUFFERED=1 \
    SR_DB_PATH=/data/organicsr.db \
    BUILD_ID=$GIT_SHA

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/
COPY --from=frontend /src/dist/ /app/spa/

# SQLite lives on a mounted volume
VOLUME ["/data"]
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
