#!/bin/bash

# FastAPI 애플리케이션 EC2 자동 배포 스크립트 (rsync 버전)

set -e

# 설정 변수
EC2_HOST="3.35.8.151"
EC2_USER="ubuntu"
SSH_KEY="ubuntu.pem"
CONTAINER_NAME="fastapi-app"
IMAGE_NAME="fastapi-app:latest"

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "FastAPI 애플리케이션 EC2 배포 시작 (rsync)"
echo "=========================================="

# SSH 키 파일 확인
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}❌ SSH 키 파일을 찾을 수 없습니다: $SSH_KEY${NC}"
    exit 1
fi

# Docker 이미지 빌드
echo -e "${YELLOW}1. Docker 이미지 빌드 중...${NC}"
docker build -t $IMAGE_NAME .
echo -e "${GREEN}✅ 이미지 빌드 완료${NC}"

# Docker 이미지를 tar.gz로 저장
echo -e "${YELLOW}2. Docker 이미지 압축 중...${NC}"
docker save $IMAGE_NAME | gzip > /tmp/fastapi-app.tar.gz
echo -e "${GREEN}✅ 이미지 압축 완료${NC}"

# 파일 크기 확인
FILE_SIZE=$(du -h /tmp/fastapi-app.tar.gz | cut -f1)
echo "압축된 이미지 크기: $FILE_SIZE"

# EC2로 이미지 전송 (rsync 사용 - 중단 시 이어받기 가능)
echo -e "${YELLOW}3. EC2로 이미지 전송 중 (rsync)...${NC}"
echo "rsync는 중단되어도 이어서 전송할 수 있습니다."

# rsync 옵션:
# -a: 아카이브 모드
# -v: 상세 출력
# -z: 압축 전송
# -P: 진행상황 표시 + 부분 전송 유지 (중단 시 이어받기)
# --partial: 부분 전송된 파일 유지
# --progress: 진행률 표시
rsync -avzP --partial \
    -e "ssh -i $SSH_KEY -o ServerAliveInterval=60 -o ServerAliveCountMax=10" \
    /tmp/fastapi-app.tar.gz \
    ${EC2_USER}@${EC2_HOST}:/tmp/

echo -e "${GREEN}✅ 이미지 전송 완료${NC}"

# 임시 파일 삭제
rm /tmp/fastapi-app.tar.gz

# EC2에서 배포 실행
echo -e "${YELLOW}4. EC2에서 애플리케이션 배포 중...${NC}"
ssh -i $SSH_KEY \
    -o ServerAliveInterval=60 \
    -o ServerAliveCountMax=10 \
    ${EC2_USER}@${EC2_HOST} << 'ENDSSH'
set -e

# 환경 변수 로드
if [ -f ~/.env ]; then
    export $(cat ~/.env | grep -v '^#' | xargs)
fi

# Docker 이미지 로드
echo "이미지 로드 중..."
gunzip -c /tmp/fastapi-app.tar.gz | docker load
rm /tmp/fastapi-app.tar.gz

# 기존 컨테이너 중지 및 제거
if [ "$(docker ps -aq -f name=fastapi-app)" ]; then
    echo "기존 컨테이너 중지 및 제거..."
    docker stop fastapi-app || true
    docker rm fastapi-app || true
fi

# 새 컨테이너 실행
echo "새 컨테이너 시작..."
docker run -d \
    --name fastapi-app \
    -p 8000:8000 \
    -v ~/data:/app/data \
    -v ~/logs:/app/logs \
    -e OPENAI_API_KEY="${OPENAI_API_KEY}" \
    -e SUPABASE_URL="${SUPABASE_URL}" \
    -e SUPABASE_KEY="${SUPABASE_KEY}" \
    -e NEXT_PUBLIC_ACCESS_TOKEN="${NEXT_PUBLIC_ACCESS_TOKEN}" \
    -e NEXT_PUBLIC_HF_TOKEN="${NEXT_PUBLIC_HF_TOKEN}" \
    -e NEXT_PUBLIC_S3_ACCESS_KEY="${NEXT_PUBLIC_S3_ACCESS_KEY}" \
    -e NEXT_PUBLIC_S3_SECRET_KEY="${NEXT_PUBLIC_S3_SECRET_KEY}" \
    --restart unless-stopped \
    fastapi-app:latest

# 컨테이너 시작 대기
echo "컨테이너 시작 대기 중..."
sleep 15

# 컨테이너 상태 확인
if [ "$(docker ps -q -f name=fastapi-app)" ]; then
    echo "✅ 컨테이너가 성공적으로 시작되었습니다!"
    docker ps -f name=fastapi-app
    echo ""
    echo "애플리케이션 로그:"
    docker logs --tail 20 fastapi-app
else
    echo "❌ 컨테이너 시작 실패. 로그:"
    docker logs fastapi-app
    exit 1
fi

# 이미지 정리
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
        echo "접속 정보:"
        echo "  - API 문서: http://${EC2_HOST}:8000/docs"
        echo "  - 헬스 체크: http://${EC2_HOST}:8000/health"
        break
    else
        if [ $i -lt 12 ]; then
            echo "시도 $i/12 실패, 5초 후 재시도..."
            sleep 5
        else
            echo -e "${RED}⚠️  헬스 체크 실패${NC}"
            echo "로그 확인: ssh -i $SSH_KEY ${EC2_USER}@${EC2_HOST} 'docker logs fastapi-app'"
        fi
    fi
done

echo ""
echo "로그 확인: ssh -i $SSH_KEY ${EC2_USER}@${EC2_HOST} 'docker logs -f fastapi-app'"
