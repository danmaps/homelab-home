FROM python:3.12-slim
WORKDIR /app
COPY app.py index.html ./
ENV PYTHONDONTWRITEBYTECODE=1 SOLO_HOST=0.0.0.0 SOLO_PORT=8787 SOLO_DB=/data/workouts.db
RUN mkdir -p /data && chown 65534:65534 /data
USER 65534:65534
EXPOSE 8787
CMD ["python", "app.py"]