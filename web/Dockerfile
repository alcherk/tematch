# Stage 1: Build React frontend
FROM node:20-slim AS frontend
WORKDIR /app/web/frontend
COPY web/frontend/package*.json ./
RUN npm ci
COPY web/frontend/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY core/ core/
COPY web/ web/
COPY --from=frontend /app/web/frontend/dist web/frontend/dist
CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "8080"]
