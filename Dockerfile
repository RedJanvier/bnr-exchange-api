FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code + committed data + demo page.
COPY app ./app
COPY data ./data
COPY web ./web

EXPOSE 8080
ENV PORT=8080

# The data is baked into the image; redeploy to pick up newer committed rates.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
