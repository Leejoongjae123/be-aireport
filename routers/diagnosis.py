"""
진단(Diagnosis) 관련 API 라우터

사업계획서 평가 및 진단 기능을 제공합니다.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import json
import os
from openai import OpenAI
from supabase import create_client, Client


router = APIRouter(
    prefix="/api/diagnosis",
    tags=["Diagnosis"],
    responses={404: {"description": "Not found"}},
)


# ==================== Pydantic 모델 정의 ====================

class EvaluationCriteriaItem(BaseModel):
    """평가 항목 개별 아이템"""
    id: int
    내용: str


class EvaluationCriteriaCategory(BaseModel):
    """평가 카테고리 (여러 평가 항목 포함)"""
    id: int
    카테고리: str
    평가항목: List[EvaluationCriteriaItem]


class RequestItem(BaseModel):
    """진단 요청 개별 아이템"""
    query: Optional[str] = None
    contents: Optional[str] = Field(None, min_length=1)


class DiagnosisRequest(BaseModel):
    """
    진단 요청 모델
    
    - input: 평가할 콘텐츠 리스트 (query 또는 contents 중 하나 이상 필수)
    - evaluation: 평가 기준 (선택사항, 미제공 시 기본 평가 기준 사용)
    """
    input: List[RequestItem]
    evaluation: Optional[List[EvaluationCriteriaCategory]] = None


class EvaluationItem(BaseModel):
    """평가 결과 개별 아이템"""
    id: int
    title: str
    score: int = Field(..., ge=1, le=100, description="1-100 사이의 점수")


class EvaluationCategory(BaseModel):
    """평가 결과 카테고리"""
    id: int
    name: str
    items: List[EvaluationItem]


class DiagnosisResponse(BaseModel):
    """
    진단 응답 모델
    
    - categories: 카테고리별 평가 결과 리스트
    - score_average: 전체 항목의 평균 점수
    - success: 저장 성공 여부
    - message: 결과 메시지
    """
    categories: List[EvaluationCategory]
    score_average: float = Field(..., description="전체 항목의 평균 점수")
    success: bool = Field(..., description="진단 및 저장 성공 여부")
    message: str = Field(..., description="처리 결과 메시지")


# ==================== 기본 평가 기준 ====================

DEFAULT_EVALUATION_CRITERIA = [
    EvaluationCriteriaCategory(
        id=1,
        카테고리="기술성",
        평가항목=[
            EvaluationCriteriaItem(id=1, 내용="핵심 기술의 독창성 및 차별성"),
            EvaluationCriteriaItem(id=2, 내용="기술 성숙도(TRL) 및 적용 가능성"),
            EvaluationCriteriaItem(id=3, 내용="AI 모델/알고리즘의 정확도·성능·신뢰성"),
            EvaluationCriteriaItem(id=4, 내용="데이터 확보 수준 및 품질 관리 체계"),
            EvaluationCriteriaItem(id=5, 내용="시스템 아키텍처의 안정성 및 확장성"),
            EvaluationCriteriaItem(id=6, 내용="개인정보 보호, AI 윤리·공정성 준수 여부"),
        ],
    ),
    EvaluationCriteriaCategory(
        id=2,
        카테고리="사업성",
        평가항목=[
            EvaluationCriteriaItem(id=7, 내용="목표 시장 규모 및 성장 가능성"),
            EvaluationCriteriaItem(id=8, 내용="경쟁사 대비 우위 요소(가격·품질·기술)"),
            EvaluationCriteriaItem(id=9, 내용="사업화 모델(BM)의 적정성 및 수익 구조"),
            EvaluationCriteriaItem(id=10, 내용="지식재산권(IP) 확보 전략 및 보호 가능성"),
            EvaluationCriteriaItem(id=11, 내용="글로벌 진출 가능성(해외시장 적합성)"),
            EvaluationCriteriaItem(id=12, 내용="투자 유치 가능성 및 재무 건전성"),
        ],
    ),
    EvaluationCriteriaCategory(
        id=3,
        카테고리="공공성·정책 부합성",
        평가항목=[
            EvaluationCriteriaItem(id=13, 내용="국가 전략·정책(디지털 전환, AI 전략 등) 부합성"),
            EvaluationCriteriaItem(id=14, 내용="사회문제 해결 기여도 (환경·복지·안전 등)"),
            EvaluationCriteriaItem(id=15, 내용="산업 생태계 강화 기여도"),
            EvaluationCriteriaItem(id=16, 내용="데이터 개방·공유·표준화 기여도"),
            EvaluationCriteriaItem(id=17, 내용="지역 균형 발전 및 일자리 창출 효과"),
            EvaluationCriteriaItem(id=18, 내용="법·제도·규제 준수 및 보안 적합성"),
        ],
    ),
    EvaluationCriteriaCategory(
        id=4,
        카테고리="성과·기대효과",
        평가항목=[
            EvaluationCriteriaItem(id=19, 내용="정량적 성과 목표 달성 가능성 (매출, 고용 등)"),
            EvaluationCriteriaItem(id=20, 내용="정성적 성과 목표 달성 가능성 (혁신성, 브랜드 가치)"),
            EvaluationCriteriaItem(id=21, 내용="파급효과 (산업·경제적 확산 가능성)"),
            EvaluationCriteriaItem(id=22, 내용="해외 시장 파급효과 (수출, 글로벌 네트워크)"),
            EvaluationCriteriaItem(id=23, 내용="지속적인 서비스 개선 및 고도화 가능성"),
            EvaluationCriteriaItem(id=24, 내용="사회적 신뢰도 및 파트너십 강화 효과"),
        ],
    ),
    EvaluationCriteriaCategory(
        id=5,
        카테고리="추진체계 및 역량",
        평가항목=[
            EvaluationCriteriaItem(id=25, 내용="주관기관의 전문성 및 수행 경험"),
            EvaluationCriteriaItem(id=26, 내용="참여기관·컨소시엄 구성의 적절성"),
            EvaluationCriteriaItem(id=27, 내용="연구개발 인력 역량 및 확보 수준"),
            EvaluationCriteriaItem(id=28, 내용="프로젝트 관리 및 리스크 대응 체계"),
            EvaluationCriteriaItem(id=29, 내용="외부 협력·오픈이노베이션 활용도"),
            EvaluationCriteriaItem(id=30, 내용="실증 및 검증(테스트베드, PoC) 수행 역량"),
        ],
    ),
]


# ==================== 헬퍼 함수 ====================

def get_openai_client() -> Optional[OpenAI]:
    """
    OpenAI 클라이언트를 반환합니다.
    
    Returns:
        OpenAI 클라이언트 인스턴스 또는 None (API 키가 없는 경우)
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def get_supabase_client() -> Optional[Client]:
    """
    Supabase 클라이언트를 반환합니다.
    
    Returns:
        Supabase 클라이언트 인스턴스 또는 None (환경변수가 없는 경우)
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("Supabase 환경변수가 설정되지 않았습니다.")
        return None
    
    try:
        client = create_client(supabase_url, supabase_key)
        return client
    except Exception as e:
        print(f"Supabase 클라이언트 초기화 실패: {str(e)}")
        return None


def convert_evaluation_criteria(criteria: List[EvaluationCriteriaCategory]) -> List[dict]:
    """
    사용자가 제공한 한국어 키 구조를 영어 키 구조로 변환합니다.
    
    Args:
        criteria: 한국어 키를 가진 평가 기준 리스트
        
    Returns:
        영어 키로 변환된 평가 기준 리스트
    """
    converted = []
    for category in criteria:
        converted_category = {
            "id": category.id,
            "name": category.카테고리,
            "items": [
                {"id": item.id, "title": item.내용}
                for item in category.평가항목
            ]
        }
        converted.append(converted_category)
    return converted


def build_prompt(content: str, criteria: List[EvaluationCriteriaCategory]) -> str:
    """
    GPT 모델에 전달할 프롬프트를 생성합니다.
    
    Args:
        content: 평가할 콘텐츠
        criteria: 평가 기준
        
    Returns:
        생성된 프롬프트 문자열
    """
    converted_criteria = convert_evaluation_criteria(criteria)
    criteria_text = json.dumps(converted_criteria, ensure_ascii=False, indent=2)
    return (
        "다음은 평가 항목 목록입니다:\n"
        f"{criteria_text}\n\n"
        "제공된 콘텐츠를 참고하여 각 항목을 1에서 100 사이의 정수 점수로 평가하세요. "
        "1은 매우 부족함, 100은 매우 우수함을 의미합니다. 평균은 75점 정도가 되게 해줘."
        "출력은 JSON 객체 하나로 작성하며 키는 categories 입니다. "
        "각 categories 요소는 id, name, items 필드를 포함하고, items는 id, title, score 필드를 포함해야 합니다. "
        "추가 설명이나 이유를 포함하지 마세요.\n\n"
        "콘텐츠:\n"
        f"{content}"
    )


# ==================== API 엔드포인트 ====================

@router.post("/", response_model=DiagnosisResponse)
async def run_diagnosis(request: DiagnosisRequest) -> DiagnosisResponse:
    """
    사업계획서 진단 및 평가를 수행하고 Supabase에 저장합니다.
    
    제공된 콘텐츠를 기반으로 다양한 평가 기준에 따라 점수를 산출합니다.
    평가 기준을 제공하지 않으면 기본 평가 기준(기술성, 사업성, 공공성 등)을 사용합니다.
    
    **주요 기능:**
    - 사업계획서 콘텐츠 평가
    - 5개 카테고리 30개 항목 기본 평가 (커스터마이징 가능)
    - GPT-5 모델 기반 자동 점수 산출
    - 1-100점 척도 평가
    - Supabase에 진단 결과 자동 저장
    
    **사용 예시:**
    ```json
    {
        "input": [
            {
                "contents": "AI 기반 헬스케어 솔루션 사업계획서..."
            }
        ]
    }
    ```
    
    Args:
        request: 진단 요청 데이터
            - input: 평가할 콘텐츠 리스트
            - evaluation: 평가 기준 (선택사항)
    
    Returns:
        DiagnosisResponse: 카테고리별 평가 결과 및 저장 상태
        
    Raises:
        HTTPException 400: 유효한 콘텐츠가 없는 경우
        HTTPException 500: OpenAI API 키가 설정되지 않은 경우
        HTTPException 502: 모델 응답 파싱 실패
    """
    client = get_openai_client()
    if not client:
        return DiagnosisResponse(
            categories=[],
            score_average=0.0,
            success=False,
            message="OPENAI_API_KEY가 설정되지 않았습니다."
        )

    # 평가 기준 설정 (제공되지 않으면 기본값 사용)
    criteria = request.evaluation if request.evaluation else DEFAULT_EVALUATION_CRITERIA

    # 입력 콘텐츠 병합
    combined_content = "\n\n".join(
        (item.contents if item.contents else item.query or "")
        for item in request.input
        if item.contents or item.query
    ).strip()

    if not combined_content:
        return DiagnosisResponse(
            categories=[],
            score_average=0.0,
            success=False,
            message="유효한 content 또는 query가 필요합니다."
        )

    try:
        # 프롬프트 생성 및 GPT 호출
        prompt = build_prompt(combined_content, criteria)
        response = client.responses.create(model="gpt-5", input=prompt)
        output_text = getattr(response, "output_text", None)

        if not output_text:
            return DiagnosisResponse(
                categories=[],
                score_average=0.0,
                success=False,
                message="모델 응답이 비어 있습니다."
            )

        # JSON 파싱
        try:
            parsed = json.loads(output_text)
        except json.JSONDecodeError:
            return DiagnosisResponse(
                categories=[],
                score_average=0.0,
                success=False,
                message="모델 응답을 JSON으로 해석할 수 없습니다."
            )

        categories = parsed.get("categories") if isinstance(parsed, dict) else None

        if not isinstance(categories, list):
            return DiagnosisResponse(
                categories=[],
                score_average=0.0,
                success=False,
                message="categories 형식이 올바르지 않습니다."
            )

        # 전체 항목의 평균 점수 계산
        total_score = 0
        total_count = 0
        for category in categories:
            items = category.get("items", [])
            for item in items:
                score = item.get("score", 0)
                total_score += score
                total_count += 1
        
        score_average = round(total_score / total_count, 2) if total_count > 0 else 0.0

        # Supabase에 저장 시도
        supabase = get_supabase_client()
        if supabase:
            try:
                diagnosis_record = {
                    "report_uuid": None,  # standalone diagnosis
                    "diagnosis_result": {
                        "input_content": combined_content,
                        "evaluation_result": parsed,
                        "categories_count": len(categories),
                        "total_items": total_count
                    },
                    "score_average": int(score_average),
                    "duration_seconds": 0
                }
                
                result = supabase.table("diagnosis").insert(diagnosis_record).execute()
                if result.data:
                    return DiagnosisResponse(
                        categories=categories,
                        score_average=score_average,
                        success=True,
                        message="진단이 완료되고 결과가 성공적으로 저장되었습니다."
                    )
                else:
                    return DiagnosisResponse(
                        categories=categories,
                        score_average=score_average,
                        success=False,
                        message="진단 결과 저장에 실패했습니다."
                    )
            except Exception as e:
                print(f"Supabase 저장 중 오류: {str(e)}")
                return DiagnosisResponse(
                    categories=categories,
                    score_average=score_average,
                    success=False,
                    message="진단 결과 저장에 실패했습니다."
                )
        else:
            return DiagnosisResponse(
                categories=categories,
                score_average=score_average,
                success=False,
                message="진단 결과 저장에 실패했습니다."
            )

    except Exception as e:
        print(f"진단 중 오류: {str(e)}")
        return DiagnosisResponse(
            categories=[],
            score_average=0.0,
            success=False,
            message="진단 처리 중 오류가 발생했습니다."
        )


@router.get("/criteria")
async def get_default_criteria():
    """
    기본 평가 기준을 조회합니다.
    
    5개 카테고리(기술성, 사업성, 공공성·정책 부합성, 성과·기대효과, 추진체계 및 역량)와
    각 카테고리별 6개 항목, 총 30개의 평가 항목을 반환합니다.
    
    **반환 구조:**
    - 각 카테고리는 id, 카테고리명, 평가항목 리스트를 포함
    - 각 평가항목은 id와 내용을 포함
    
    Returns:
        기본 평가 기준 리스트
    """
    return {
        "total_categories": len(DEFAULT_EVALUATION_CRITERIA),
        "total_items": sum(len(cat.평가항목) for cat in DEFAULT_EVALUATION_CRITERIA),
        "criteria": [
            {
                "id": cat.id,
                "카테고리": cat.카테고리,
                "평가항목": [
                    {"id": item.id, "내용": item.내용}
                    for item in cat.평가항목
                ]
            }
            for cat in DEFAULT_EVALUATION_CRITERIA
        ]
    }
