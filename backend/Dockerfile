# Hugging Face Spaces expects the app on port 7860.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only torch keeps the image near 1 GB instead of pulling the CUDA stack.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
        -r requirements.txt

# Weights are baked in so a cold start does not depend on the hub being up.
COPY src/nutrivision ./nutrivision_pkg/nutrivision
COPY backend/app ./app
COPY data/nutrition/kb.json ./data/nutrition/kb.json
COPY artifacts/checkpoints/probe_siglip_so400m.pt artifacts/checkpoints/probe_eva02_large.pt ./artifacts/checkpoints/
COPY artifacts/reports/calibration_ensemble_siglip_eva02.json artifacts/reports/conformal.json ./artifacts/reports/

ENV PYTHONPATH=/app/nutrivision_pkg \
    FOODGENOME_ROOT=/app \
    HF_HOME=/app/.hf

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
