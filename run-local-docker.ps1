#!/usr/bin/env pwsh
# 로컬 Docker 환경에서 실행하는 스크립트

Write-Host "================================" -ForegroundColor Cyan
Write-Host "로컬 Docker 환경 시작" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# 1. 환경 변수 확인
if (-not (Test-Path .env)) {
    Write-Host "❌ .env 파일이 없습니다." -ForegroundColor Red
    exit 1
}

# 2. Docker 이미지 빌드
Write-Host "`n🔨 Docker 이미지 빌드 중..." -ForegroundColor Yellow
docker build -t multimodal-rag:local .

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 이미지 빌드 실패" -ForegroundColor Red
    exit 1
}
Write-Host "✅ 이미지 빌드 완료" -ForegroundColor Green

# 3. 기존 컨테이너 중지 및 제거
Write-Host "`n🛑 기존 컨테이너 중지 중..." -ForegroundColor Yellow
docker-compose -f docker-compose.local.yml down 2>$null

# 4. .env 파일 로드
Write-Host "`n📝 환경 변수 로드 중..." -ForegroundColor Yellow
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        $key = $matches[1]
        $value = $matches[2]
        [Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

# 5. 컨테이너 시작
Write-Host "`n🚀 컨테이너 시작 중..." -ForegroundColor Yellow
$env:DOCKER_IMAGE = "multimodal-rag:local"
docker-compose -f docker-compose.local.yml up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 컨테이너 시작 실패" -ForegroundColor Red
    exit 1
}

# 6. 컨테이너 상태 확인
Start-Sleep -Seconds 3
Write-Host "`n📊 컨테이너 상태:" -ForegroundColor Yellow
docker-compose -f docker-compose.local.yml ps

Write-Host "`n================================" -ForegroundColor Green
Write-Host "✅ 로컬 Docker 환경 시작 완료!" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 API 접속: http://localhost:8000" -ForegroundColor Cyan
Write-Host "📚 API 문서: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "📝 유용한 명령어:" -ForegroundColor Yellow
Write-Host "  로그 확인: docker-compose -f docker-compose.local.yml logs -f" -ForegroundColor White
Write-Host "  재시작: docker-compose -f docker-compose.local.yml restart" -ForegroundColor White
Write-Host "  중지: docker-compose -f docker-compose.local.yml down" -ForegroundColor White
Write-Host ""
