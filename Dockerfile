FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=Europe/Moscow
WORKDIR /app
COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt && useradd --uid 10001 --create-home skz
COPY server /app/server
COPY backend/schema.sql /app/backend/schema.sql
COPY dist/server.html dist/server.css dist/server.js dist/xlsx.full.min.js /app/dist/
USER skz
ENV PYTHONPATH=/app/server
EXPOSE 8080
CMD ["gunicorn","--chdir","/app/server","--bind","0.0.0.0:8080","--workers","2","--threads","8","--timeout","120","--access-logfile","-","app:app"]
