# 사업계획서 생성 API 문서

## 개요

사업계획서 생성, 진단, 전문가 매칭을 위한 통합 FastAPI 서버입니다.

- **버전**: 2.0.0
- **모델**: GPT-5 (Responses API)
- **문서**: `/docs` (Swagger UI)

---

## 목차

1. [시스템 엔드포인트](#1-시스템-엔드포인트)
2. [진단 API](#2-진단-api)
3. [전문가 매칭 API](#3-전문가-매칭-api)
4. [보고서 생성 및 관리 API](#4-보고서-생성-및-관리-api)
5. [작업 상태 관리 API](#5-작업-상태-관리-api)

---

## 1. 시스템 엔드포인트

### 1.1 루트 정보 조회

**Endpoint**: `GET /`

**설명**: API 전체 구조 및 사용 가능한 엔드포인트 목록을 반환합니다.

**Response**:
```json
{
  "message": "사업계획서 생성 및 전문가 매칭 API 서버",
  "version": "2.0.0",
  "model": "GPT-5 (Responses API)",
  "api_structure": {
    "diagnosis": { ... },
    "expert": { ... },
    "reports": { ... }
  },
  "documentation": "/docs"
}
```

---

### 1.2 헬스 체크

**Endpoint**: `GET /health`

**설명**: 시스템 상태 및 설정을 확인합니다.

**Response**:
```json
{
  "status": "healthy",
  "openai_api_key_configured": true,
  "supabase_configured": true,
  "total_experts": 50
}
```

---

## 2. 진단 API

### 2.1 사업계획서 진단 및 평가

**Endpoint**: `POST /api/diagnosis/`

**설명**: 사업계획서 콘텐츠를 5개 카테고리 30개 항목으로 평가하고 점수를 산출합니다.

**Request Body**:
```json
{
  "input": [
    {
      "contents": "AI 기반 헬스케어 솔루션 사업계획서 내용..."
    }
  ],
  "evaluation": [
    {
      "id": 1,
      "카테고리": "기술성",
      "평가항목": [
        {
          "id": 1,
          "내용": "핵심 기술의 독창성 및 차별성"
        }
      ]
    }
  ]
}
```

**Parameters**:
- `input` (required): 평가할 콘텐츠 리스트
  - `contents` (optional): 평가할 텍스트 내용
  - `query` (optional): 평가 쿼리
- `evaluation` (optional): 커스텀 평가 기준 (미제공 시 기본 평가 기준 사용)

**Response**:
```json
{
  "categories": [
    {
      "id": 1,
      "name": "기술성",
      "items": [
        {
          "id": 1,
          "title": "핵심 기술의 독창성 및 차별성",
          "score": 85
        },
        {
          "id": 2,
          "title": "기술 성숙도(TRL) 및 적용 가능성",
          "score": 78
        }
      ]
    },
    {
      "id": 2,
      "name": "사업성",
      "items": [ ... ]
    }
  ],
  "score_average": 75.5
}
```

**기본 평가 카테고리**:
1. **기술성** (6개 항목)
2. **사업성** (6개 항목)
3. **공공성·정책 부합성** (6개 항목)
4. **성과·기대효과** (6개 항목)
5. **추진체계 및 역량** (6개 항목)

---

### 2.2 기본 평가 기준 조회

**Endpoint**: `GET /api/diagnosis/criteria`

**설명**: 기본 평가 기준 30개 항목을 조회합니다.

**Response**:
```json
{
  "total_categories": 5,
  "total_items": 30,
  "criteria": [
    {
      "id": 1,
      "카테고리": "기술성",
      "평가항목": [
        {
          "id": 1,
          "내용": "핵심 기술의 독창성 및 차별성"
        },
        {
          "id": 2,
          "내용": "기술 성숙도(TRL) 및 적용 가능성"
        }
      ]
    }
  ]
}
```

---

## 3. 전문가 매칭 API

### 3.1 전문가 매칭

**Endpoint**: `POST /api/expert/match`

**설명**: 사업보고서 내용을 기반으로 키워드를 추출하고 전문가를 매칭합니다.

**Request Body**:
```json
{
  "business_report": "AI 기반 헬스케어 솔루션 사업계획서...",
  "num_keywords": 10,
  "top_k": 10,
  "similarity_threshold": 0.5
}
```

**Parameters**:
- `business_report` (required): 사업보고서 내용
- `num_keywords` (optional, default: 10): 추출할 키워드 개수 (1-10)
- `top_k` (optional, default: 10): 반환할 상위 전문가 수 (1-50)
- `similarity_threshold` (optional, default: 0.5): 유사도 임계값 (0.0-1.0)

**Response**:
```json
{
  "keywords": ["AI", "헬스케어", "디지털전환", "데이터분석", "의료"],
  "matching_method": "semantic_count",
  "similarity_threshold": 0.5,
  "total_experts_evaluated": 50,
  "final_ranking": [
    {
      "순위": 1,
      "이름": "홍길동",
      "경력": ["AI 연구소 선임연구원", "헬스케어 스타트업 CTO"],
      "분야": ["인공지능", "헬스케어", "데이터분석"],
      "경력파일명": "홍길동_경력.pdf",
      "매칭_개수": 15,
      "매칭_상세": [
        {
          "keyword": "AI",
          "matched_item": "인공지능",
          "similarity": 0.92
        },
        {
          "keyword": "헬스케어",
          "matched_item": "헬스케어",
          "similarity": 1.0
        }
      ]
    }
  ]
}
```

---

### 3.2 전체 전문가 목록 조회

**Endpoint**: `GET /api/expert/list`

**설명**: 시스템에 등록된 모든 전문가의 정보를 반환합니다.

**Response**:
```json
{
  "total_count": 50,
  "experts": [
    {
      "id": 1,
      "name": "홍길동",
      "career": ["AI 연구소 선임연구원", "헬스케어 스타트업 CTO"],
      "field": ["인공지능", "헬스케어", "데이터분석"],
      "career_file_name": "홍길동_경력.pdf",
      "is_visible": true
    }
  ]
}
```

---

### 3.3 특정 전문가 정보 조회

**Endpoint**: `GET /api/expert/{expert_name}`

**설명**: 전문가 이름으로 상세 정보를 조회합니다.

**Path Parameters**:
- `expert_name` (required): 전문가 이름

**Response**:
```json
{
  "id": 1,
  "name": "홍길동",
  "career": ["AI 연구소 선임연구원", "헬스케어 스타트업 CTO"],
  "field": ["인공지능", "헬스케어", "데이터분석"],
  "career_file_name": "홍길동_경력.pdf",
  "is_visible": true
}
```

**Error Response** (404):
```json
{
  "detail": "전문가 '홍길동'을(를) 찾을 수 없습니다."
}
```

---

## 4. 보고서 생성 및 관리 API

### 4.1 전체 보고서 생성 (비동기)

**Endpoint**: `POST /api/reports/generate`

**설명**: 전체 사업계획서를 백그라운드에서 비동기로 생성합니다. 즉시 응답을 반환하며, Supabase에서 진행 상황을 확인할 수 있습니다.

**Request Body**:
```json
{
  "business_idea": "AI 기반 헬스케어 솔루션",
  "core_value": "개인 맞춤형 건강 관리",
  "file_name": "강소기업1.pdf",
  "report_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Parameters**:
- `business_idea` (required): 사업 아이디어
- `core_value` (required): 핵심 가치
- `file_name` (required): 참고 PDF 파일명 (예: 강소기업1.pdf)
- `report_id` (required): Supabase report_create 테이블의 UUID

**Response**:
```json
{
  "success": true,
  "message": "generation started (task_id: abc123-task-id)",
  "report_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**처리 과정**:
1. Celery 태스크로 백그라운드에서 모든 섹션 순차 생성
2. 각 섹션을 `report_sections` 테이블에 개별 저장
3. 완료 시 `report_create` 테이블의 `is_complete` = `true`로 업데이트
4. `/api/jobs/status/{task_id}`로 작업 상태 확인 가능

**작업 상태 확인**:
```bash
# 반환된 task_id로 작업 상태 조회
GET /api/jobs/status/abc123-task-id
```

---

### 4.2 보고서 재생성 (비동기)

**Endpoint**: `POST /api/reports/regenerate`

**설명**: 기존 보고서 내용을 다양한 스타일로 재생성하거나 추가 정보를 검색합니다. Celery를 통해 백그라운드에서 비동기로 처리됩니다.

**Request Body**:

**스타일 변경 (자세히/간결하게/윤문)**:
```json
{
  "classification": "자세히",
  "contents": "원본 내용..."
}
```

**추가 정보 검색 (특허/뉴스)**:
```json
{
  "classification": "특허",
  "subject": "AI 헬스케어"
}
```

**Parameters**:
- `classification` (required): 재생성 분류
  - `"자세히"`: 내용 보강 (글자수 20% 증가)
  - `"간결하게"`: 핵심 요약 (글자수 20% 감소)
  - `"윤문"`: 문장 다듬기
  - `"특허"`: 관련 특허 검색 (2020년 이후)
  - `"뉴스"`: 최신 뉴스 검색
- `contents` (optional): 원본 내용 (자세히/간결하게/윤문 시 필수)
- `subject` (optional): 검색 주제 (특허/뉴스 시 필수)

**Response**:
```json
{
  "success": true,
  "message": "regeneration started (task_id: xyz789-task-id)",
  "task_id": "xyz789-task-id"
}
```

**처리 과정**:
1. Celery 태스크로 백그라운드에서 재생성 작업 시작
2. 즉시 task_id를 반환하여 클라이언트가 작업 상태를 추적할 수 있도록 함
3. `/api/jobs/status/{task_id}`로 작업 진행 상황 및 결과 확인

**작업 상태 확인**:
```bash
# 반환된 task_id로 작업 상태 조회
GET /api/jobs/status/xyz789-task-id
```

---

### 4.3 보고서 유사도 검색

**Endpoint**: `POST /api/reports/search`

**설명**: 사업아이디어와 핵심가치를 기반으로 유사한 보고서를 검색합니다.

**Request Body**:
```json
{
  "business_idea": "AI 기반 헬스케어 솔루션",
  "core_value": "개인 맞춤형 건강 관리",
  "category_number": 1,
  "top_k": 5
}
```

**Parameters**:
- `business_idea` (required): 사업 아이디어
- `core_value` (required): 핵심 가치
- `category_number` (required): 분야 번호 (1-5)
- `top_k` (optional, default: 5): 반환할 결과 개수 (1-20)

**Response**:
```json
{
  "success": true,
  "query": "사업아이디어: AI 기반 헬스케어 솔루션\n핵심가치제안: 개인 맞춤형 건강 관리",
  "category_number": 1,
  "total_found": 5,
  "results": [
    {
      "id": 1,
      "number": 101,
      "title": "AI 기반 개인 맞춤형 건강관리 플랫폼",
      "field": "헬스케어",
      "keywords": "AI, 헬스케어, 개인화, 데이터분석",
      "file_name": "강소기업1.pdf",
      "category_number": 1,
      "similarity": 0.92
    }
  ]
}
```

---

### 4.4 보고서 멀티모달 임베딩 처리

**Endpoint**: `POST /api/reports/embed`

**설명**: S3에 저장된 PDF 파일을 다운로드하여 멀티모달 임베딩 처리를 수행합니다.

**Request Body**:
```json
{
  "file_name": "강소기업1.pdf",
  "embed_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Parameters**:
- `file_name` (required): S3에 저장된 PDF 파일명
- `embed_id` (required): Supabase report_embed 테이블의 ID

**Response**:
```json
{
  "success": true,
  "message": "embedding started (task_id: def456-task-id)",
  "embed_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**처리 과정**:
1. Celery 태스크로 백그라운드에서 처리 시작
2. S3에서 PDF 파일 다운로드
3. `data/{파일명_확장자제거}/` 폴더에 저장
4. PDF 파싱 및 멀티모달 임베딩 (텍스트, 테이블, 이미지)
5. `output` 폴더에 JSON 결과 저장
6. `report_embed` 테이블의 `is_completed` = `true`로 업데이트
7. `/api/jobs/status/{task_id}`로 작업 상태 확인 가능

**작업 상태 확인**:
```bash
# 반환된 task_id로 작업 상태 조회
GET /api/jobs/status/def456-task-id
```

---

### 4.5 파일 S3 업로드

**Endpoint**: `POST /api/reports/upload`

**설명**: 클라이언트에서 파일을 직접 업로드하여 S3에 저장합니다. S3에 동일한 파일명이 이미 존재하는 경우 업로드가 거부됩니다.

**Request**:
- **Content-Type**: `multipart/form-data`
- **Form field name**: `file`
- **파일**: PDF 파일 등

**cURL 예시**:
```bash
curl -X POST "http://localhost:8000/api/reports/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@강소기업1.pdf"
```

**성공 Response**:
```json
{
  "success": true,
  "message": "파일이 성공적으로 업로드되었습니다.",
  "file_name": "강소기업1.pdf",
  "s3_url": "https://bucket-name.s3.ap-northeast-2.amazonaws.com/강소기업1.pdf"
}
```

**실패 Response (중복 파일)**:
```json
{
  "success": false,
  "message": "S3에 이미 동일한 파일명(강소기업1.pdf)이 존재합니다.",
  "file_name": "강소기업1.pdf",
  "s3_url": null
}
```

**주의사항**:
- S3에 동일한 파일명이 존재하면 업로드가 거부됩니다
- 파일을 덮어쓰려면 기존 파일을 먼저 삭제해야 합니다

---

## 5. 작업 상태 관리 API

### 5.1 작업 상태 조회

**Endpoint**: `GET /api/jobs/status/{task_id}`

**설명**: Celery 태스크의 현재 상태를 조회합니다.

**Path Parameters**:
- `task_id` (required): Celery 태스크 ID

**Response**:
```json
{
  "task_id": "abc123-task-id",
  "status": "PROGRESS",
  "result": null,
  "error": null,
  "meta": {
    "status": "보고서 생성 중...",
    "report_id": "550e8400-e29b-41d4-a716-446655440000",
    "current": 50,
    "total": 100
  }
}
```

**작업 상태**:
- `PENDING`: 작업이 대기 중
- `STARTED`: 작업이 시작됨
- `PROGRESS`: 작업이 진행 중
- `SUCCESS`: 작업이 성공적으로 완료됨
- `FAILURE`: 작업이 실패함
- `RETRY`: 작업이 재시도 중

---

### 5.2 작업 목록 조회

**Endpoint**: `GET /api/jobs/list`

**설명**: 현재 실행 중이거나 예약된 작업 목록을 조회합니다.

**Response**:
```json
{
  "active": [
    {
      "worker": "celery@worker1",
      "task_id": "abc123-task-id",
      "name": "tasks.report_tasks.generate_report_task",
      "args": ["AI 기반 헬스케어", "개인 맞춤형", "강소기업1.pdf", "uuid"],
      "kwargs": {}
    }
  ],
  "scheduled": [],
  "reserved": []
}
```

---

### 5.3 작업 취소

**Endpoint**: `DELETE /api/jobs/cancel/{task_id}`

**설명**: 실행 중인 작업을 취소합니다.

**Path Parameters**:
- `task_id` (required): Celery 태스크 ID

**Response**:
```json
{
  "success": true,
  "message": "작업 취소 요청이 전송되었습니다.",
  "task_id": "abc123-task-id"
}
```

**주의사항**:
- 이미 시작된 작업은 즉시 중단되지 않을 수 있습니다
- 작업이 완료된 후에는 취소할 수 없습니다

---

## 환경 변수 설정

프로젝트 실행을 위해 다음 환경 변수를 설정해야 합니다:

```env
# OpenAI API
OPENAI_API_KEY=your_openai_api_key

# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# AWS S3
NEXT_PUBLIC_S3_ACCESS_KEY=your_s3_access_key
NEXT_PUBLIC_S3_SECRET_KEY=your_s3_secret_key
NEXT_PUBLIC_S3_REGION=ap-northeast-2
AWS_S3_BUCKET_NAME=your_bucket_name
AWS_REGION=ap-northeast-2

# Redis (Celery)
REDIS_URL=redis://localhost:6379/0
```

---

## 실행 방법

### 로컬 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# Redis 서버 실행 (별도 터미널)
redis-server

# Celery 워커 실행 (별도 터미널)
celery -A celery_worker worker --loglevel=info --concurrency=2 -Q report_generation,report_embedding

# FastAPI 서버 실행
python main.py
```

서버는 `http://localhost:8000`에서 실행됩니다.

### Docker 실행

```bash
# Docker 이미지 빌드
docker build -t report-api .

# Docker 컨테이너 실행
docker run -p 8000:8000 --env-file .env report-api
```

### Docker Compose 실행 (권장)

```bash
# 모든 서비스 시작 (FastAPI, Redis, Celery Worker)
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 서비스 중지
docker-compose down
```

**실행되는 서비스**:
- `redis`: Redis 서버 (포트 6379)
- `fastapi-app`: FastAPI 애플리케이션 (포트 8000)
- `celery-worker`: Celery 워커 (백그라운드 작업 처리)

---

## API 문서 접근

서버 실행 후 다음 URL에서 인터랙티브 API 문서를 확인할 수 있습니다:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

---

## 에러 코드

| 상태 코드 | 설명 |
|---------|------|
| 200 | 성공 |
| 400 | 잘못된 요청 (필수 파라미터 누락 등) |
| 404 | 리소스를 찾을 수 없음 |
| 500 | 서버 내부 오류 (API 키 미설정 등) |
| 502 | 외부 서비스 오류 (모델 응답 파싱 실패 등) |

---

## 주요 기능

### 1. 사업계획서 진단
- 5개 카테고리 30개 항목 기반 자동 평가
- GPT-5 모델을 활용한 정량적 점수 산출
- 커스터마이징 가능한 평가 기준

### 2. 전문가 매칭
- 사업보고서 기반 키워드 자동 추출
- 의미적 유사도 기반 전문가 매칭
- 임계값 조정 가능한 유연한 매칭 시스템

### 3. 보고서 생성
- 참고 자료 기반 자동 보고서 생성
- 섹션별 개별 생성 및 관리
- Celery 기반 비동기 처리로 빠른 응답
- Redis를 통한 안정적인 작업 큐 관리

### 4. 보고서 관리
- 다양한 스타일 재생성 (자세히/간결하게/윤문)
- 특허/뉴스 검색 기능
- 벡터 임베딩 기반 유사도 검색
- S3 연동 파일 업로드/다운로드

### 5. 백그라운드 작업 관리
- Celery와 Redis 기반 분산 작업 처리
- 서버 재시작 시에도 작업 유지
- 실시간 작업 상태 조회
- 작업 취소 및 재시도 기능

---

## 프론트엔드 개발 가이드

### Celery 비동기 작업 처리 방법

프론트엔드에서 Celery 기반 비동기 작업을 처리하는 방법을 안내합니다.

---

#### 1. 보고서 재생성 (`/api/reports/regenerate`)

**Step 1: 재생성 작업 시작**

**Endpoint**: `POST /api/reports/regenerate`

**Request Body**:
```json
{
  "classification": "자세히",
  "contents": "원본 보고서 내용..."
}
```

**Response**:
```json
{
  "success": true,
  "message": "regeneration started (task_id: xyz789-task-id)",
  "task_id": "xyz789-task-id"
}
```

**Step 2: 작업 상태 조회 (폴링)**

**Endpoint**: `GET /api/jobs/status/{task_id}`

**Response (진행 중)**:
```json
{
  "task_id": "xyz789-task-id",
  "status": "PROGRESS",
  "result": null,
  "error": null,
  "meta": {
    "status": "재생성 중..."
  }
}
```

**Response (완료)**:
```json
{
  "task_id": "xyz789-task-id",
  "status": "SUCCESS",
  "result": {
    "result": "success",
    "contents": "재생성된 보고서 내용...",
    "elapsed_seconds": 3.5
  },
  "error": null,
  "meta": {
    "status": "작업이 완료되었습니다.",
    "success": true
  }
}
```

**Response (실패)**:
```json
{
  "task_id": "xyz789-task-id",
  "status": "FAILURE",
  "result": null,
  "error": "오류 메시지",
  "meta": {
    "status": "작업이 실패했습니다."
  }
}
```

**처리 플로우**:
1. `/api/reports/regenerate`로 POST 요청하여 `task_id` 받기
2. 5초마다 `/api/jobs/status/{task_id}`로 GET 요청하여 상태 확인
3. `status`가 `SUCCESS`이면 `result.contents`에서 결과 추출
4. `status`가 `FAILURE`이면 `error` 메시지 표시
5. `status`가 `PENDING`, `STARTED`, `PROGRESS`이면 계속 폴링

---

#### 2. 보고서 전체 생성 (`/api/reports/generate`)

**Step 1: 생성 작업 시작**

**Endpoint**: `POST /api/reports/generate`

**Request Body**:
```json
{
  "business_idea": "AI 기반 헬스케어 솔루션",
  "core_value": "개인 맞춤형 건강 관리",
  "file_name": "강소기업1.pdf",
  "report_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response**:
```json
{
  "success": true,
  "message": "generation started (task_id: abc123-task-id)",
  "report_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Step 2: 작업 상태 조회 (폴링)**

**Endpoint**: `GET /api/jobs/status/abc123-task-id`

**Response (진행 중)**:
```json
{
  "task_id": "abc123-task-id",
  "status": "PROGRESS",
  "result": null,
  "error": null,
  "meta": {
    "status": "보고서 생성 중...",
    "report_id": "550e8400-e29b-41d4-a716-446655440000",
    "current": 50,
    "total": 100
  }
}
```

**Response (완료)**:
```json
{
  "task_id": "abc123-task-id",
  "status": "SUCCESS",
  "result": {
    "success": true,
    "message": "보고서 생성 완료",
    "report_id": "550e8400-e29b-41d4-a716-446655440000"
  },
  "error": null,
  "meta": {
    "status": "작업이 완료되었습니다.",
    "success": true
  }
}
```

**처리 플로우**:
1. `/api/reports/generate`로 POST 요청하여 `task_id` 받기
2. 5초마다 `/api/jobs/status/{task_id}`로 상태 확인
3. `status`가 `SUCCESS`이면 Supabase `report_create` 테이블에서 생성된 보고서 조회
4. `meta.current`와 `meta.total`로 진행률 표시 가능

---

#### 3. 보고서 임베딩 처리 (`/api/reports/embed`)

**Step 1: 임베딩 작업 시작**

**Endpoint**: `POST /api/reports/embed`

**Request Body**:
```json
{
  "file_name": "강소기업1.pdf",
  "embed_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response**:
```json
{
  "success": true,
  "message": "embedding started (task_id: def456-task-id)",
  "embed_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Step 2: 작업 상태 조회 (폴링)**

**Endpoint**: `GET /api/jobs/status/def456-task-id`

**Response (완료)**:
```json
{
  "task_id": "def456-task-id",
  "status": "SUCCESS",
  "result": {
    "success": true,
    "message": "임베딩 완료",
    "embed_id": "550e8400-e29b-41d4-a716-446655440000"
  },
  "error": null,
  "meta": {
    "status": "작업이 완료되었습니다.",
    "success": true
  }
}
```

**처리 플로우**:
1. `/api/reports/embed`로 POST 요청하여 `task_id` 받기
2. 5초마다 `/api/jobs/status/{task_id}`로 상태 확인
3. `status`가 `SUCCESS`이면 Supabase `report_embed` 테이블에서 `is_completed` 확인

---

#### 4. 작업 상태 종류

| 상태 | 설명 | 다음 액션 |
|------|------|----------|
| `PENDING` | 작업이 대기 중 | 계속 폴링 (5초 후 재시도) |
| `STARTED` | 작업이 시작됨 | 계속 폴링 (5초 후 재시도) |
| `PROGRESS` | 작업이 진행 중 | 계속 폴링, `meta` 필드에서 진행 상황 확인 가능 |
| `SUCCESS` | 작업이 완료됨 | `result` 필드에서 최종 결과 추출 |
| `FAILURE` | 작업이 실패함 | `error` 필드에서 오류 메시지 확인 |
| `RETRY` | 작업이 재시도 중 | 계속 폴링 (5초 후 재시도) |

---

#### 5. 권장 구현 방법

**폴링 설정**:
- **폴링 간격**: 5초 (서버 부하와 UX 균형)
- **최대 시도 횟수**: 60회 (총 5분)
- **타임아웃**: 작업 유형에 따라 3-10분 설정

**에러 처리**:
- 네트워크 오류 시 재시도 로직 구현
- `FAILURE` 상태 시 사용자에게 명확한 오류 메시지 표시

**UI 피드백**:
- 로딩 스피너 또는 프로그레스 바 표시
- `PROGRESS` 상태의 `meta` 필드를 활용하여 진행률 표시
- 예상 소요 시간 안내

**작업 취소**:
- 필요시 `DELETE /api/jobs/cancel/{task_id}` 호출
- 단, 이미 시작된 작업은 즉시 중단되지 않을 수 있음

---

## 라이선스

이 프로젝트는 내부 사용을 위한 것입니다.
