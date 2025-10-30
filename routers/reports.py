"""
보고서 생성 및 관리 API 라우터

사업계획서 생성, 검색, 재생성 기능을 제공합니다.
"""

from fastapi import APIRouter, BackgroundTasks, UploadFile, File
from services.report import (
    GenerateBackgroundRequest,
    GenerateBackgroundResponse,
    GenerateReportRequest,
    GenerateReportResponse,
    SearchRequest,
    SearchResponse,
    RegenerateRequest,
    RegenerateResponse,
    GenerateStartResponse,
    EmbedReportRequest,
    EmbedReportResponse,
    UploadReportResponse,
    generate_background,
    generate_report,
    generate_start,
    report_regenerate,
    search_reports,
    embed_report_start,
    upload_report
)


router = APIRouter(
    prefix="/api/reports",
    tags=["Reports"],
    responses={404: {"description": "Not found"}},
)


# @router.post("/generate/background", response_model=GenerateBackgroundResponse)
# async def generate_background_endpoint(request: GenerateBackgroundRequest):
#     """
#     사업계획서 섹션 컨텐츠 생성 (단일 섹션)
    
#     **주요 기능:**
#     - subsection_id 기반 동적 컨텐츠 생성
#     - 참고 데이터(JSON) 기반 스타일 학습
#     - GPT-5 모델 활용
#     - HTML 형식 출력
    
#     **사용 예시:**
#     ```json
#     {
#         "business_idea": "AI 기반 헬스케어 솔루션",
#         "core_value": "개인 맞춤형 건강 관리",
#         "subsection_id": "1.1",
#         "subsection_name": "추진 배경 및 필요성"
#     }
#     ```
    
#     Args:
#         request: 섹션 생성 요청 데이터
        
#     Returns:
#         생성된 섹션 컨텐츠 및 메타데이터
#     """
#     return await generate_background(request)


# @router.post("/generate/full", response_model=GenerateReportResponse)
# async def generate_report_endpoint(request: GenerateReportRequest):
#     """
#     전체 사업계획서 자동 생성 (동기 처리)
    
#     **주요 기능:**
#     - 모든 섹션 순차 생성
#     - Supabase에 자동 저장
#     - 진행 상황 실시간 반환
    
#     **주의:**
#     - 동기 처리 방식으로 응답까지 시간이 소요됨
#     - 빠른 응답이 필요한 경우 /generate/async 사용 권장
    
#     Args:
#         request: 전체 보고서 생성 요청
        
#     Returns:
#         생성 완료 상태 및 결과
#     """
#     return await generate_report(request)


@router.post("/generate", response_model=GenerateStartResponse)
async def generate_async_endpoint(background_tasks: BackgroundTasks, request: GenerateReportRequest):
    """
    전체 사업계획서 생성 (백그라운드 비동기 처리)
    
    **주요 기능:**
    - 즉시 성공 응답 반환
    - 백그라운드에서 보고서 생성
    - Supabase에서 진행 상황 확인 가능
    
    **권장 사용 시나리오:**
    - 프론트엔드에서 빠른 응답 필요
    - 긴 작업 시간이 예상되는 경우
    
    Args:
        background_tasks: FastAPI 백그라운드 태스크
        request: 전체 보고서 생성 요청
        
    Returns:
        생성 시작 확인 메시지
    """
    return await generate_start(background_tasks, request)


@router.post("/regenerate", response_model=RegenerateResponse)
async def regenerate_endpoint(request: RegenerateRequest):
    """
    보고서 재생성 (스타일 변경 및 추가 정보)
    
    **지원 분류:**
    - **자세히**: 내용 보강 (글자수 20% 증가)
    - **간결하게**: 핵심 요약 (글자수 20% 감소)
    - **윤문**: 문장 다듬기
    - **특허**: 관련 특허 검색 (2020년 이후)
    - **뉴스**: 최신 뉴스 검색
    
    **사용 예시:**
    ```json
    {
        "classification": "자세히",
        "contents": "원본 내용..."
    }
    ```
    
    Args:
        request: 재생성 요청
        
    Returns:
        재생성된 컨텐츠
    """
    return await report_regenerate(request)


@router.post("/search", response_model=SearchResponse)
async def search_reports_endpoint(request: SearchRequest):
    """
    보고서 유사도 검색
    
    **주요 기능:**
    - 사업아이디어 기반 벡터 임베딩 생성
    - 분야번호별 유사도 검색
    - Top-K 결과 반환
    
    **사용 예시:**
    ```json
    {
        "business_idea": "AI 기반 헬스케어 솔루션",
        "core_value": "개인 맞춤형 건강 관리",
        "category_number": 1,
        "top_k": 5
    }
    ```
    
    Args:
        request: 검색 요청
        
    Returns:
        유사도 기준 정렬된 보고서 목록
    """
    return await search_reports(request)


@router.post("/embed", response_model=EmbedReportResponse)
async def embed_report_endpoint(background_tasks: BackgroundTasks, request: EmbedReportRequest):
    """
    보고서 멀티모달 임베딩 처리 (백그라운드 비동기 처리)
    
    **주요 기능:**
    - S3에서 PDF 파일 다운로드
    - data 폴더에 파일 저장
    - 멀티모달 임베딩 처리 (텍스트, 테이블, 이미지)
    - 백그라운드에서 비동기 처리
    - 완료 시 Supabase report_embed 테이블 업데이트
    
    **처리 과정:**
    1. S3에서 파일 다운로드
    2. data/{파일명_확장자제거}/ 폴더 생성
    3. PDF 파싱 및 멀티모달 임베딩
    4. output 폴더에 JSON 결과 저장
    5. is_completed = true로 업데이트
    
    **사용 예시:**
    ```json
    {
        "file_name": "강소기업1.pdf",
        "embed_id": "uuid-string"
    }
    ```
    
    Args:
        background_tasks: FastAPI 백그라운드 태스크
        request: 임베딩 요청 (파일명, embed_id)
        
    Returns:
        임베딩 시작 확인 메시지
    """
    return await embed_report_start(background_tasks, request)


@router.post("/upload", response_model=UploadReportResponse)
async def upload_report_endpoint(file: UploadFile = File(...)):
    """
    파일을 S3에 업로드
    
    **주요 기능:**
    - 클라이언트에서 파일 직접 업로드
    - AWS S3에 파일 저장
    - S3 URL 반환
    
    **사용 방법:**
    - Content-Type: multipart/form-data
    - Form field name: file
    - 파일을 직접 첨부하여 전송
    
    **예시 (curl):**
    ```bash
    curl -X POST "http://localhost:8000/api/reports/upload" \
      -H "accept: application/json" \
      -H "Content-Type: multipart/form-data" \
      -F "file=@강소기업1.pdf"
    ```
    
    Args:
        file: 업로드할 파일 (multipart/form-data)
        
    Returns:
        업로드 결과 및 S3 URL
    """
    return await upload_report(file)
