FROM python:3.13-slim
ARG BUILD_VERSION
ARG BUILD_ARCH
LABEL io.hass.version="${BUILD_VERSION}" io.hass.type="app" io.hass.arch="${BUILD_ARCH}"
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-kor && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# Pin the Korean accuracy model and the English model used for site labels.
RUN python - <<'PYMODELS'
import hashlib,urllib.request
from pathlib import Path
root=Path('/app/ocr-models');root.mkdir()
for lang,repo,rev,digest in [
 ('kor','tessdata_best','e12c65a915945e4c28e237a9b52bc4a8f39a0cec','f888d4038348a0c3d25151e7f452bda0d74ca275b18cab146798bcbb94084fff'),
 ('eng','tessdata_fast','87416418657359cb625c412a48b6e1d6d41c29bd','7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2')]:
 data=urllib.request.urlopen(f'https://raw.githubusercontent.com/tesseract-ocr/{repo}/{rev}/{lang}.traineddata',timeout=90).read()
 assert hashlib.sha256(data).hexdigest()==digest,'OCR model checksum mismatch'
 (root/(lang+'.traineddata')).write_bytes(data)
PYMODELS
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py mobile_access.py exchange.py live_sync.py integrated.py config.yaml .
COPY static ./static
COPY journal ./journal
ENV JOURNAL_VERSION=${BUILD_VERSION} JOURNAL_DATA=/data/campsite-journal CAMP_VERSION=${BUILD_VERSION} CAMP_DATA=/data/camp-ledger HA_INGRESS=1 PYTHONUNBUFFERED=1 TZ=Asia/Seoul
EXPOSE 8099 8098
CMD ["python", "app.py"]
