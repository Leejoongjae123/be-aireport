#!/bin/bash
# 로컬 Docker 환경에서 실행하는 스크립트

echo "================================"
echo "로컬 Docker 환경 시작"
echo "================================"

# 1. 환경 변수 확인
if [ ! -f .env ]; then
    echo "❌ .env 파일이 없습니다."
    exit 1
fi

# 2. Docker 이미지 빌드
echo ""
echo "🔨 Docker 이미지 빌드 중..."
docker build -t multimodal-rag:local .

if [ $? -ne 0 ]; then
    echo "❌ 이미지 빌드 실패"
    exit 1
fi
echo "✅ 이미지 빌드 완료"

# 3. 기존 컨테이너 중지 및 제거
echo ""
echo "🛑 기존 컨테이너 중지 중..."
docker-compose -f docker-compose.local.yml down 2>/dev/null

# 4. 컨테이너 시작
echo ""
echo "🚀 컨테이너 시작 중..."
export DOCKER_IMAGE="multimodal-rag:local"
docker-compose -f docker-compose.local.yml up -d

if [ $? -ne 0 ]; then
    echo "❌ 컨테이너 시작 실패"
    exit 1
fi

# 5. 컨테이너 상태 확인
sleep 3
echo ""
echo "📊 컨테이너 상태:"
docker-compose -f docker-compose.local.yml ps

echo ""
echo "================================"
echo "✅ 로컬 Docker 환경 시작 완료!"
echo "================================"
echo ""
echo "🌐 API 접속: http://localhost:8000"
echo "📚 API 문서: http://localhost:8000/docs"
echo ""
echo "📝 유용한 명령어:"
echo "  로그 확인: docker-compose -f docker-compose.local.yml logs -f"
echo "  재시작: docker-compose -f docker-compose.local.yml restart"
echo "  중지: docker-compose -f docker-compose.local.yml down"
echo ""
