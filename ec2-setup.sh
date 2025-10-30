#!/bin/bash

# EC2 초기 설정 스크립트
# Ubuntu 22.04 LTS 기준

set -e

echo "=========================================="
echo "EC2 인스턴스 초기 설정 시작"
echo "=========================================="

# 시스템 업데이트
echo "1. 시스템 패키지 업데이트 중..."
sudo apt-get update
sudo apt-get upgrade -y

# Docker 설치
echo "2. Docker 설치 중..."
if ! command -v docker &> /dev/null; then
    # Docker 공식 GPG 키 추가
    sudo apt-get install -y ca-certificates curl gnupg lsb-release
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    
    # Docker 저장소 추가
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Docker 설치
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # 현재 사용자를 docker 그룹에 추가
    sudo usermod -aG docker $USER
    
    echo "Docker 설치 완료!"
else
    echo "Docker가 이미 설치되어 있습니다."
fi

# Docker 서비스 시작 및 활성화
echo "3. Docker 서비스 시작..."
sudo systemctl start docker
sudo systemctl enable docker

# 스왑 메모리 설정 (4GB)
echo "4. 스왑 메모리 설정 중..."
if [ ! -f /swapfile ]; then
    sudo fallocate -l 4G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    
    # 재부팅 후에도 스왑 유지
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    
    echo "스왑 메모리 설정 완료!"
else
    echo "스왑 파일이 이미 존재합니다."
fi

# 환경 변수 파일 생성
echo "5. 환경 변수 파일 생성..."
if [ ! -f ~/.env ]; then
    cat > ~/.env << 'EOF'
# Supabase 설정
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-key

# OpenAI API Key (필수)
OPENAI_API_KEY=your-openai-api-key

# 기타 설정 (필요시)
NEXT_PUBLIC_ACCESS_TOKEN=
NEXT_PUBLIC_HF_TOKEN=
NEXT_PUBLIC_S3_ACCESS_KEY=
NEXT_PUBLIC_S3_SECRET_KEY=
EOF
    echo "환경 변수 파일이 생성되었습니다: ~/.env"
    echo "⚠️  중요: nano ~/.env 명령으로 실제 값을 입력해주세요!"
else
    echo "환경 변수 파일이 이미 존재합니다."
fi

# 방화벽 설정 (UFW)
echo "6. 방화벽 설정..."
if command -v ufw &> /dev/null; then
    sudo ufw allow 22/tcp
    sudo ufw allow 8000/tcp
    echo "방화벽 규칙 추가 완료 (SSH: 22, API: 8000)"
fi

# Docker 정리 크론잡 추가 (선택사항)
echo "7. Docker 정리 크론잡 설정..."
(crontab -l 2>/dev/null; echo "0 3 * * 0 docker system prune -af --volumes") | crontab -

echo ""
echo "=========================================="
echo "✅ EC2 초기 설정 완료!"
echo "=========================================="
echo ""
echo "다음 단계:"
echo "1. 환경 변수 설정: nano ~/.env"
echo "2. 재로그인: exit 후 다시 SSH 접속"
echo "3. Docker 그룹 적용 확인: docker ps"
echo ""
echo "⚠️  재로그인 후 docker 명령어를 sudo 없이 사용할 수 있습니다."
echo ""
