#!/bin/bash

# EC2 디스크 공간 확보 스크립트

set -e

# 설정 변수
EC2_HOST="54.180.120.201"
EC2_USER="ubuntu"
SSH_KEY="ubuntu.pem"

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "EC2 디스크 공간 확보 시작"
echo "=========================================="

# SSH 키 파일 확인
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}❌ SSH 키 파일을 찾을 수 없습니다: $SSH_KEY${NC}"
    exit 1
fi

echo "1. 현재 디스크 사용량 확인..."
ssh -i $SSH_KEY ${EC2_USER}@${EC2_HOST} "df -h"

echo ""
echo "2. Docker 시스템 정리 중..."
ssh -i $SSH_KEY ${EC2_USER}@${EC2_HOST} << 'EOF'
    # 중지된 컨테이너 삭제
    echo "- 중지된 컨테이너 삭제..."
    docker container prune -f
    
    # 사용하지 않는 이미지 삭제
    echo "- 사용하지 않는 이미지 삭제..."
    docker image prune -a -f
    
    # 사용하지 않는 볼륨 삭제
    echo "- 사용하지 않는 볼륨 삭제..."
    docker volume prune -f
    
    # 사용하지 않는 네트워크 삭제
    echo "- 사용하지 않는 네트워크 삭제..."
    docker network prune -f
    
    # 빌드 캐시 삭제
    echo "- 빌드 캐시 삭제..."
    docker builder prune -a -f
    
    # 전송된 tar.gz 파일 삭제
    echo "- 전송된 이미지 파일 삭제..."
    rm -f ~/fastapi-app.tar.gz
    
    echo ""
    echo "✅ Docker 시스템 정리 완료"
EOF

echo ""
echo "3. 정리 후 디스크 사용량..."
ssh -i $SSH_KEY ${EC2_USER}@${EC2_HOST} "df -h"

echo ""
echo -e "${GREEN}=========================================="
echo "디스크 공간 확보 완료"
echo -e "==========================================${NC}"
