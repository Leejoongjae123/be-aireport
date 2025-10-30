"""
전문가 매칭 API 라우터

사업보고서 기반 전문가 매칭 및 전문가 정보 조회 기능을 제공합니다.
"""

from fastapi import APIRouter
from services.expert import (
    ExpertMatchRequest,
    ExpertMatchResponse,
    match_experts,
    get_all_experts,
    get_expert_by_name
)


router = APIRouter(
    prefix="/api/expert",
    tags=["Expert"],
    responses={404: {"description": "Not found"}},
)


@router.post("/match", response_model=ExpertMatchResponse)
async def match_experts_endpoint(request: ExpertMatchRequest):
    """
    사업보고서를 기반으로 전문가 매칭 수행
    
    **주요 기능:**
    - 사업보고서 내용에서 키워드 추출
    - 전문가 경력 및 분야와 유사도 매칭
    - 유사도 임계값 기반 필터링
    - 매칭 점수 기준 정렬
    
    **사용 예시:**
    ```json
    {
        "business_report": "AI 기반 헬스케어 솔루션...",
        "num_keywords": 10,
        "top_k": 10,
        "similarity_threshold": 0.5
    }
    ```
    
    Args:
        request: 전문가 매칭 요청 데이터
        
    Returns:
        매칭 결과 (키워드, 전문가 랭킹 등)
    """
    return await match_experts(request)


@router.get("/list")
async def get_experts_list():
    """
    전체 전문가 목록 조회
    
    시스템에 등록된 모든 전문가의 정보를 반환합니다.
    
    Returns:
        전문가 목록 및 총 인원수
    """
    return await get_all_experts()


@router.get("/{expert_name}")
async def get_expert_info(expert_name: str):
    """
    특정 전문가 정보 조회
    
    전문가 이름으로 상세 정보를 조회합니다.
    
    Args:
        expert_name: 전문가 이름
        
    Returns:
        전문가 상세 정보
        
    Raises:
        HTTPException 404: 전문가를 찾을 수 없는 경우
    """
    return await get_expert_by_name(expert_name)
