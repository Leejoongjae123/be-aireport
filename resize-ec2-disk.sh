#!/bin/bash

# EC2 디스크 확장 스크립트 (AWS 콘솔에서 볼륨 크기 증가 후 실행)

set -e

# 설정 변수
EC2_HOST="54.180.120.201"
EC2_USER="ubuntu"
SSH_KEY="ubuntu.pem"

# 색상 코드
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "EC2 디스크 파일시스템 확장"
echo "=========================================="
echo ""
echo -e "${YELLOW}주의: AWS 콘솔에서 EBS 볼륨 크기를 먼저 증가시켜야 합니다!${NC}"
echo ""

# SSH 키 파일 확인
if [ ! -f "$SSH_KEY" ]; then
    echo "❌ SSH 키 파일을 찾을 수 없습니다: $SSH_KEY"
    exit 1
fi

echo "1. 현재 디스크 상태 확인..."
ssh -i $SSH_KEY ${EC2_USER}@${EC2_HOST} "df -h && echo '' && lsblk"

echo ""
echo "2. 파티션 및 파일시스템 확장 중..."
ssh -i $SSH_KEY ${EC2_USER}@${EC2_HOST} << 'EOF'
    # 파티션 확장 (루트 볼륨이 /dev/xvda1 또는 /dev/nvme0n1p1일 수 있음)
    if [ -e /dev/xvda1 ]; then
        echo "- /dev/xvda 파티션 확장..."
        sudo growpart /dev/xvda 1
        echo "- 파일시스템 확장..."
        sudo resize2fs /dev/xvda1
    elif [ -e /dev/nvme0n1p1 ]; then
        echo "- /dev/nvme0n1 파티션 확장..."
        sudo growpart /dev/nvme0n1 1
        echo "- 파일시스템 확장..."
        sudo resize2fs /dev/nvme0n1p1
    else
        echo "❌ 루트 파티션을 찾을 수 없습니다."
        exit 1
    fi
    
    echo ""
    echo "✅ 파일시스템 확장 완료"
EOF

echo ""
echo "3. 확장 후 디스크 상태..."
ssh -i $SSH_KEY ${EC2_USER}@${EC2_HOST} "df -h"

echo ""
echo -e "${GREEN}=========================================="
echo "디스크 확장 완료"
echo -e "==========================================${NC}"
