FROM python:3.12-alpine
WORKDIR /app
COPY server.py index.html ./
RUN adduser -D -u 10001 atlas && chown -R atlas:atlas /app
USER atlas
ENV PYTHONDONTWRITEBYTECODE=1
CMD ["python", "server.py"]