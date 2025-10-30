import json
import os
from supabase import create_client, Client
from typing import List, Dict, Tuple

from fastapi import HTTPException
from pydantic import BaseModel, Field
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from dotenv import load_dotenv
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

load_dotenv()


class ExpertMatcher:
    """전문가 매칭 클래스"""
    
    def __init__(self):
        """초기화: Supabase에서 전문가 정보를 로드합니다."""
        # Supabase 클라이언트 초기화 (환경변수에서 URL과 KEY를 읽음)
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        if not supabase_url or not supabase_key:
            raise ValueError("Supabase URL or ANON KEY not set in environment variables.")
        self.supabase: Client = create_client(supabase_url, supabase_key)
        # 전문가 데이터 로드
        self.experts = self._load_experts()
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    def _load_experts(self) -> List[Dict]:
        """Supabase 테이블에서 전문가 정보를 로드합니다."""
        response = self.supabase.table("expert_informations").select("*").eq("is_visible", True).execute()
        if hasattr(response, 'error') and response.error:
            raise RuntimeError(f"Supabase 로드 오류: {response.error.message}")
        # response.data는 리스트 형태이며, 각 항목은 dict
        return response.data
    
    def _normalize_to_string_list(self, data) -> List[str]:
        """딕셔너리 또는 리스트를 문자열 리스트로 정규화합니다."""
        if isinstance(data, dict):
            data = list(data.values()) if data else []
        if not isinstance(data, list):
            return []
        return [str(item) for item in data if item]
    
    def extract_keywords(self, business_report: str, num_keywords: int = 5) -> List[str]:
        """
        사업보고서에서 키워드 추출
        
        Args:
            business_report: 사업보고서 내용
            num_keywords: 추출할 키워드 개수
            
        Returns:
            추출된 키워드 리스트
        """
        prompt = f"""다음 사업보고서 내용을 분석하여 핵심 키워드 {num_keywords}개를 추출해주세요.
키워드는 전문가 매칭에 사용될 것이므로, 사업 분야, 기술, 산업 등과 관련된 중요한 단어를 선택해주세요.

사업보고서:
{business_report}

응답 형식: 키워드만 쉼표로 구분하여 나열 (예: 디지털전환, 마케팅, 창업, 브랜딩, 사업계획)
"""
        
        response = self.llm.invoke(prompt)
        keywords_text = response.content.strip()
        
        # 쉼표로 구분하여 키워드 리스트 생성
        keywords = [k.strip() for k in keywords_text.split(',')]
        
        return keywords[:num_keywords]
    
    def semantic_keyword_matching(self, keywords: List[str], 
                                   similarity_threshold: float = 0.7) -> List[Tuple[Dict, int, List[Dict]]]:
        """
        임베딩 기반 의미적 키워드 매칭으로 전문가 랭킹
        경력과 분야를 개별 항목으로 쪼개서 벡터 임베딩 후
        키워드와 유사도 0.7 이상인 매칭 개수를 카운트
        
        Args:
            keywords: 검색 키워드 리스트 (5개)
            similarity_threshold: 유사도 임계값 (0~1, 기본값 0.7)
            
        Returns:
            (전문가 정보, 매칭 개수, 매칭 상세) 튜플 리스트 (내림차순 정렬)
        """
        # 키워드 임베딩 생성
        print(f"키워드 임베딩 생성 중: {keywords}")
        keyword_embeddings = self.embeddings.embed_documents(keywords)
        
        expert_scores = []
        
        for expert in self.experts:
            # 전문가의 경력과 분야를 개별 항목으로 분리
            career_items = expert.get("career", [])
            field_items = expert.get("field", [])
            
            # JSONB 타입이 딕셔너리로 올 수 있으므로 문자열 리스트로 변환
            if isinstance(career_items, dict):
                career_items = list(career_items.values()) if career_items else []
            if isinstance(field_items, dict):
                field_items = list(field_items.values()) if field_items else []
            
            # 문자열만 필터링 (혹시 모를 다른 타입 제거)
            career_items = [str(item) for item in career_items if item]
            field_items = [str(item) for item in field_items if item]
            
            all_items = career_items + field_items
            
            if not all_items:
                expert_scores.append((expert, 0, []))
                continue
            
            # 전문가 항목들의 임베딩 생성 (각 항목을 개별적으로 임베딩)
            expert_embeddings = self.embeddings.embed_documents(all_items)
            
            # 유사도 0.7 이상인 매칭 개수 카운트
            match_count = 0
            match_details = []
            
            for keyword, keyword_emb in zip(keywords, keyword_embeddings):
                # 각 키워드에 대해 전문가의 모든 항목과 비교
                for item, expert_emb in zip(all_items, expert_embeddings):
                    # 코사인 유사도 계산
                    similarity = cosine_similarity(
                        np.array(keyword_emb).reshape(1, -1),
                        np.array(expert_emb).reshape(1, -1)
                    )[0][0]
                    
                    # 임계값 이상인 경우 카운트
                    if similarity >= similarity_threshold:
                        match_count += 1
                        match_details.append({
                            "keyword": keyword,
                            "matched_item": item,
                            "similarity": float(similarity)
                        })
            
            expert_scores.append((expert, match_count, match_details))
        
        # 매칭 개수 기준 내림차순 정렬
        expert_scores.sort(key=lambda x: x[1], reverse=True)
        
        return expert_scores
    
    def match_experts(self, business_report: str, num_keywords: int = 5, top_k: int = 10, 
                     similarity_threshold: float = 0.7) -> Dict:
        """
        사업보고서를 기반으로 전문가 매칭 수행
        
        Args:
            business_report: 사업보고서 내용
            num_keywords: 추출할 키워드 개수 (기본값 5)
            top_k: 반환할 최종 전문가 수 (기본값 10)
            similarity_threshold: 유사도 임계값 (0~1, 기본값 0.7)
            
        Returns:
            매칭 결과 딕셔너리
        """
        # 1단계: 키워드 추출
        print("=" * 80)
        print("1단계: 키워드 추출 중...")
        print("=" * 80)
        keywords = self.extract_keywords(business_report, num_keywords)
        print(f"추출된 키워드 ({len(keywords)}개): {keywords}\n")
        
        # 2단계: 전체 전문가 대상 의미적 키워드 매칭
        print("=" * 80)
        print(f"2단계: 전체 전문가 대상 의미적 키워드 매칭 (임계값: {similarity_threshold})")
        print("=" * 80)
        ranked_experts = self.semantic_keyword_matching(keywords, similarity_threshold)
        
        # 상위 top_k명만 추출
        top_experts = ranked_experts[:top_k]
        
        print(f"\n최종 랭킹 (유사도 {similarity_threshold} 이상 매칭 개수 기준):")
        print("=" * 80)
        for idx, (expert, match_count, match_details) in enumerate(top_experts, 1):
            print(f"\n{idx}. {expert['name']} - 매칭 개수: {match_count}개")
            
            # career와 field를 문자열 리스트로 변환
            career_list = expert.get('career', [])
            field_list = expert.get('field', [])
            if isinstance(career_list, dict):
                career_list = list(career_list.values()) if career_list else []
            if isinstance(field_list, dict):
                field_list = list(field_list.values()) if field_list else []
            career_list = [str(item) for item in career_list if item]
            field_list = [str(item) for item in field_list if item]
            
            print(f"   경력: {', '.join(career_list)}")
            print(f"   분야: {', '.join(field_list)}")
            
            # 매칭 상세 정보 출력 (상위 3개만)
            if match_details:
                print(f"   주요 매칭:")
                for detail in match_details[:3]:
                    print(f"     - 키워드 '{detail['keyword']}' ↔ '{detail['matched_item']}' (유사도: {detail['similarity']:.3f})")
        
        print("=" * 80)
        
        # 결과 반환
        return {
            "keywords": keywords,
            "matching_method": "semantic_count",
            "similarity_threshold": similarity_threshold,
            "total_experts_evaluated": len(self.experts),
            "final_ranking": [
                {
                    "순위": idx,
                    "이름": expert["name"],
                    "경력": self._normalize_to_string_list(expert.get("career", [])),
                    "분야": self._normalize_to_string_list(expert.get("field", [])),
                    "경력파일명": expert.get("career_file_name", ""),
                    "매칭_개수": match_count,
                    "매칭_상세": match_details
                }
                for idx, (expert, match_count, match_details) in enumerate(top_experts, 1)
            ]
        }


