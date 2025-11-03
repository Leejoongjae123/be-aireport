# Service Unavailable 오류 수정 내역

## 수정 날짜
2025-11-03

## 문제 상황
- **증상**: 로컬에서는 정상 작동하지만 EC2 서버 배포 후 `/api/reports/regenerate` 엔드포인트에서 Service Unavailable 503 에러 발생
- **요청 예시**:
  ```json
  {
    "classification": "간결하게",
    "subject": "AI보고서",
    "contents": "AI 보고서를 잘 쓰게 하는 서비스서비스서비스서비스서비스"
  }
  ```

## 근본 원인
1. **OpenAI GPT-5 모델의 긴 응답 시간**: 수 분 소요 가능
2. **타임아웃 설정 부족**: 기본 120초로는 부족
3. **로깅 부족**: 에러 발생 시 원인 파악 어려움

## 수정 내역

### 1. `services/report.py` - OpenAI 클라이언트 타임아웃 설정

**변경 전:**
```python
def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)
```

**변경 후:**
```python
def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key, timeout=300.0, max_retries=2)
```

**효과**: OpenAI API 호출 시 최대 5분(300초) 대기, 실패 시 최대 2회 재시도

### 2. `services/report.py` - 상세 로깅 추가

**추가된 로깅:**
```python
print(f"\n{'='*60}")
print(f"📝 보고서 재생성 요청")
print(f"{'='*60}")
print(f"분류: {request.classification}")
print(f"주제: {request.subject}")
print(f"내용 길이: {len(request.contents) if request.contents else 0}자")
print(f"{'='*60}\n")

print(f"🔄 OpenAI API 호출 시작 (model: gpt-5)...")
# API 호출
print(f"✅ OpenAI API 응답 완료")
print(f"✅ 재생성 완료 (소요시간: {elapsed_seconds:.2f}초)")
```

**효과**: 
- 요청 시작/종료 시점 명확히 확인 가능
- 문제 발생 구간 즉시 파악 가능
- 성능 모니터링 용이

### 3. `services/report.py` - 에러 처리 강화

**변경 전:**
```python
except Exception as e:
    elapsed_seconds = time.time() - start_time
    return RegenerateResponse(
        result="error",
        contents=f"오류가 발생했습니다: {str(e)}",
        elapsed_seconds=elapsed_seconds
    )
```

**변경 후:**
```python
except Exception as e:
    elapsed_seconds = time.time() - start_time
    error_msg = f"오류가 발생했습니다: {str(e)}"
    print(f"❌ {error_msg}")
    print(f"에러 타입: {type(e).__name__}")
    import traceback
    print(f"상세 스택:\n{traceback.format_exc()}")
    return RegenerateResponse(
        result="error",
        contents=error_msg,
        elapsed_seconds=elapsed_seconds
    )
```

**효과**: 에러 발생 시 상세한 스택 트레이스로 디버깅 용이

### 4. `Dockerfile` - Uvicorn 타임아웃 증가

**변경 전:**
```dockerfile
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info", "--timeout-keep-alive", "120"]
```

**변경 후:**
```dockerfile
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info", "--timeout-keep-alive", "300", "--timeout-graceful-shutdown", "30"]
```

**효과**: 
- keep-alive 타임아웃 120초 → 300초 증가
- graceful shutdown 타임아웃 30초 추가

### 5. `requirements.txt` - httpx 명시적 추가

**추가:**
```
httpx==0.27.0
```

**효과**: OpenAI SDK가 내부적으로 사용하는 httpx 버전 명시적 관리

## 배포 방법

```bash
# 1. Docker 이미지 빌드 및 배포
./deploy-to-ec2-hub.sh

# 2. 배포 완료 후 로그 확인
ssh -i ubuntu.pem ubuntu@54.180.120.201 'docker logs -f fastapi-app'
```

## 테스트 방법

### 1. 로컬 테스트
```bash
curl -X POST http://localhost:8000/api/reports/regenerate \
  -H "Content-Type: application/json" \
  -d '{
    "classification": "간결하게",
    "subject": "AI보고서",
    "contents": "AI 보고서를 잘 쓰게 하는 서비스서비스서비스서비스서비스"
  }'
```

### 2. 서버 테스트
```bash
curl -X POST http://54.180.120.201:8000/api/reports/regenerate \
  -H "Content-Type: application/json" \
  -d '{
    "classification": "간결하게",
    "subject": "AI보고서",
    "contents": "AI 보고서를 잘 쓰게 하는 서비스서비스서비스서비스서비스"
  }' \
  --max-time 300
```

### 3. 예상 응답
```json
{
  "result": "success",
  "contents": "간결하게 재작성된 내용...",
  "elapsed_seconds": 45.67
}
```

## 모니터링

### 로그 확인
```bash
# 실시간 로그
ssh -i ubuntu.pem ubuntu@54.180.120.201 'docker logs -f fastapi-app'

# 최근 로그
ssh -i ubuntu.pem ubuntu@54.180.120.201 'docker logs --tail 100 fastapi-app'

# 에러만 필터링
ssh -i ubuntu.pem ubuntu@54.180.120.201 'docker logs fastapi-app 2>&1 | grep "❌"'
```

### 성공 로그 예시
```
============================================================
📝 보고서 재생성 요청
============================================================
분류: 간결하게
주제: AI보고서
내용 길이: 45자
============================================================

🔄 OpenAI API 호출 시작 (model: gpt-5)...
✅ OpenAI API 응답 완료
✅ 재생성 완료 (소요시간: 67.89초)
```

### 실패 로그 예시
```
❌ 오류가 발생했습니다: Connection timeout
에러 타입: TimeoutError
상세 스택:
Traceback (most recent call last):
  ...
```

## 추가 권장사항

### 1. 프론트엔드에서 타임아웃 처리
```javascript
// 5분 타임아웃 설정
const response = await fetch('/api/reports/regenerate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data),
  signal: AbortSignal.timeout(300000) // 5분
});
```

### 2. 로딩 UI 개선
- 긴 처리 시간을 고려한 로딩 인디케이터
- 예상 소요 시간 안내 (1-3분)

### 3. 향후 개선 방향
- Celery를 활용한 비동기 처리로 전환
- WebSocket을 통한 실시간 진행 상황 전달
- 결과 캐싱으로 동일 요청 빠른 응답

## 관련 파일
- `services/report.py`: 핵심 비즈니스 로직
- `routers/reports.py`: API 엔드포인트
- `Dockerfile`: 컨테이너 설정
- `requirements.txt`: 패키지 의존성
- `TROUBLESHOOTING.md`: 상세 트러블슈팅 가이드
