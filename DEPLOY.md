# FastAPI 애플리케이션 EC2 배포 가이드

## 📋 사전 준비사항

### 1. AWS EC2 인스턴스
- **인스턴스 타입**: t3.medium 이상 권장 (메모리 4GB+)
- **OS**: Ubuntu 22.04 LTS
- **스토리지**: 30GB 이상
- **보안 그룹 설정**:
  - SSH (22): 본인 IP
  - HTTP (8000): 0.0.0.0/0 (또는 필요한 IP만)

### 2. 로컬 환경
- Docker Desktop 설치
- Docker Hub 계정
- SSH 키 파일 (ubuntu.pem)

### 3. Docker Hub 설정
```bash
# Docker Hub 로그인
docker login
```

---

## 🚀 배포 방법 (Docker Hub 기반)

### Step 1: EC2 초기 설정

#### 1-1. EC2에 SSH 접속
```bash
ssh -i ubuntu.pem ubuntu@52.79.211.44
```

#### 1-2. 설정 스크립트 실행
```bash
# 스크립트 다운로드 (로컬에서 전송)
# 로컬 PowerShell에서:
scp -i ubuntu.pem ec2-setup.sh ubuntu@52.79.211.44:~/

# EC2에서 실행
chmod +x ec2-setup.sh
./ec2-setup.sh
```

#### 1-3. 환경 변수 설정
```bash
cd ~/multimodal-rag
nano .env

# 다음 값들을 실제 값으로 변경:
# - OPENAI_API_KEY
# - SUPABASE_URL
# - SUPABASE_KEY
# - AWS_ACCESS_KEY_ID
# - AWS_SECRET_ACCESS_KEY
# - S3_BUCKET_NAME
```

#### 1-4. 재로그인 (Docker 그룹 적용)
```bash
exit
ssh -i ubuntu.pem ubuntu@52.79.211.44
```

---

### Step 2: Docker 이미지 빌드 및 푸시

#### 2-1. build-and-push.ps1 수정
```powershell
# 파일 열기
notepad build-and-push.ps1

# DockerUsername을 본인의 Docker Hub 사용자명으로 변경
# 예: $DockerUsername = "myusername"
```

#### 2-2. 이미지 빌드 및 푸시
```powershell
# PowerShell에서 실행
.\build-and-push.ps1
```

이 명령은:
1. Docker 이미지 빌드
2. Docker Hub에 푸시
3. 약 5-10분 소요 (인터넷 속도에 따라 다름)

---

### Step 3: EC2에 배포

#### 3-1. deploy-to-ec2.ps1 수정
```powershell
# 파일 열기
notepad deploy-to-ec2.ps1

# DockerImage를 본인의 이미지로 변경
# 예: $DockerImage = "myusername/multimodal-rag:latest"
```

#### 3-2. 배포 실행
```powershell
# PowerShell에서 실행
.\deploy-to-ec2.ps1
```

이 명령은:
1. docker-compose.hub.yml과 .env 파일을 EC2로 전송
2. EC2에서 Docker Hub에서 이미지 다운로드
3. 컨테이너 시작
4. 약 2-3분 소요

---

## 🔍 배포 확인

### 1. 컨테이너 상태 확인
```bash
# EC2에서 실행
ssh -i ubuntu.pem ubuntu@52.79.211.44
cd ~/multimodal-rag
sudo docker-compose ps
```

### 2. 로그 확인
```bash
# 전체 로그
sudo docker-compose logs -f

# 특정 서비스 로그
sudo docker-compose logs -f app
sudo docker-compose logs -f celery-worker
```

### 3. API 테스트
```bash
# 헬스 체크
curl http://52.79.211.44:8000/

# 브라우저에서 API 문서 확인
# http://52.79.211.44:8000/docs
```

---

## 🔄 업데이트 방법

### 코드 변경 후 재배포

```powershell
# 1. 이미지 빌드 및 푸시
.\build-and-push.ps1

# 2. EC2에 배포
.\deploy-to-ec2.ps1
```

---

## 🛠️ 트러블슈팅

### 1. 이미지 빌드가 느린 경우
```powershell
# .dockerignore 확인
# data/, logs/, venv/ 등이 제외되어 있는지 확인
```

### 2. Docker Hub 푸시 실패
```powershell
# Docker Hub 재로그인
docker login

# 이미지 이름 확인
docker images
```