# 전문가 매칭 시스템 초기화
matcher = ExpertMatcher()


class ExpertMatchRequest(BaseModel):
    """전문가 매칭 요청 모델"""
    business_report: str = Field(..., description="사업보고서 내용")
    num_keywords: int = Field(10, description="추출할 키워드 개수", ge=1, le=10)
    top_k: int = Field(10, description="반환할 상위 전문가 수", ge=1, le=50)
    similarity_threshold: float = Field(0.5, description="유사도 임계값", ge=0.0, le=1.0)


class MatchDetail(BaseModel):
    """매칭 상세 정보"""
    keyword: str
    matched_item: str
    similarity: float


class ExpertRanking(BaseModel):
    """전문가 랭킹 정보"""
    순위: int
    이름: str
    경력: List[str]
    분야: List[str]
    경력파일명: str
    매칭_개수: int
    매칭_상세: List[MatchDetail]


class ExpertMatchResponse(BaseModel):
    """전문가 매칭 응답 모델"""
    keywords: List[str]
    matching_method: str
    similarity_threshold: float
    total_experts_evaluated: int
    final_ranking: List[ExpertRanking]


async def match_experts(request: ExpertMatchRequest):
    """
    사업보고서를 기반으로 전문가 매칭 수행
    
    Args:
        request: 전문가 매칭 요청 데이터
        
    Returns:
        매칭 결과
    """
    try:
        result = matcher.match_experts(
            business_report=request.business_report,
            num_keywords=request.num_keywords,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"전문가 매칭 중 오류가 발생했습니다: {str(e)}"
        )


async def get_all_experts():
    """
    전체 전문가 목록 조회
    
    Returns:
        전문가 목록
    """
    return {
        "total_count": len(matcher.experts),
        "experts": matcher.experts
    }


async def get_expert_by_name(expert_name: str):
    """
    특정 전문가 정보 조회
    
    Args:
        expert_name: 전문가 이름
        
    Returns:
        전문가 정보
    """
    for expert in matcher.experts:
        if expert.get("이름") == expert_name:
            return expert
    
    raise HTTPException(
        status_code=404,
        detail=f"전문가 '{expert_name}'을(를) 찾을 수 없습니다."
    )
