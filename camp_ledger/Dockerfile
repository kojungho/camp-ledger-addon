FROM python:3.13-slim
ARG BUILD_VERSION
ARG BUILD_ARCH
LABEL io.hass.version="${BUILD_VERSION}" io.hass.type="app" io.hass.arch="${BUILD_ARCH}"
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY static ./static
ENV CAMP_DATA=/data/camp-ledger HA_INGRESS=1 PYTHONUNBUFFERED=1 TZ=Asia/Seoul
EXPOSE 8099
CMD ["python", "app.py"]
