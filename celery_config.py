"""
Celery 설정 파일

Redis를 브로커와 결과 백엔드로 사용하는 Celery 설정
"""

from celery import Celery
import os
from dotenv import load_dotenv

load_dotenv()

# Redis URL 설정 (환경변수 또는 기본값)
# Docker 환경에서는 REDIS_HOST 환경변수 사용
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_URL = os.getenv("REDIS_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}/0")

# Celery 앱 생성
celery_app = Celery(
    "report_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks.report_tasks"]
)

# Celery 설정
celery_app.conf.update(
    # 작업 결과 만료 시간 (7일)
    result_expires=604800,
    
    # 작업 타임아웃 설정 (1시간)
    task_time_limit=3600,
    task_soft_time_limit=3300,
    
    # 작업 결과 저장
    task_track_started=True,
    task_send_sent_event=True,
    
    # 작업 직렬화 포맷
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # 타임존 설정
    timezone="Asia/Seoul",
    enable_utc=True,
    
    # 워커 설정
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    
    # 재시도 설정
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# 작업 라우팅 설정
celery_app.conf.task_routes = {
    "tasks.report_tasks.generate_report_task": {"queue": "report_generation"},
    "tasks.report_tasks.embed_report_task": {"queue": "report_embedding"},
}
