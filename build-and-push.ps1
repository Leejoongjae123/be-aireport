# Docker 이미지 빌드 및 Docker Hub 푸시 스크립트

# 변수 설정
$DockerUsername = "leejoongjae"
$ImageName = "multimodal-rag"
$Tag = "latest"

$FullImageName = "$DockerUsername/$ImageName`:$Tag"

Write-Host "================================" -ForegroundColor Cyan
Write-Host "🐳 Docker 이미지 빌드 및 푸시" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host "Docker Username: $DockerUsername" -ForegroundColor Gray
Write-Host "Image Name: $ImageName" -ForegroundColor Gray
Write-Host "Tag: $Tag" -ForegroundColor Gray
Write-Host "Full Image: $FullImageName" -ForegroundColor Yellow
Write-Host ""

# 1. Docker 로그인 확인
Write-Host "🔐 Docker Hub 로그인 확인 중..." -ForegroundColor Yellow
docker info | Select-String "Username" | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker Hub에 로그인이 필요합니다." -ForegroundColor Red
    docker login
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Docker Hub 로그인 실패" -ForegroundColor Red
        exit 1
    }
}
Write-Host "✅ Docker Hub 로그인 확인 완료" -ForegroundColor Green

# 2. 이미지 빌드
Write-Host "`n🔨 Docker 이미지 빌드 중..." -ForegroundColor Yellow
docker build -t $FullImageName .
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 이미지 빌드 실패" -ForegroundColor Red
    exit 1
}
Write-Host "✅ 이미지 빌드 완료" -ForegroundColor Green

# 3. Docker Hub에 푸시
Write-Host "`n📤 Docker Hub에 푸시 중..." -ForegroundColor Yellow
docker push $FullImageName
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 이미지 푸시 실패" -ForegroundColor Red
    exit 1
}
Write-Host "✅ 이미지 푸시 완료" -ForegroundColor Green

# 4. 이미지 정보 출력
Write-Host "`n================================" -ForegroundColor Cyan
Write-Host "✅ 완료!" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Cyan
Write-Host "이미지: $FullImageName" -ForegroundColor Yellow
Write-Host ""
Write-Host "다음 명령어로 EC2에 배포하세요:" -ForegroundColor Cyan
Write-Host "  .\deploy-to-ec2.ps1 -DockerImage $FullImageName" -ForegroundColor White
Write-Host ""
