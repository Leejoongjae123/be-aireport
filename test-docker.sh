#!/bin/bash

echo "=== Docker 이미지 빌드 ==="
docker build -t fastapi-app:latest .

echo ""
echo "=== Docker 컨테이너 실행 ==="
docker run -d --name fastapi-app-test -p 8000:8000 fastapi-app:latest

echo ""
echo "=== 5초 대기 ==="
sleep 5

echo ""
echo "=== 컨테이너 상태 확인 ==="
docker ps -a | grep fastapi-app-test

echo ""
echo "=== 컨테이너 로그 ==="
docker logs fastapi-app-test

echo ""
echo "=== 헬스 체크 ==="
curl -s http://localhost:8000/health | python -m json.tool || echo "헬스 체크 실패"

echo ""
echo "=== 컨테이너 정리 ==="
docker stop fastapi-app-test
docker rm fastapi-app-test
