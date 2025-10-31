"""
Celery 워커 실행 파일

사용법:
    celery -A celery_worker worker --loglevel=info --concurrency=2 -Q report_generation,report_embedding
"""

from celery_config import celery_app
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# Celery 앱을 워커로 실행하기 위해 export
app = celery_app

if __name__ == "__main__":
    app.start()
