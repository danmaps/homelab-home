# Keep the vendor application and its data unchanged; this image only repairs
# the Docker readiness probe using Python already present in the vendor image.
FROM ghcr.io/open-webui/open-webui:v0.11.1@sha256:6bb1fbe8ab0a3e0456067f493044ffb66a30a65a34be47f6a5862176a370dd16

COPY healthcheck.py /opt/open-webui-healthcheck.py

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD ["python3", "/opt/open-webui-healthcheck.py"]
