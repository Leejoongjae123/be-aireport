#!/bin/bash

# FastAPI 애플리케이션 EC2 자동 배포 스크립트 (Docker Hub 방식)
# 이미지를 Docker Hub에 푸시 후 EC2에서 pull

set -e

# 설정 변수
EC2_HOST="54.180.120.201"
EC2_USER="ubuntu"
SSH_KEY="ubuntu.pem"
CONTAINER_NAME="fastapi-app"
IMAGE_NAME="fastapi-app:latest"
DOCKER_USERNAME="leejoongjae"  # Docker Hub 사용자명으로 변경
DOCKER_IMAGE="${DOCKER_USERNAME}/fastapi-app:latest"
REDIS_IMAGE="redis:7-alpine"

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "FastAPI 애플리케이션 EC2 배포 시작 (Docker Hub)"
echo "=========================================="

# Docker Hub 사용자명 확인
if [ "$DOCKER_USERNAME" = "your-dockerhub-username" ]; then
    echo -e "${RED}❌ DOCKER_USERNAME을 실제 Docker Hub 사용자명으로 변경해주세요.${NC}"
    exit 1
fi

# SSH 키 파일 확인
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}❌ SSH 키 파일을 찾을 수 없습니다: $SSH_KEY${NC}"
    exit 1
fi

# Docker 이미지 빌드
echo -e "${YELLOW}1. Docker 이미지 빌드 중...${NC}"
docker build -t $IMAGE_NAME .
echo -e "${GREEN}✅ 이미지 빌드 완료${NC}"

# Docker Hub용 태그 추가
echo -e "${YELLOW}2. Docker Hub용 태그 추가...${NC}"
docker tag $IMAGE_NAME $DOCKER_IMAGE
echo -e "${GREEN}✅ 태그 추가 완료${NC}"

# Docker Hub 로그인 확인
echo -e "${YELLOW}3. Docker Hub 로그인 확인...${NC}"
if ! docker info | grep -q "Username: $DOCKER_USERNAME"; then
    echo "Docker Hub에 로그인이 필요합니다."
    docker login
fi

# Docker Hub에 이미지 푸시
echo -e "${YELLOW}4. Docker Hub에 이미지 푸시 중...${NC}"
echo "이미지를 Docker Hub에 업로드합니다. 시간이 걸릴 수 있습니다..."
docker push $DOCKER_IMAGE
echo -e "${GREEN}✅ 이미지 푸시 완료${NC}"

# EC2에서 배포 실행
echo -e "${YELLOW}5. EC2에서 애플리케이션 배포 중...${NC}"
ssh -i $SSH_KEY \
    -o ServerAliveInterval=60 \
    -o ServerAliveCountMax=10 \
    ${EC2_USER}@${EC2_HOST} bash -s << ENDSSH
set -e

# 환경 변수 로드
if [ -f ~/.env ]; then
    export \$(cat ~/.env | grep -v '^#' | xargs)
fi

# 기존 컨테이너 중지 및 제거
echo "기존 컨테이너 중지 및 제거..."
docker stop fastapi-app celery-worker redis 2>/dev/null || true
docker rm fastapi-app celery-worker redis 2>/dev/null || true

# Docker 네트워크 생성 (이미 존재하면 무시)
echo "Docker 네트워크 생성..."
docker network create fastapi-network 2>/dev/null || true

# Docker Hub에서 최신 이미지 pull
echo "Docker Hub에서 최신 이미지 다운로드 중..."
docker pull $DOCKER_IMAGE
docker pull $REDIS_IMAGE

# Redis 컨테이너 시작
echo "Redis 컨테이너 시작..."
docker run -d \
    --name redis \
    --network fastapi-network \
    -p 6379:6379 \
    -v redis-data:/data \
    --restart unless-stopped \
    $REDIS_IMAGE redis-server --appendonly yes

# Redis 헬스 체크
echo "Redis 시작 대기 중..."
sleep 5
for i in {1..10}; do
    if docker exec redis redis-cli ping > /dev/null 2>&1; then
        echo "✅ Redis 정상 실행 중"
        break
    fi
    if [ \$i -eq 10 ]; then
        echo "❌ Redis 시작 실패"
        docker logs redis
        exit 1
    fi
    sleep 2
done

# FastAPI 컨테이너 시작
echo "FastAPI 컨테이너 시작..."
docker run -d \
    --name fastapi-app \
    --network fastapi-network \
    -p 8000:8000 \
    -v ~/data:/app/data \
    -v ~/logs:/app/logs \
    -e OPENAI_API_KEY="\${OPENAI_API_KEY}" \
    -e SUPABASE_URL="\${SUPABASE_URL}" \
    -e SUPABASE_KEY="\${SUPABASE_KEY}" \
    -e NEXT_PUBLIC_ACCESS_TOKEN="\${NEXT_PUBLIC_ACCESS_TOKEN}" \
    -e NEXT_PUBLIC_HF_TOKEN="\${NEXT_PUBLIC_HF_TOKEN}" \
    -e NEXT_PUBLIC_S3_ACCESS_KEY="\${NEXT_PUBLIC_S3_ACCESS_KEY}" \
    -e NEXT_PUBLIC_S3_SECRET_KEY="\${NEXT_PUBLIC_S3_SECRET_KEY}" \
    -e REDIS_URL=redis://redis:6379/0 \
    --restart unless-stopped \
    $DOCKER_IMAGE

