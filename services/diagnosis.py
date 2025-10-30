from fastapi import HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import json
from openai import OpenAI
import os


class EvaluationCriteriaItem(BaseModel):
    id: int
    내용: str


class EvaluationCriteriaCategory(BaseModel):
    id: int
    카테고리: str
    평가항목: List[EvaluationCriteriaItem]


class RequestItem(BaseModel):
    query: Optional[str] = None
    contents: Optional[str] = Field(None, min_length=1)


class DiagnosisRequest(BaseModel):
    input: List[RequestItem]
    evaluation: Optional[List[EvaluationCriteriaCategory]] = None


class EvaluationItem(BaseModel):
    id: int
    title: str
    score: int = Field(..., ge=1, le=100)


class EvaluationCategory(BaseModel):
    id: int
    name: str
    items: List[EvaluationItem]


class DiagnosisResponse(BaseModel):
    categories: List[EvaluationCategory]
    score_average: float = Field(..., description="전체 항목의 평균 점수")


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


def get_openai_client():
    """OpenAI 클라이언트를 반환합니다."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def convert_evaluation_criteria(criteria: List[EvaluationCriteriaCategory]) -> List[dict]:
    """사용자가 제공한 한국어 키 구조를 영어 키 구조로 변환"""
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


async def run_diagnosis(request: DiagnosisRequest) -> DiagnosisResponse:
    client = get_openai_client()
    print("시작하기")
    if not client:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY가 설정되지 않았습니다.")

    criteria = request.evaluation if request.evaluation else DEFAULT_EVALUATION_CRITERIA

    combined_content = "\n\n".join(
        (item.contents if item.contents else item.query or "")
        for item in request.input
        if item.contents or item.query
    ).strip()

    if not combined_content:
        raise HTTPException(status_code=400, detail="유효한 content 또는 query가 필요합니다.")

    prompt = build_prompt(combined_content, criteria)
    response = client.responses.create(model="gpt-5", input=prompt)
    output_text = getattr(response, "output_text", None)

    if not output_text:
        raise HTTPException(status_code=502, detail="모델 응답이 비어 있습니다.")

    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="모델 응답을 JSON으로 해석할 수 없습니다.") from exc

    categories = parsed.get("categories") if isinstance(parsed, dict) else None

    if not isinstance(categories, list):
        raise HTTPException(status_code=502, detail="categories 형식이 올바르지 않습니다.")

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

    return DiagnosisResponse(categories=categories, score_average=score_average)
