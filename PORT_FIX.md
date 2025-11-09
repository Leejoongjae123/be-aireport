# Windows Docker 포트 충돌 문제 해결

## 문제 상황
```
Error response from daemon: Ports are not available: exposing port TCP 0.0.0.0:6379 -> 127.0.0.1:0: listen tcp 0.0.0.0:6379: bind: An attempt was made to access a socket in a way forbidden by its access permissions.
```

## 원인
Windows에서 특정 포트 범위가 Hyper-V 또는 다른 시스템 서비스에 의해 예약되어 있음.

### 예약된 포트 범위 확인
```powershell
netsh interface ipv4 show excludedportrange protocol=tcp
```

예시 출력:
```
시작 포트    끝 포트
----------    --------
      6363        6462
      6463        6562
      6563        6662    # 6379가 이 범위에 포함됨!
     13934       14033
```

## 해결 방법

### 1. Redis 포트 변경 (적용됨) ✅

`docker-compose.yml` 수정:
```yaml
redis:
  image: redis:7-alpine
  container_name: redis
  ports:
    - "6700:6379"  # 외부 포트를 예약 범위 밖으로 변경
```

**주의**: 컨테이너 간 통신은 여전히 `redis:6379`를 사용합니다.
- 외부(호스트)에서 접근: `localhost:6700`
- 컨테이너 내부에서 접근: `redis:6379`

### 2. 환경 변수는 변경 불필요
`REDIS_URL=redis://redis:6379/0`는 그대로 유지합니다.
이는 Docker 네트워크 내부 주소이므로 포트 매핑과 무관합니다.

## 다른 포트 충돌 시 해결 방법

### FastAPI (8000 포트)
```yaml
fastapi-app:
  ports:
    - "8001:8000"  # 외부 포트만 변경
```

### 예약된 포트 범위 해제 (관리자 권한 필요)
```powershell
# Hyper-V 동적 포트 범위 변경
netsh int ipv4 set dynamicport tcp start=49152 num=16384
netsh int ipv6 set dynamicport tcp start=49152 num=16384

# 재부팅 필요
```

**경고**: 시스템 설정을 변경하므로 신중하게 사용하세요.

## 검증

### 1. 포트 사용 확인
```powershell
netstat -ano | findstr :6700
```

### 2. 컨테이너 상태 확인
```bash
docker-compose ps
```

예상 출력:
```
NAME            STATUS                   PORTS
redis           Up (healthy)             0.0.0.0:6700->6379/tcp
fastapi-app     Up (health: starting)    0.0.0.0:8000->8000/tcp
celery-worker   Up (health: starting)    8000/tcp
```

### 3. Redis 연결 테스트
```bash
# 호스트에서
redis-cli -p 6700 ping

# 컨테이너 내부에서
docker exec -it celery-worker redis-cli -h redis -p 6379 ping
```

## 참고
- Windows 10/11에서 Hyper-V가 활성화되면 동적 포트 범위가 예약됨
- WSL2 사용 시에도 동일한 문제 발생 가능
- Docker Desktop for Windows는 Hyper-V 또는 WSL2를 사용함
