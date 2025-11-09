#!/bin/bash

# EC2 초기 설정 스크립트
# Ubuntu 22.04 LTS 기준

echo "================================"
echo "🔧 EC2 초기 설정 시작"
echo "================================"

# 1. 시스템 업데이트
echo ""
echo "📦 시스템 패키지 업데이트 중..."
sudo apt-get update
sudo apt-get upgrade -y

# 2. Docker 설치
echo ""
echo "🐳 Docker 설치 중..."
if ! command -v docker &> /dev/null; then
    # Docker 공식 GPG 키 추가
    sudo apt-get install -y ca-certificates curl gnupg
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    # Docker 저장소 추가
    echo \
      "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Docker 설치
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # 현재 사용자를 docker 그룹에 추가
    sudo usermod -aG docker $USER

    echo "✅ Docker 설치 완료"
else
    echo "✅ Docker가 이미 설치되어 있습니다"
fi

# 3. Docker Compose 설치 (standalone)
echo ""
echo "🐳 Docker Compose 설치 중..."
if ! command -v docker-compose &> /dev/null; then
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    echo "✅ Docker Compose 설치 완료"
else
    echo "✅ Docker Compose가 이미 설치되어 있습니다"
fi

# 4. 작업 디렉토리 생성
echo ""
echo "📁 작업 디렉토리 생성 중..."
mkdir -p ~/multimodal-rag/data
mkdir -p ~/multimodal-rag/logs
cd ~/multimodal-rag

# 5. .env 파일 템플릿 생성
echo ""
echo "📝 .env 파일 템플릿 생성 중..."
cat > .env << 'EOF'
# OpenAI API
OPENAI_API_KEY=your-openai-api-key

# Supabase
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-key

# AWS S3
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_REGION=ap-northeast-2
S3_BUCKET_NAME=your-bucket-name

# Redis
REDIS_URL=redis://redis:6379/0
EOF

echo "✅ .env 파일 템플릿 생성 완료"

# 6. 스왑 메모리 설정 (메모리 부족 방지)
echo ""
echo "💾 스왑 메모리 설정 중..."
if [ ! -f /swapfile ]; then
    sudo fallocate -l 4G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "✅ 스왑 메모리 설정 완료 (4GB)"
else
    echo "✅ 스왑 메모리가 이미 설정되어 있습니다"
fi

# 7. 방화벽 설정 (UFW)
echo ""
echo "🔥 방화벽 설정 중..."
sudo ufw allow 22/tcp
sudo ufw allow 8000/tcp
echo "y" | sudo ufw enable
echo "✅ 방화벽 설정 완료"

# 8. Docker 서비스 시작
echo ""
echo "🚀 Docker 서비스 시작 중..."
sudo systemctl start docker
sudo systemctl enable docker

echo ""
echo "================================"
echo "✅ EC2 초기 설정 완료!"
echo "================================"
echo ""
echo "📝 다음 단계:"
echo "1. .env 파일 편집:"
echo "   nano ~/multimodal-rag/.env"
echo ""
echo "2. 재로그인 (Docker 그룹 적용):"
echo "   exit"
echo "   ssh -i ubuntu.pem ubuntu@your-ec2-ip"
echo ""
echo "3. 로컬에서 배포 실행:"
echo "   .\deploy-to-ec2.ps1"
echo ""