### 3. EC2에서 이미지 다운로드 실패
```bash
# EC2에서 Docker Hub 로그인 (private 이미지인 경우)
sudo docker login

# 수동으로 이미지 다운로드
sudo docker pull yourusername/multimodal-rag:latest
```

### 4. 컨테이너 시작 실패
```bash
# 로그 확인
sudo docker-compose logs

# .env 파일 확인
cat .env

# 컨테이너 재시작
sudo docker-compose restart
```

### 5. 메모리 부족
```bash
# 메모리 사용량 확인
free -h

# 스왑 메모리 확인
swapon --show

# 스왑 추가 (ec2-setup.sh에 포함됨)
```

### 6. 포트 충돌
```bash
# 포트 사용 확인
sudo lsof -i :8000

# 기존 프로세스 종료
sudo docker-compose down
```

---

## 📊 모니터링

### 리소스 사용량
```bash
# Docker 컨테이너 리소스 사용량
sudo docker stats

# 시스템 리소스
htop
```

### 로그 모니터링
```bash
# 실시간 로그
sudo docker-compose logs -f --tail=100

# 특정 시간대 로그
sudo docker-compose logs --since 1h
```

---

## 🔐 보안 권장사항

### 1. 환경 변수 관리
- `.env` 파일을 Git에 커밋하지 마세요
- EC2의 `.env` 파일 권한 설정:
  ```bash
  chmod 600 ~/multimodal-rag/.env
  ```

### 2. Docker Hub Private Repository
```bash
# Docker Hub에서 Repository를 Private으로 설정
# EC2에서 Docker Hub 로그인 필요
sudo docker login
```

### 3. 방화벽 설정
```bash
# UFW 상태 확인
sudo ufw status

# 필요한 포트만 오픈
sudo ufw allow 22/tcp
sudo ufw allow 8000/tcp
```

### 4. SSH 키 보안
```bash
# PEM 파일 권한 설정
chmod 400 ubuntu.pem
```

---

## 📝 주요 명령어 모음

### 로컬 (PowerShell)
```powershell
# 이미지 빌드 및 푸시
.\build-and-push.ps1

# EC2 배포
.\deploy-to-ec2.ps1

# EC2 접속
ssh -i ubuntu.pem ubuntu@52.79.211.44
```

### EC2 (Bash)
```bash
# 컨테이너 상태 확인
sudo docker-compose ps

# 로그 확인
sudo docker-compose logs -f

# 컨테이너 재시작
sudo docker-compose restart

# 컨테이너 중지
sudo docker-compose down

# 컨테이너 시작
sudo docker-compose up -d

# 이미지 업데이트
sudo docker pull yourusername/multimodal-rag:latest
sudo docker-compose up -d
```

---

## 🎯 배포 플로우 요약

```
로컬 개발
    ↓
코드 변경
    ↓
.\build-and-push.ps1  ← Docker 이미지 빌드 및 Docker Hub 푸시
    ↓
.\deploy-to-ec2.ps1   ← EC2에서 이미지 다운로드 및 배포
    ↓
http://52.79.211.44:8000/docs  ← API 테스트
```

---

## 💡 팁

1. **빠른 배포**: 코드 변경이 적을 때는 특정 파일만 수정하고 컨테이너 재시작
2. **로그 모니터링**: 배포 후 반드시 로그 확인
3. **백업**: 중요한 데이터는 S3나 EBS 스냅샷으로 백업
4. **자동화**: GitHub Actions로 CI/CD 파이프라인 구축 가능

---

## 🆘 문제 발생 시 체크리스트

- [ ] .env 파일이 올바르게 설정되었는가?
- [ ] Docker Hub에 이미지가 정상적으로 푸시되었는가?
- [ ] EC2 보안 그룹에서 8000 포트가 열려있는가?
- [ ] EC2에 충분한 메모리가 있는가? (free -h)
- [ ] Docker 서비스가 실행 중인가? (sudo systemctl status docker)
- [ ] 컨테이너 로그에 에러가 있는가? (sudo docker-compose logs)

---

## 📞 지원

문제가 계속되면 다음을 확인하세요:
1. 컨테이너 로그 전체 내용
2. EC2 시스템 리소스 상태
3. Docker Hub 이미지 상태
