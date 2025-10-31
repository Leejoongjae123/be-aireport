#!/bin/bash

# 로컬 Docker Compose 실행 스크립트
# Redis, FastAPI, Celery Worker를 한 번에 실행합니다.

set -e

echo "=========================================="
echo "로컬 개발 환경 시작"
echo "=========================================="

# .env 파일 확인
if [ ! -f .env ]; then
    echo "❌ .env 파일이 없습니다. .env 파일을 생성해주세요."
    exit 1
fi

echo "✅ .env 파일 확인 완료"

# 기존 컨테이너 정리
echo ""
echo "기존 컨테이너 확인 중..."

# docker-compose로 관리되는 컨테이너 정리
echo "docker-compose 컨테이너 중지 및 삭제 중..."
docker-compose down 2>/dev/null || true

# 개별 컨테이너 강제 삭제 (이름 충돌 방지)
echo "개별 컨테이너 확인 및 삭제 중..."
docker rm -f redis 2>/dev/null || true
docker rm -f fastapi-app 2>/dev/null || true
docker rm -f celery-worker 2>/dev/null || true

echo "✅ 기존 컨테이너 정리 완료"

# Docker Compose 빌드 및 실행
echo ""
echo "=========================================="
echo "Docker 이미지 빌드 중..."
echo "=========================================="
docker-compose build

echo ""
echo "=========================================="
echo "서비스 시작 중..."
echo "=========================================="
docker-compose up -d

echo ""
echo "서비스 시작 대기 중..."
sleep 5

# 서비스 상태 확인
echo ""
echo "=========================================="
echo "서비스 상태 확인"
echo "=========================================="
docker-compose ps

echo ""
echo "=========================================="
echo "헬스 체크"
echo "=========================================="

# Redis 헬스 체크
echo -n "Redis: "
if docker exec redis redis-cli ping > /dev/null 2>&1; then
    echo "✅ 정상"
else
    echo "❌ 실패"
fi

# FastAPI 헬스 체크
echo -n "FastAPI: "
MAX_RETRIES=10
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ 정상"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        echo "❌ 실패 (타임아웃)"
    else
        sleep 2
    fi
done

# Celery Worker 상태 확인
echo -n "Celery Worker: "
if docker ps | grep -q "celery-worker"; then
    echo "✅ 실행 중"
else
    echo "❌ 실행되지 않음"
fi

echo ""
echo "=========================================="
echo "✅ 로컬 개발 환경 시작 완료!"
echo "=========================================="
echo ""
echo "📌 접속 정보:"
echo "  - API 서버: http://localhost:8000"
echo "  - API 문서: http://localhost:8000/docs"
echo "  - Redis: localhost:6379"
echo ""
echo "📋 유용한 명령어:"
echo "  - 로그 확인: docker-compose logs -f"
echo "  - 특정 서비스 로그: docker-compose logs -f [fastapi-app|celery-worker|redis]"
echo "  - 서비스 중지: docker-compose down"
echo "  - 서비스 재시작: docker-compose restart"
echo ""
echo "🔍 Redis 작업 확인:"
echo "  - docker exec -it redis redis-cli"
echo "  - 또는 API: http://localhost:8000/api/jobs/list"
echo ""
