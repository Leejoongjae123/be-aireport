from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

# 라우터 import
from routers import diagnosis, expert, reports

app = FastAPI(
    title="사업계획서 생성 API", 
    version="2.0.0",
    description="사업계획서 생성, 진단, 전문가 매칭을 위한 통합 API",
    openapi_tags=[
        {
            "name": "Root",
            "description": "API 루트 및 기본 정보"
        },
        {
            "name": "System",
            "description": "시스템 상태 확인"
        },
        {
            "name": "Diagnosis",
            "description": "사업계획서 진단 및 평가 - 기술성, 사업성, 공공성 등 다양한 기준으로 평가"
        },
        {
            "name": "Expert",
            "description": "전문가 매칭 - 사업보고서 기반 전문가 추천 및 정보 조회"
        },
        {
            "name": "Reports",
            "description": "보고서 생성 및 관리 - 사업계획서 생성, 검색, 재생성"
        }
    ]
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(diagnosis.router)
app.include_router(expert.router)
app.include_router(reports.router)


@app.get("/", tags=["Root"])
async def root():
    """
    API 루트 엔드포인트 - 전체 API 구조 안내
    """
    return {
        "message": "사업계획서 생성 및 전문가 매칭 API 서버",
        "version": "2.0.0",
        "model": "GPT-5 (Responses API)",
        "api_structure": {
            "diagnosis": {
                "prefix": "/api/diagnosis",
                "endpoints": [
                    "POST /api/diagnosis/ - 사업계획서 진단 및 평가",
                    "GET /api/diagnosis/criteria - 기본 평가 기준 조회"
                ]
            },
            "expert": {
                "prefix": "/api/expert",
                "endpoints": [
                    "POST /api/expert/match - 전문가 매칭",
                    "GET /api/expert/list - 전체 전문가 목록 조회",
                    "GET /api/expert/{expert_name} - 특정 전문가 정보 조회"
                ]
            },
            "reports": {
                "prefix": "/api/reports",
                "endpoints": [
                    "POST /api/reports/generate/background - 섹션 컨텐츠 생성",
                    "POST /api/reports/generate/full - 전체 보고서 동기 생성",
                    "POST /api/reports/generate - 전체 보고서 비동기 생성",
                    "POST /api/reports/regenerate - 보고서 재생성",
                    "POST /api/reports/search - 보고서 유사도 검색"
                ]
            }
        },
        "documentation": "/docs"
    }


@app.get("/health", tags=["System"])
async def health_check():
    """
    헬스 체크 엔드포인트
    
    시스템 상태 및 설정 확인을 위한 엔드포인트입니다.
    """
    from services.expert import matcher
    
    openai_key_exists = bool(os.getenv("OPENAI_API_KEY"))
    supabase_configured = bool(os.getenv("SUPABASE_URL")) and bool(os.getenv("SUPABASE_KEY"))
    
    return {
        "status": "healthy",
        "openai_api_key_configured": openai_key_exists,
        "supabase_configured": supabase_configured,
        "total_experts": len(matcher.experts)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
