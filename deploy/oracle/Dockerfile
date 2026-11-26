FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake libopenblas-dev && rm -rf /var/lib/apt/lists/*
RUN CMAKE_BUILD_PARALLEL_LEVEL=2 CMAKE_ARGS="-DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS -DGGML_NATIVE=OFF" pip install --no-cache-dir "llama-cpp-python>=0.3.16,<0.4" "fastapi>=0.115,<1" "uvicorn>=0.34,<1" "huggingface-hub>=0.30,<1"
WORKDIR /app
COPY boitia ./boitia
COPY frontend ./frontend
COPY deploy/oracle ./deploy/oracle
RUN useradd -m -u 10001 boitia && mkdir /cache && chown boitia:boitia /cache
USER boitia
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python","deploy/oracle/app.py"]