# Celery Worker 컨테이너 시작
echo "Celery Worker 컨테이너 시작..."
docker run -d \
    --name celery-worker \
    --network fastapi-network \
    -v ~/data:/app/data \
    -v ~/logs:/app/logs \
    -e OPENAI_API_KEY="\${OPENAI_API_KEY}" \
    -e SUPABASE_URL="\${SUPABASE_URL}" \
    -e SUPABASE_KEY="\${SUPABASE_KEY}" \
    -e NEXT_PUBLIC_ACCESS_TOKEN="\${NEXT_PUBLIC_ACCESS_TOKEN}" \
    -e NEXT_PUBLIC_HF_TOKEN="\${NEXT_PUBLIC_HF_TOKEN}" \
    -e NEXT_PUBLIC_S3_ACCESS_KEY="\${NEXT_PUBLIC_S3_ACCESS_KEY}" \
    -e NEXT_PUBLIC_S3_SECRET_KEY="\${NEXT_PUBLIC_S3_SECRET_KEY}" \
    -e REDIS_URL=redis://redis:6379/0 \
    --restart unless-stopped \
    $DOCKER_IMAGE \
    celery -A celery_worker worker --loglevel=info --concurrency=2 -Q report_generation,report_embedding

# 컨테이너 시작 대기
echo "컨테이너 시작 대기 중..."
sleep 15

# 컨테이너 상태 확인
echo "=========================================="
echo "컨테이너 상태 확인"
echo "=========================================="

# Redis 상태 확인
echo -n "Redis: "
if docker ps -q -f name=redis > /dev/null 2>&1; then
    echo "✅ 실행 중"
else
    echo "❌ 실행되지 않음"
fi

# FastAPI 상태 확인
echo -n "FastAPI: "
if docker ps -q -f name=fastapi-app > /dev/null 2>&1; then
    echo "✅ 실행 중"
else
    echo "❌ 실행되지 않음"
fi

# Celery Worker 상태 확인
echo -n "Celery Worker: "
if docker ps -q -f name=celery-worker > /dev/null 2>&1; then
    echo "✅ 실행 중"
else
    echo "❌ 실행되지 않음"
fi

echo ""
echo "모든 컨테이너:"
docker ps --filter "name=redis" --filter "name=fastapi-app" --filter "name=celery-worker"

echo ""
echo "최근 로그:"
echo "--- Redis ---"
docker logs --tail 10 redis
echo ""
echo "--- FastAPI ---"
docker logs --tail 10 fastapi-app
echo ""
echo "--- Celery Worker ---"
docker logs --tail 10 celery-worker

# 사용하지 않는 이미지 정리
echo "사용하지 않는 Docker 이미지 정리..."
docker image prune -f

ENDSSH

echo -e "${GREEN}✅ EC2 배포 완료${NC}"

# 배포 확인
echo ""
echo "=========================================="
echo "배포 확인"
echo "=========================================="
echo -e "${YELLOW}헬스 체크 중...${NC}"

for i in {1..12}; do
    if curl -f -s --max-time 10 http://${EC2_HOST}:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 애플리케이션이 정상적으로 실행 중입니다!${NC}"
        echo ""
        echo "=========================================="
        echo "접속 정보"
        echo "=========================================="
        echo "  - API 서버: http://${EC2_HOST}:8000"
        echo "  - API 문서: http://${EC2_HOST}:8000/docs"
        echo "  - 헬스 체크: http://${EC2_HOST}:8000/health"
        echo "  - Redis: ${EC2_HOST}:6379"
        echo ""
        echo "Docker Hub 이미지: https://hub.docker.com/r/${DOCKER_USERNAME}/fastapi-app"
        echo ""
        echo "=========================================="
        echo "유용한 명령어"
        echo "=========================================="
        echo "  - 모든 로그: ssh -i $SSH_KEY ${EC2_USER}@${EC2_HOST} 'docker logs -f fastapi-app'"
        echo "  - Redis 로그: ssh -i $SSH_KEY ${EC2_USER}@${EC2_HOST} 'docker logs -f redis'"
        echo "  - Celery 로그: ssh -i $SSH_KEY ${EC2_USER}@${EC2_HOST} 'docker logs -f celery-worker'"
        echo "  - 컨테이너 상태: ssh -i $SSH_KEY ${EC2_USER}@${EC2_HOST} 'docker ps'"
        echo "  - Redis CLI: ssh -i $SSH_KEY ${EC2_USER}@${EC2_HOST} 'docker exec -it redis redis-cli'"
        break
    else
        if [ $i -lt 12 ]; then
            echo "시도 $i/12 실패, 5초 후 재시도..."
            sleep 5
        else
            echo -e "${RED}⚠️  헬스 체크 실패${NC}"
            echo "로그 확인:"
            echo "  - FastAPI: ssh -i $SSH_KEY ${EC2_USER}@${EC2_HOST} 'docker logs fastapi-app'"
            echo "  - Redis: ssh -i $SSH_KEY ${EC2_USER}@${EC2_HOST} 'docker logs redis'"
            echo "  - Celery: ssh -i $SSH_KEY ${EC2_USER}@${EC2_HOST} 'docker logs celery-worker'"
        fi
    fi
done
