# EC2 배포 스크립트 (Docker Hub 기반)

# 변수 설정
$EC2Host = "43.202.56.229"
$PemFile = "ubuntu.pem"
$DockerImage = "leejoongjae/multimodal-rag:latest"
$RemoteDir = "/home/ubuntu/multimodal-rag"

Write-Host "================================" -ForegroundColor Cyan
Write-Host "🚀 EC2 배포 시작" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host "EC2 호스트: $EC2Host" -ForegroundColor Yellow
Write-Host "Docker 이미지: $DockerImage" -ForegroundColor Yellow
Write-Host ""

# 1. PEM 파일 확인
if (-not (Test-Path $PemFile)) {
    Write-Host "❌ PEM 파일을 찾을 수 없습니다: $PemFile" -ForegroundColor Red
    exit 1
}

# 2. .env 파일 확인
if (-not (Test-Path .env)) {
    Write-Host "❌ .env 파일이 없습니다." -ForegroundColor Red
    exit 1
}

Write-Host "✅ 파일 확인 완료" -ForegroundColor Green

# 3. 필수 파일 전송
Write-Host "`n📤 설정 파일 전송 중..." -ForegroundColor Yellow
scp -i $PemFile docker-compose.hub.yml "ubuntu@${EC2Host}:${RemoteDir}/docker-compose.yml"

# .env 파일은 EC2에 이미 있으면 덮어쓰지 않음
ssh -i $PemFile "ubuntu@$EC2Host" "test -f ${RemoteDir}/.env"
if ($LASTEXITCODE -ne 0) {
    Write-Host "📝 .env 파일이 없습니다. 로컬 .env를 전송합니다..." -ForegroundColor Yellow
    scp -i $PemFile .env "ubuntu@${EC2Host}:${RemoteDir}/.env"
} else {
    Write-Host "✅ .env 파일이 이미 존재합니다. 유지합니다." -ForegroundColor Green
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 파일 전송 실패" -ForegroundColor Red
    exit 1
}
Write-Host "✅ 파일 전송 완료" -ForegroundColor Green

# 4. EC2에서 배포 실행
Write-Host "`n🐳 EC2에서 Docker 컨테이너 배포 중..." -ForegroundColor Yellow
ssh -i $PemFile "ubuntu@$EC2Host" @"
cd $RemoteDir

# 환경 변수 설정
export DOCKER_IMAGE=$DockerImage

# 기존 컨테이너 중지 및 제거
echo '🛑 기존 컨테이너 중지 중...'
sudo docker-compose down 2>/dev/null || true

# 최신 이미지 pull
echo '📥 Docker Hub에서 이미지 다운로드 중...'
sudo docker pull $DockerImage

# 컨테이너 시작
echo '🚀 컨테이너 시작 중...'
sudo DOCKER_IMAGE=$DockerImage docker-compose up -d

# 상태 확인
echo ''
echo '📊 컨테이너 상태:'
sudo docker-compose ps

# 로그 확인 (마지막 20줄)
echo ''
echo '📋 최근 로그:'
sudo docker-compose logs --tail=20
"@

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 배포 실패" -ForegroundColor Red
    exit 1
}

Write-Host "`n================================" -ForegroundColor Cyan
Write-Host "✅ 배포 완료!" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "🌐 API 접속: http://${EC2Host}:8000" -ForegroundColor Cyan
Write-Host "📚 API 문서: http://${EC2Host}:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "📝 유용한 명령어:" -ForegroundColor Yellow
Write-Host "  로그 확인: ssh -i $PemFile ubuntu@$EC2Host 'cd $RemoteDir && sudo docker-compose logs -f'" -ForegroundColor White
Write-Host "  재시작: ssh -i $PemFile ubuntu@$EC2Host 'cd $RemoteDir && sudo docker-compose restart'" -ForegroundColor White
Write-Host "  중지: ssh -i $PemFile ubuntu@$EC2Host 'cd $RemoteDir && sudo docker-compose down'" -ForegroundColor White
Write-Host ""
