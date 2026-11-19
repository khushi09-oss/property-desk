FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir --only-binary=:all: -r requirements.txt
COPY app/*.py ./app/
COPY data/knowledge.json ./data/knowledge.json
COPY web/index.html web/style.css web/app.js web/history.mjs ./web/
COPY web/fonts/newsreader-latin.woff2 web/fonts/public-sans-latin.woff2 web/fonts/newsreader-OFL.txt web/fonts/public-sans-OFL.txt ./web/fonts/
USER 10001:10001
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --no-access-log"]
