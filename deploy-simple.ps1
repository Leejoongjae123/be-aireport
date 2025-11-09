# 간단한 EC2 배포 스크립트

$EC2_HOST = "43.202.56.229"
$PEM_FILE = "ubuntu.pem"
$REMOTE_DIR = "/home/ubuntu/multimodal-rag"

Write-Host "🚀 EC2 배포 시작..." -ForegroundColor Cyan

# 1. 필수 파일들만 개별 전송
Write-Host "`n📤 파일 전송 중..." -ForegroundColor Yellow

$files = @(
    "Dockerfile",
    "docker-compose.yml",
    ".dockerignore",
    "requirements.txt",
    ".env"
)

foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "  - $file" -ForegroundColor Gray
        scp -i $PEM_FILE $file "ubuntu@${EC2_HOST}:${REMOTE_DIR}/"
    }
}

# 2. Python 파일들 전송
Write-Host "`n📤 Python 파일 전송 중..." -ForegroundColor Yellow
scp -i $PEM_FILE *.py "ubuntu@${EC2_HOST}:${REMOTE_DIR}/"

# 3. 디렉토리별 전송
Write-Host "`n📤 디렉토리 전송 중..." -ForegroundColor Yellow
scp -i $PEM_FILE -r services "ubuntu@${EC2_HOST}:${REMOTE_DIR}/"
scp -i $PEM_FILE -r routers "ubuntu@${EC2_HOST}:${REMOTE_DIR}/"
scp -i $PEM_FILE -r tasks "ubuntu@${EC2_HOST}:${REMOTE_DIR}/"

# 4. EC2에서 Docker 재시작
Write-Host "`n🐳 Docker 컨테이너 재시작 중..." -ForegroundColor Yellow
ssh -i $PEM_FILE "ubuntu@$EC2_HOST" @"
cd $REMOTE_DIR
sudo docker-compose down
sudo docker-compose up --build -d
sudo docker-compose ps
"@

Write-Host "`n✅ 배포 완료!" -ForegroundColor Green
Write-Host "🌐 API: http://${EC2_HOST}:8000" -ForegroundColor Cyan
Write-Host "📚 문서: http://${EC2_HOST}:8000/docs" -ForegroundColor Cyan
