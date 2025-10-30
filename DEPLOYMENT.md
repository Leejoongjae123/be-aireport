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
- SSH 키 파일 (ubuntu.pem)

---

## 🚀 배포 방법

### 방법 1: 자동 배포 스크립트 사용 (권장)

#### Step 1: EC2 초기 설정
```bash
# EC2에 SSH 접속
ssh -i ubuntu.pem ubuntu@your-ec2-ip

# 설정 스크립트 업로드 및 실행
# 로컬에서 스크립트 전송
scp -i ubuntu.pem ec2-setup.sh ubuntu@your-ec2-ip:~/

# EC2에서 실행
ssh -i ubuntu.pem ubuntu@your-ec2-ip
bash ec2-setup.sh

# 환경 변수 설정
nano ~/.env
# OPENAI_API_KEY를 실제 값으로 변경

# 재로그인
exit
ssh -i ubuntu.pem ubuntu@your-ec2-ip
```

#### Step 2: 로컬에서 배포 실행
```bash
# deploy-to-ec2.sh 파일 수정
nano deploy-to-ec2.sh
# EC2_HOST를 실제 EC2 IP로 변경

# 실행 권한 부여
chmod +x deploy-to-ec2.sh
chmod +x ec2-setup.sh

# 배포 실행
./deploy-to-ec2.sh
```

---

### 방법 2: Docker Compose 사용 (로컬 테스트)

```bash
# 환경 변수 파일 생성
cp .env.example .env
nano .env  # 실제 값으로 수정

# Docker Compose로 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 중지
docker-compose down
```

---

### 방법 3: 수동 배포

#### Step 1: 로컬에서 Docker 이미지 빌드
```bash
# Docker 이미지 빌드
docker build -t fastapi-app:latest .

# 로컬 테스트
docker run -d -p 8000:8000 --env-file .env fastapi-app:latest

# 브라우저에서 확인
# http://localhost:8000/docs
```

#### Step 2: EC2로 이미지 전송
```bash
# 이미지 저장 및 전송
docker save fastapi-app:latest | gzip | ssh -i ubuntu.pem ubuntu@your-ec2-ip 'gunzip | docker load'
```

#### Step 3: EC2에서 실행
```bash
# EC2에 SSH 접속
ssh -i ubuntu.pem ubuntu@your-ec2-ip

# 환경 변수 로드
source ~/.env

# 컨테이너 실행
docker run -d \
  --name fastapi-app \
  -p 8000:8000 \
  -e OPENAI_API_KEY="${OPENAI_API_KEY}" \
  -e SUPABASE_URL="${SUPABASE_URL}" \
  -e SUPABASE_KEY="${SUPABASE_KEY}" \
  --restart unless-stopped \
  fastapi-app:latest
```

---

## 🔍 배포 확인

### 1. 컨테이너 상태 확인
```bash
# EC2에서 실행
docker ps
docker logs fastapi-app
docker logs -f fastapi-app  # 실시간 로그
```

### 2. API 테스트
```bash
# 헬스 체크
curl http://your-ec2-ip:8000/health

# API 문서 확인
# 브라우저: http://your-ec2-ip:8000/docs
```

---

## 🔄 업데이트 방법

### 자동 배포 스크립트 사용
```bash
# 로컬에서
./deploy-to-ec2.sh
```

### 수동 업데이트
```bash
# 1. 새 이미지 빌드
docker build -t fastapi-app:latest .

# 2. EC2로 전송
docker save fastapi-app:latest | gzip | ssh -i ubuntu.pem ubuntu@your-ec2-ip 'gunzip | docker load'

# 3. EC2에서 컨테이너 재시작
ssh -i ubuntu.pem ubuntu@your-ec2-ip << 'EOF'
docker stop fastapi-app
docker rm fastapi-app
source ~/.env
docker run -d --name fastapi-app -p 8000:8000 \
  -e OPENAI_API_KEY="${OPENAI_API_KEY}" \
  -e SUPABASE_URL="${SUPABASE_URL}" \
  -e SUPABASE_KEY="${SUPABASE_KEY}" \
  --restart unless-stopped \
  fastapi-app:latest
EOF
```

---

## 🛠️ 트러블슈팅

### 1. 포트가 이미 사용 중
```bash
# 포트 사용 프로세스 확인
sudo lsof -i :8000

# 기존 컨테이너 중지
docker stop fastapi-app
docker rm fastapi-app
```

### 2. 메모리 부족
```bash
# 메모리 사용량 확인
free -h

# 스왑 메모리 추가 (ec2-setup.sh에 포함됨)
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 3. 로그 확인
```bash
# 컨테이너 로그
docker logs -f fastapi-app
docker logs --tail 100 fastapi-app

# 시스템 로그
journalctl -u docker -f
```

### 4. 환경 변수 문제
```bash
# EC2에서 환경 변수 확인
cat ~/.env

# 컨테이너 내부 환경 변수 확인
docker exec fastapi-app env | grep OPENAI
```

---

## 🔐 보안 권장사항

1. **환경 변수 관리**
   - `.env` 파일을 Git에 커밋하지 마세요
   - `.env.example`만 커밋하세요
   - AWS Secrets Manager 사용 권장

2. **HTTPS 설정**
   - Nginx 리버스 프록시 + Let's Encrypt 사용
   - 또는 AWS Application Load Balancer 사용

3. **방화벽 설정**
   - 필요한 포트만 오픈
   - SSH는 본인 IP만 허용

4. **정기 업데이트**
   ```bash
   sudo apt-get update && sudo apt-get upgrade -y
   ```

---

## 📊 모니터링

### Docker Stats
```bash
docker stats fastapi-app
```

### 로그 모니터링
```bash
docker logs -f --tail 100 fastapi-app
```

### 리소스 사용량 확인
```bash
# 메모리
free -h

# 디스크
df -h

# CPU
top
```

---

## 🆘 문제 발생 시

1. **컨테이너 재시작**
   ```bash
   docker restart fastapi-app
   ```

2. **완전 재배포**
   ```bash
   docker stop fastapi-app
   docker rm fastapi-app
   docker rmi fastapi-app:latest
   # 그 다음 재배포
   ```

3. **EC2 인스턴스 재부팅**
   ```bash
   sudo reboot
   ```

4. **Docker 서비스 재시작**
   ```bash
   sudo systemctl restart docker
   ```

---

## 📝 유용한 명령어

```bash
# 모든 컨테이너 확인
docker ps -a

# 컨테이너 내부 접속
docker exec -it fastapi-app bash

# 이미지 목록
docker images

# 사용하지 않는 리소스 정리
docker system prune -af

# 특정 컨테이너 로그 저장
docker logs fastapi-app > app.log 2>&1
```

---

## 🎯 체크리스트

배포 전:
- [ ] EC2 인스턴스 생성 및 보안 그룹 설정
- [ ] SSH 키 파일 준비
- [ ] 로컬에 Docker 설치
- [ ] `.env` 파일 설정

배포 후:
- [ ] 헬스 체크 확인
- [ ] API 문서 접속 확인
- [ ] 로그 확인
- [ ] 리소스 사용량 모니터링

---

## 📞 지원

문제가 발생하면 다음을 확인하세요:
1. EC2 보안 그룹 설정
2. Docker 로그
3. 환경 변수 설정
4. 네트워크 연결 상태
