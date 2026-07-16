FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 🔥 SỬA CMD: dùng shell để parse $PORT
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT app:app"]
