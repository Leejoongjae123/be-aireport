# 트러블슈팅 가이드

## Service Unavailable 오류 해결

### 문제 증상
- 로컬에서는 `/regenerate` 엔드포인트가 정상 작동
- 서버 배포 후 Service Unavailable 503 에러 발생

### 원인 분석

#### 1. OpenAI API 응답 시간 초과
- `gpt-5` 모델은 응답 시간이 매우 길 수 있음 (수 분 소요 가능)
- 기본 타임아웃 설정(120초)으로는 부족

#### 2. 다층 타임아웃 문제
```
클라이언트 → 로드밸런서 → Uvicorn → FastAPI → OpenAI API
    ↓           ↓          ↓        ↓         ↓
타임아웃    타임아웃   타임아웃  타임아웃   타임아웃
```

### 적용된 해결책

#### 1. OpenAI 클라이언트 타임아웃 증가
```python
# services/report.py
OpenAI(api_key=api_key, timeout=300.0, max_retries=2)
```

#### 2. Uvicorn 타임아웃 증가
```dockerfile
# Dockerfile
CMD ["python", "-m", "uvicorn", "main:app", 
     "--timeout-keep-alive", "300",
     "--timeout-graceful-shutdown", "30"]
```

#### 3. 상세한 로깅 추가
- 요청 시작/종료 시점 로깅
- 에러 발생 시 상세 스택 트레이스 출력
- OpenAI API 호출 전후 로깅

### 로그 확인 방법

#### EC2 서버에서 로그 확인
```bash
# FastAPI 로그
ssh -i ubuntu.pem ubuntu@54.180.120.201 'docker logs -f fastapi-app'

# 최근 100줄만 확인
ssh -i ubuntu.pem ubuntu@54.180.120.201 'docker logs --tail 100 fastapi-app'

# 에러만 필터링
ssh -i ubuntu.pem ubuntu@54.180.120.201 'docker logs fastapi-app 2>&1 | grep -i error'
```

#### 로그에서 확인할 내용
```
📝 보고서 재생성 요청
============================================================
분류: 간결하게
주제: AI보고서
내용 길이: 45자
============================================================

🔄 OpenAI API 호출 시작 (model: gpt-5)...
✅ OpenAI API 응답 완료
✅ 재생성 완료 (소요시간: 123.45초)
```

### 추가 확인 사항

#### 1. 환경변수 확인
```bash
ssh -i ubuntu.pem ubuntu@54.180.120.201 'docker exec fastapi-app env | grep OPENAI'
```

#### 2. 헬스체크 확인
```bash
curl http://54.180.120.201:8000/health
```

예상 응답:
```json
{
  "status": "healthy",
  "openai_api_key_configured": true,
  "supabase_configured": true,
  "total_experts": 10
}
```

#### 3. 컨테이너 상태 확인
```bash
ssh -i ubuntu.pem ubuntu@54.180.120.201 'docker ps'
```

### 여전히 문제가 발생하는 경우

#### 1. 로드밸런서/프록시 타임아웃 확인
- Nginx, ALB 등의 타임아웃 설정 확인
- 최소 300초 이상으로 설정 필요

#### 2. OpenAI API 상태 확인
```bash
curl https://status.openai.com/
```

#### 3. 네트워크 연결 확인
```bash
ssh -i ubuntu.pem ubuntu@54.180.120.201 'docker exec fastapi-app curl -I https://api.openai.com'
```

#### 4. 메모리 부족 확인
```bash
ssh -i ubuntu.pem ubuntu@54.180.120.201 'docker stats --no-stream'
```

### 성능 최적화 권장사항

#### 1. 비동기 처리로 전환 (장기적 해결책)
현재는 동기 방식으로 처리하여 응답을 기다리지만, 
Celery 태스크로 전환하여 즉시 응답 후 백그라운드 처리 가능:

```python
# 비동기 처리 예시
@router.post("/regenerate/async")
async def regenerate_async(request: RegenerateRequest):
    task = regenerate_task.apply_async(args=[request.dict()])
    return {"task_id": task.id, "status": "processing"}
```

#### 2. 캐싱 적용
동일한 요청에 대해 캐싱 적용 고려

#### 3. 모델 변경 고려
- `gpt-5` 대신 `gpt-4o` 사용 (더 빠른 응답)
- 간단한 작업은 `gpt-4o-mini` 사용

### 배포 후 테스트

```bash
# 1. 서버 배포
./deploy-to-ec2-hub.sh

# 2. 헬스체크
curl http://54.180.120.201:8000/health

# 3. regenerate 테스트 (타임아웃 5분 설정)
curl -X POST http://54.180.120.201:8000/api/reports/regenerate \
  -H "Content-Type: application/json" \
  -d '{
    "classification": "간결하게",
    "subject": "AI보고서",
    "contents": "AI 보고서를 잘 쓰게 하는 서비스서비스서비스서비스서비스"
  }' \
  --max-time 300

# 4. 로그 확인
ssh -i ubuntu.pem ubuntu@54.180.120.201 'docker logs --tail 50 fastapi-app'
```
