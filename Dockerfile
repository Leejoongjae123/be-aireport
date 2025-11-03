# Multi-stage build로 이미지 크기 최적화
FROM python:3.11-slim as builder

WORKDIR /app

# 빌드 도구 설치
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# requirements 복사 및 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user -r requirements.txt

# 최종 이미지
FROM python:3.11-slim

WORKDIR /app

# unstructured[pdf]를 위한 런타임 의존성만 설치
RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    libtesseract-dev \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# builder에서 설치된 패키지 복사
COPY --from=builder /root/.local /root/.local

# PATH 설정
ENV PATH=/root/.local/bin:$PATH

# 애플리케이션 코드 복사
COPY . .

# 포트 노출
EXPOSE 8000

# 헬스체크 설정 (초기화 시간을 충분히 확보)
HEALTHCHECK --interval=30s --timeout=30s --start-period=120s --retries=5 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=10)" || exit 1

# 애플리케이션 실행 (타임아웃 설정 추가)
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info", "--timeout-keep-alive", "300", "--timeout-graceful-shutdown", "30"]
