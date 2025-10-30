from fastapi import HTTPException, BackgroundTasks, UploadFile, File
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
import os
import json
import time
import re
from pathlib import Path
from openai import OpenAI
from supabase import create_client, Client
import boto3
from botocore.exceptions import ClientError


def get_openai_client():
    """OpenAI 클라이언트를 반환합니다."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def get_supabase_client() -> Optional[Client]:
    """Supabase 클라이언트를 반환합니다."""
    print("get_supabase_client")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    print("supabase_url", supabase_url)
    print("supabase_key", supabase_key)
    
    if not supabase_url or not supabase_key:
        print("Supabase 환경변수가 설정되지 않았습니다.")
        return None
    
    try:
        client = create_client(supabase_url, supabase_key)
        return client
    except Exception as e:
        print(f"Supabase 클라이언트 초기화 실패: {str(e)}")
        return None


def remove_html_tags(text: str) -> str:
    """
    HTML 태그를 제거하고 순수 텍스트만 반환합니다.
    
    Args:
        text: HTML 태그가 포함된 텍스트
    
    Returns:
        HTML 태그가 제거된 순수 텍스트
    """
    clean_text = re.sub(r'<[^>]+>', '', text)
    clean_text = re.sub(r'\s+', ' ', clean_text)
    return clean_text.strip()


def parse_search_results(text_response: str) -> str:
    """검색 결과를 HTML 형식으로 변환합니다."""
    html_content = "<h2>관련 자료</h2>"
    items = re.split(r'\n\d+\.\s', '\n' + text_response.strip())[1:]
    if not items:
        return html_content + f"<p>{text_response.strip()}</p>"

    for item in items:
        if item.strip():
            cleaned_item = item.strip().replace('\n', '<br>')
            html_content += f"<p>{cleaned_item}</p>"
    return html_content


def load_reference_data(json_file: str = "1.1.json", data_folder: Optional[Path] = None) -> tuple[str, str, str]:
    """
    참고용 JSON 파일에서 메타데이터와 contexts 중 rank 1을 로드합니다.
    
    Args:
        json_file: 참고할 JSON 파일명 (기본값: 1.1.json)
        data_folder: 데이터 폴더 경로 (지정되지 않으면 현재 디렉토리에서 검색)
    
    Returns:
        tuple: (subsection_id, subsection_name, rank 1 content)
               로드 실패 시 ("", "", "")
    """
    try:
        current_dir = Path(__file__).parent.parent
        
        if data_folder and data_folder.exists():
            json_path = data_folder / "output" / json_file
        else:
            json_path = current_dir / json_file
        
        if not json_path.exists():
            return ("", "", "")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            subsection_id = data.get('subsection_id', '')
            subsection_name = data.get('subsection_name', '')
            contexts = data.get('contexts', [])
            
            content = ""
            for ctx in contexts:
                if ctx.get('rank') == 1:
                    content = ctx.get('content', '')
                    break
            
            return (subsection_id, subsection_name, content)
    except Exception as e:
        print(f"참고 파일 로드 중 오류: {e}")
        return ("", "", "")


# Request/Response Models
class GenerateBackgroundRequest(BaseModel):
    business_idea: str = Field(..., description="사업 아이디어")
    core_value: str = Field(..., description="핵심 가치")
    subsection_id: str = Field(default="1.1", description="섹션 ID")
    subsection_name: str = Field(default="추진 배경 및 필요성", description="섹션 이름")
    section_id: str = Field(default="1", description="상위 섹션 ID")
    section_name: str = Field(default="사업 개요", description="상위 섹션 이름")


class GenerateBackgroundResponse(BaseModel):
    subsection_id: str
    subsection_name: str
    section_id: str
    section_name: str
    query: str
    content: str
    character_count: int = Field(..., description="태그를 제외한 순수 글자수")
    elapsed_time: float = Field(..., description="소요 시간 (초)")


class GenerateReportRequest(BaseModel):
    business_idea: str = Field(..., description="사업 아이디어")
    core_value: str = Field(..., description="핵심 가치")
    file_name: str = Field(..., description="참고 PDF 파일명 (예: 강소기업1.pdf)")
    report_id: str = Field(..., description="Supabase report_create 테이블의 UUID")


class SearchRequest(BaseModel):
    """보고서 검색 요청 모델"""
    business_idea: str = Field(..., description="사업 아이디어")
    core_value: str = Field(..., description="핵심 가치")
    category_number: int = Field(..., ge=1, le=5, description="분야 번호 (1-5)")
    top_k: int = Field(5, ge=1, le=20, description="반환할 결과 개수")


class ReportResult(BaseModel):
    """보고서 검색 결과 모델"""
    id: int
    number: int = Field(..., alias="번호")
    title: str = Field(..., alias="제목")
    field: str = Field(..., alias="분야")
    keywords: str = Field(..., alias="키워드")
    file_name: str = Field(..., alias="보고서파일명")
    category_number: int = Field(..., alias="분야번호")
    similarity: float = Field(..., description="유사도 점수 (0-1)")


class SearchResponse(BaseModel):
    """검색 응답 모델"""
    success: bool
    query: str = Field(..., description="검색에 사용된 쿼리")
    category_number: int
    total_found: int
    results: List[ReportResult]


class GenerateReportResponse(BaseModel):
    success: bool
    message: str
    report_id: str
    generated_sections: List[str]
    elapsed_time: float = Field(..., description="총 소요 시간 (초)")


class RegenerateRequest(BaseModel):
    classification: str
    subject: Optional[str] = None
    contents: Optional[str] = None


class RegenerateResponse(BaseModel):
    result: str
    contents: str
    elapsed_seconds: float


class GenerateStartResponse(BaseModel):
    success: bool
    message: str
    report_id: str


class EmbedReportRequest(BaseModel):
    """보고서 임베딩 요청 모델"""
    file_name: str = Field(..., description="S3에 저장된 PDF 파일명 (예: 강소기업1.pdf)")
    embed_id: str = Field(..., description="Supabase report_embed 테이블의 ID")


class EmbedReportResponse(BaseModel):
    """보고서 임베딩 응답 모델"""
    success: bool
    message: str
    embed_id: str


class UploadReportResponse(BaseModel):
    """보고서 업로드 응답 모델"""
    success: bool
    message: str
    file_name: str
    s3_url: Optional[str] = None


def generate_background_content(
    business_idea: str, 
    core_value: str,
    json_file: str = "1.1.json",
    data_folder: Optional[Path] = None
) -> str:
    """
    OpenAI Responses API (GPT-5)를 사용하여 사업계획서 컨텐츠를 생성합니다.
    
    Args:
        business_idea: 사업 아이디어
        core_value: 핵심 가치
        json_file: 참고할 JSON 파일명 (기본값: 1.1.json)
        data_folder: 데이터 폴더 경로 (지정되지 않으면 현재 디렉토리에서 검색)
    
    Returns:
        생성된 컨텐츠 텍스트
    """
    
    subsection_id, subsection_name, reference_content = load_reference_data(json_file, data_folder)

    print(f"subsection_id: {subsection_id}")
    print(f"subsection_name: {subsection_name}")
    # print(f"reference_content: {reference_content}")
    
    
    if not subsection_name:
        subsection_name = "해당 섹션"
    
    if reference_content:
        if len(reference_content) > 1500:
            reference_content = reference_content[:1500] + "..."
        reference_example = f"\n[참고 예시]\n{reference_content}\n"
    else:
        reference_example = "[참고 예시를 로드할 수 없습니다]"
    
    user_prompt = f"""다음 사업 아이디어와 핵심 가치를 바탕으로 '{subsection_name}' 전체 내용을 작성해주세요.

사업 아이디어: {business_idea}
핵심 가치: {core_value}

아래는 실제 작성된 사업계획서의 '{subsection_name}' 예시입니다:
{reference_example}

위의 참고 예시의 작성 스타일, 구조, 형식을 참고하여 작성해주세요:
- 참고 예시와 유사한 구조로 보고서 작성
- 가장 상단에 subsection_name값을 적고 h1태그를 써줘
- 내용에서 불필요한 말머리기호는 없애주고, N.소제목(h2태그)으로 작성하고 그 밑에는 -기호로 개행하면서 작성(p태그)해줘
- 테이블형태로 작성해야되는거는 HTML 테이블 형태 고려해서 작성해줘.
- 약 1000자 내외 분량의 체계적이고 포괄적인 내용으로 작성
- HTML형태로 작성하여 개행과 넘버링 체계 유지
- {subsection_name}에 부합하지 않는 내용은 제거
"""
    
    client = get_openai_client()
    print(f"요청시작")
    if not client:
        return "OpenAI API 키가 설정되지 않았습니다."
    
    try:
        response = client.responses.create(
            model="gpt-5",
            reasoning={"effort": "medium"},
            instructions="당신은 정부 R&D 사업계획서 작성 전문가입니다. 기술적이고 전문적인 용어를 사용하며, 설득력 있는 내용을 작성합니다.",
            input=user_prompt
        )
        
        content = response.output_text
        if content:
            return content.strip()
        return "컨텐츠가 생성되지 않았습니다."
        
    except Exception as e:
        print(f"컨텐츠 생성 중 오류: {str(e)}")
        return f"컨텐츠 생성 중 오류: {str(e)}"


async def generate_background(request: GenerateBackgroundRequest):
    """
    사업 아이디어와 핵심 가치를 바탕으로 사업계획서 섹션 컨텐츠를 생성합니다.
    
    Args:
        request: 사업 아이디어, 핵심 가치, subsection_id를 포함한 요청 데이터
    
    Returns:
        섹션 정보와 생성된 컨텐츠 및 소요 시간을 포함한 응답
    """
    
    start_time = time.time()
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        elapsed_time = time.time() - start_time
        error_message = "⚠️ OPENAI_API_KEY 환경변수가 설정되지 않았습니다. .env 파일을 확인하거나 환경변수를 설정해주세요."
        return GenerateBackgroundResponse(
            subsection_id=request.subsection_id,
            subsection_name=request.subsection_name,
            section_id=request.section_id,
            section_name=request.section_name,
            query=request.subsection_name,
            content=error_message,
            character_count=len(error_message),
            elapsed_time=elapsed_time
        )
    
    json_file = f"{request.subsection_id}.json"
    
    loaded_id, loaded_name, _ = load_reference_data(json_file)
    
    final_subsection_name = loaded_name if loaded_name else request.subsection_name
    
    content = generate_background_content(
        business_idea=request.business_idea,
        core_value=request.core_value,
        json_file=json_file
    )
    
    elapsed_time = time.time() - start_time
    
    clean_content = remove_html_tags(content)
    character_count = len(clean_content)
    
    response = GenerateBackgroundResponse(
        subsection_id=request.subsection_id,
        subsection_name=final_subsection_name,
        section_id=request.section_id,
        section_name=request.section_name,
        query=final_subsection_name,
        content=content,
        character_count=character_count,
        elapsed_time=elapsed_time
    )
    
    return response


def process_report_generation(request: GenerateReportRequest) -> GenerateReportResponse:
    """
    전체 사업계획서 생성 로직. 동기 함수로 구현하여 재사용합니다.
    각 소목차별로 report_sections 테이블에 개별 레코드로 저장합니다.
    """
    start_time = time.time()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        elapsed_time = time.time() - start_time
        return GenerateReportResponse(
            success=False,
            message="⚠️ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.",
            report_id=request.report_id,
            generated_sections=[],
            elapsed_time=elapsed_time
        )

    supabase = get_supabase_client()
    if not supabase:
        elapsed_time = time.time() - start_time
        return GenerateReportResponse(
            success=False,
            message="⚠️ SUPABASE_URL 또는 SUPABASE_KEY 환경변수가 설정되지 않았습니다.",
            report_id=request.report_id,
            generated_sections=[],
            elapsed_time=elapsed_time
        )

    base_name = request.file_name.replace(".pdf", "")
    current_dir = Path(__file__).parent.parent
    data_folder = current_dir / "data" / base_name
    if not data_folder.exists():
        elapsed_time = time.time() - start_time
        return GenerateReportResponse(
            success=False,
            message=f"❌ 데이터 폴더를 찾을 수 없습니다: {data_folder}",
            report_id=request.report_id,
            generated_sections=[],
            elapsed_time=elapsed_time
        )

    output_folder = data_folder / "output"
    if not output_folder.exists():
        elapsed_time = time.time() - start_time
        return GenerateReportResponse(
            success=False,
            message=f"❌ output 폴더를 찾을 수 없습니다: {output_folder}",
            report_id=request.report_id,
            generated_sections=[],
            elapsed_time=elapsed_time
        )

    json_files = sorted([
        f for f in output_folder.glob("*.json")
        if f.name != "_summary.json" and f.stem.replace(".", "").isdigit()
    ])

    if not json_files:
        elapsed_time = time.time() - start_time
        return GenerateReportResponse(
            success=False,
            message=f"❌ JSON 파일을 찾을 수 없습니다: {output_folder}",
            report_id=request.report_id,
            generated_sections=[],
            elapsed_time=elapsed_time
        )

    print(f"\n{'='*60}")
    print(f"📊 사업계획서 생성 시작")
    print(f"{'='*60}")
    print(f"파일명: {request.file_name}")
    print(f"리포트 ID: {request.report_id}")
    print(f"총 소목차 수: {len(json_files)}개")
    print(f"{'='*60}\n")

    generated_sections: List[str] = []

    for idx, json_file in enumerate(json_files, 1):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)

            subsection_id = json_data.get('subsection_id', '')
            subsection_name = json_data.get('subsection_name', '')
            section_id = json_data.get('section_id', '')
            section_name = json_data.get('section_name', '')

            print(f"🔄 [{idx}/{len(json_files)}] 생성 중: {subsection_id} {subsection_name}")

            content = generate_background_content(
                business_idea=request.business_idea,
                core_value=request.core_value,
                json_file=json_file.name,
                data_folder=data_folder
            )

            clean_content = remove_html_tags(content)
            character_count = len(clean_content)

            section_record = {
                "report_uuid": request.report_id,
                "section_id": section_id,
                "section_name": section_name,
                "subsection_id": subsection_id,
                "subsection_name": subsection_name,
                "query": subsection_name,
                "content": content,
                "character_count": character_count,
                "is_completed": True,
                "generation_order": idx
            }

            try:
                supabase.table("report_sections").insert(section_record).execute()
                
                generated_sections.append(f"{subsection_id} {subsection_name}")
                
                print(f"✅ [{idx}/{len(json_files)}] 완료: {subsection_id} {subsection_name}")
                print(f"   생성된 내용 길이: {character_count}자 (순수 텍스트)\n")
                
            except Exception as e:
                print(f"⚠️  report_sections 저장 실패 (계속 진행): {str(e)}")
                continue

        except Exception as e:
            print(f"❌ [{idx}/{len(json_files)}] 오류 발생: {json_file.name}")
            print(f"   오류 내용: {str(e)}\n")
            continue

    try:
        supabase.table("report_create").update({
            "is_complete": True
        }).eq("uuid", request.report_id).execute()

        print(f"\n{'='*60}")
        print(f"✅ 사업계획서 생성 완료!")
        print(f"{'='*60}")
        print(f"총 생성된 소목차: {len(generated_sections)}개")
        print(f"리포트 ID: {request.report_id}")
        print(f"완료 상태: is_complete = True")
        print(f"{'='*60}\n")

    except Exception as e:
        elapsed_time = time.time() - start_time
        return GenerateReportResponse(
            success=False,
            message=f"❌ Supabase 저장 실패: {str(e)}",
            report_id=request.report_id,
            generated_sections=generated_sections,
            elapsed_time=elapsed_time
        )

    elapsed_time = time.time() - start_time
    return GenerateReportResponse(
        success=True,
        message=f"✅ {len(generated_sections)}개의 소목차가 성공적으로 생성되었습니다.",
        report_id=request.report_id,
        generated_sections=generated_sections,
        elapsed_time=elapsed_time
    )


async def generate_report(request: GenerateReportRequest):
    """
    동기 처리 엔드포인트 (기존 동작 유지)
    """
    return process_report_generation(request)


async def generate_start(background_tasks: BackgroundTasks, request: GenerateReportRequest):
    """
    즉시 성공을 반환하고, 보고서 생성은 백그라운드에서 실행합니다.
    """
    background_tasks.add_task(process_report_generation, request)
    return GenerateStartResponse(success=True, message="generation started", report_id=request.report_id)


async def report_regenerate(request: RegenerateRequest):
    start_time = time.time()
    client = get_openai_client()
    if not client:
        elapsed_seconds = time.time() - start_time
        message = "OPENAI_API_KEY 환경변수가 설정되지 않았습니다."
        return RegenerateResponse(result="error", contents=message, elapsed_seconds=elapsed_seconds)

    try:
        output_text = ""

        if request.classification in {"자세히", "간결하게", "윤문"}:
            if not request.contents:
                elapsed_seconds = time.time() - start_time
                return RegenerateResponse(
                    result="error",
                    contents="요청에 contents가 없습니다.",
                    elapsed_seconds=elapsed_seconds
                )

            style_prompts = {
                "자세히": "주어진 원문의 문단과 목록 구조를 유지하며 세부 설명을 보강해 더 자세하게 작성하면서 글자수를 지금보다 20% 늘려줘",
                "간결하게": "주어진 원문의 문단과 목록 구조를 유지하며 핵심만 남기고 간결하게 작성해하고 글자수를 지금보다 20% 줄여줘",
                "윤문": "주어진 원문의 문단과 목록 구조를 유지하며 자연스럽고 매끄러운 문장으로 다듬어.",
            }
            style_instruction = style_prompts[request.classification]
            prompt = (
                "아래 지침을 모두 준수해 결과 텍스트만 응답해.\n"
                "1. 답변은 원문과 동일한 구조(헤더, 문단, 목록, 표 등)를 유지할 것.\n"
                f"2. 요청 방식: {style_instruction}\n"
                "3. 추가 설명이나 메타 코멘트를 덧붙이지 말 것.\n\n"
                f"요청 유형: {request.classification}\n"
                f"원문:\n{request.contents}"
            )

            response = client.responses.create(
                model="gpt-5",
                input=prompt,
            )

            output_text = getattr(response, "output_text", "")
            if not output_text:
                output_text = request.contents or ""

            elapsed_seconds = time.time() - start_time
            return RegenerateResponse(
                result="success",
                contents=output_text,
                elapsed_seconds=elapsed_seconds
            )

        if request.classification == "특허":
            if not request.subject:
                elapsed_seconds = time.time() - start_time
                return RegenerateResponse(
                    result="error",
                    contents="요청에 subject가 없습니다.",
                    elapsed_seconds=elapsed_seconds
                )
            query = f"한국의 {request.subject} 관련 특허 웹 검색조건으로 2020년 이후 3건을 발명명, 출원인 알려줘"

            response = client.responses.create(
                model="o4-mini",
                tools=[{
                    "type": "web_search",
                    "user_location": {
                        "type": "approximate",
                        "country": "KR",
                        "city": "Seoul",
                        "region": "Seoul",
                    }
                }],
                input=query
            )

            if hasattr(response, "output_text"):
                output_text = response.output_text
        elif request.classification == "뉴스":
            if not request.subject:
                elapsed_seconds = time.time() - start_time
                return RegenerateResponse(
                    result="error",
                    contents="요청에 subject가 없습니다.",
                    elapsed_seconds=elapsed_seconds
                )
            query = f"{request.subject} 관련 최신 한국 뉴스 3건의 제목, 출처, 날짜를 알려줘"

            response = client.responses.create(
                model="o4-mini",
                tools=[{
                    "type": "web_search",
                    "user_location": {
                        "type": "approximate",
                        "country": "KR",
                        "city": "Seoul",
                        "region": "Seoul",
                    }
                }],
                input=query
            )

            if hasattr(response, "output_text"):
                output_text = response.output_text

        else:
            if not request.subject:
                elapsed_seconds = time.time() - start_time
                return RegenerateResponse(
                    result="error",
                    contents="요청에 subject가 없습니다.",
                    elapsed_seconds=elapsed_seconds
                )
            query = f"{request.subject}에 대한 한국의 {request.classification} 3건의 제목, 작성자, 출처를 알려줘"

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that provides information including title, author, and source."},
                    {"role": "user", "content": query}
                ]
            )

            if response.choices and response.choices[0].message.content:
                output_text = response.choices[0].message.content

        if not output_text:
            elapsed_seconds = time.time() - start_time
            return RegenerateResponse(
                result="error",
                contents="검색 결과를 가져오는 데 실패했습니다.",
                elapsed_seconds=elapsed_seconds
            )

        html_content = parse_search_results(output_text)
        elapsed_seconds = time.time() - start_time

        return RegenerateResponse(
            result="success",
            contents=html_content,
            elapsed_seconds=elapsed_seconds
        )

    except Exception as e:
        elapsed_seconds = time.time() - start_time
        return RegenerateResponse(
            result="error",
            contents=f"오류가 발생했습니다: {str(e)}",
            elapsed_seconds=elapsed_seconds
        )


def get_s3_client():
    """S3 클라이언트를 반환합니다."""
    aws_access_key = os.getenv("NEXT_PUBLIC_S3_ACCESS_KEY")
    aws_secret_key = os.getenv("NEXT_PUBLIC_S3_SECRET_KEY")
    aws_region = os.getenv("NEXT_PUBLIC_S3_REGION", "ap-northeast-2")
    
    if not aws_access_key or not aws_secret_key:
        print("AWS 자격증명이 설정되지 않았습니다.")
        return None
    
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region
        )
        return s3_client
    except Exception as e:
        print(f"S3 클라이언트 초기화 실패: {str(e)}")
        return None


def download_from_s3(file_name: str, local_path: Path) -> bool:
    """
    S3에서 파일을 다운로드합니다.
    
    Args:
        file_name: S3에 저장된 파일명
        local_path: 로컬에 저장할 경로
    
    Returns:
        성공 여부
    """
    s3_client = get_s3_client()
    if not s3_client:
        return False
    
    bucket_name = os.getenv("AWS_S3_BUCKET_NAME")
    if not bucket_name:
        print("AWS_S3_BUCKET_NAME 환경변수가 설정되지 않았습니다.")
        return False
    
    try:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        s3_client.download_file(bucket_name, file_name, str(local_path))
        print(f"S3에서 파일 다운로드 완료: {file_name} -> {local_path}")
        return True
    except ClientError as e:
        print(f"S3 다운로드 실패: {str(e)}")
        return False
    except Exception as e:
        print(f"파일 다운로드 중 오류: {str(e)}")
        return False


def upload_to_s3(file_name: str, local_path: Path) -> tuple[bool, Optional[str]]:
    """
    로컬 파일을 S3에 업로드합니다.
    
    Args:
        file_name: S3에 저장할 파일명
        local_path: 업로드할 로컬 파일 경로
    
    Returns:
        (성공 여부, S3 URL)
    """
    s3_client = get_s3_client()
    if not s3_client:
        return False, None
    
    bucket_name = os.getenv("AWS_S3_BUCKET_NAME")
    if not bucket_name:
        print("AWS_S3_BUCKET_NAME 환경변수가 설정되지 않았습니다.")
        return False, None
    
    if not local_path.exists():
        print(f"파일을 찾을 수 없습니다: {local_path}")
        return False, None
    
    try:
        s3_client.upload_file(str(local_path), bucket_name, file_name)
        
        aws_region = os.getenv("AWS_REGION", "ap-northeast-2")
        s3_url = f"https://{bucket_name}.s3.{aws_region}.amazonaws.com/{file_name}"
        
        print(f"S3에 파일 업로드 완료: {local_path} -> s3://{bucket_name}/{file_name}")
        return True, s3_url
    except ClientError as e:
        print(f"S3 업로드 실패: {str(e)}")
        return False, None
    except Exception as e:
        print(f"파일 업로드 중 오류: {str(e)}")
        return False, None


async def upload_file_to_s3(file: UploadFile) -> tuple[bool, Optional[str], str]:
    """
    업로드된 파일을 S3에 직접 업로드합니다.
    
    Args:
        file: FastAPI UploadFile 객체
    
    Returns:
        (성공 여부, S3 URL, 파일명)
    """
    s3_client = get_s3_client()
    if not s3_client:
        return False, None, file.filename
    
    bucket_name = os.getenv("AWS_S3_BUCKET_NAME")
    if not bucket_name:
        print("AWS_S3_BUCKET_NAME 환경변수가 설정되지 않았습니다.")
        return False, None, file.filename
    
    try:
        # 파일 내용 읽기
        file_content = await file.read()
        
        # S3에 업로드
        s3_client.put_object(
            Bucket=bucket_name,
            Key=file.filename,
            Body=file_content,
            ContentType=file.content_type or 'application/pdf'
        )
        
        aws_region = os.getenv("AWS_REGION", "ap-northeast-2")
        s3_url = f"https://{bucket_name}.s3.{aws_region}.amazonaws.com/{file.filename}"
        
        print(f"S3에 파일 업로드 완료: {file.filename} -> s3://{bucket_name}/{file.filename}")
        return True, s3_url, file.filename
    except ClientError as e:
        print(f"S3 업로드 실패: {str(e)}")
        return False, None, file.filename
    except Exception as e:
        print(f"파일 업로드 중 오류: {str(e)}")
        return False, None, file.filename


def process_embed_report(request: EmbedReportRequest):
    """
    보고서 임베딩 처리 로직 (백그라운드 실행용)
    
    1. S3에서 파일 다운로드
    2. data 폴더에 저장
    3. 임베딩 처리
    4. Supabase 업데이트
    """
    print(f"\n{'='*60}")
    print(f"📊 보고서 임베딩 처리 시작")
    print(f"{'='*60}")
    print(f"파일명: {request.file_name}")
    print(f"임베드 ID: {request.embed_id}")
    print(f"{'='*60}\n")
    
    try:
        # 1. 파일명에서 확장자 제거
        base_name = request.file_name.replace(".pdf", "")
        
        # 2. data 폴더 경로 설정
        current_dir = Path.cwd()
        data_dir = current_dir / "data"
        folder_path = data_dir / base_name
        
        # 3. 폴더 생성
        folder_path.mkdir(parents=True, exist_ok=True)
        print(f"📁 폴더 생성 완료: {folder_path}")
        
        # 4. S3에서 파일 다운로드
        local_file_path = folder_path / request.file_name
        print(f"⬇️  S3에서 파일 다운로드 중...")
        
        if not download_from_s3(request.file_name, local_file_path):
            raise Exception("S3 파일 다운로드 실패")
        
        print(f"✅ 파일 다운로드 완료: {local_file_path}")
        
        # 5. 임베딩 처리
        print(f"\n🔄 멀티모달 임베딩 처리 시작...")
        from embedding import process_single_folder_by_name
        
        result = process_single_folder_by_name(base_name)
        
        if not result.get("success"):
            raise Exception(f"임베딩 처리 실패: {result.get('error', 'Unknown error')}")
        
        print(f"✅ 임베딩 처리 완료")
        print(f"   처리된 subsection: {result.get('processed', 0)}개")
        
        # 6. Supabase 업데이트
        print(f"\n💾 Supabase 업데이트 중...")
        supabase = get_supabase_client()
        if not supabase:
            raise Exception("Supabase 클라이언트 초기화 실패")
        
        supabase.table("report_embed").update({
            "is_completed": True
        }).eq("id", request.embed_id).execute()
        
        print(f"✅ Supabase 업데이트 완료: is_completed = True")
        
        print(f"\n{'='*60}")
        print(f"✅ 보고서 임베딩 처리 완료!")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"❌ 보고서 임베딩 처리 실패")
        print(f"{'='*60}")
        print(f"오류: {str(e)}")
        print(f"{'='*60}\n")
        
        # 실패 시에도 Supabase 업데이트 시도 (에러 로그 기록용)
        try:
            supabase = get_supabase_client()
            if supabase:
                supabase.table("report_embed").update({
                    "is_completed": False,
                    "error_message": str(e)
                }).eq("id", request.embed_id).execute()
        except:
            pass


async def embed_report_start(background_tasks: BackgroundTasks, request: EmbedReportRequest):
    """
    보고서 임베딩 처리를 백그라운드에서 시작합니다.
    """
    background_tasks.add_task(process_embed_report, request)
    return EmbedReportResponse(
        success=True,
        message="embedding started",
        embed_id=request.embed_id
    )


async def upload_report(file: UploadFile):
    """
    업로드된 파일을 S3에 저장합니다.
    
    Args:
        file: FastAPI UploadFile 객체
        
    Returns:
        업로드 결과
    """
    try:
        # 파일 검증
        if not file.filename:
            return UploadReportResponse(
                success=False,
                message="파일명이 없습니다.",
                file_name="",
                s3_url=None
            )
        
        # S3에 업로드
        success, s3_url, file_name = await upload_file_to_s3(file)
        
        if success:
            return UploadReportResponse(
                success=True,
                message="파일이 성공적으로 업로드되었습니다.",
                file_name=file_name,
                s3_url=s3_url
            )
        else:
            return UploadReportResponse(
                success=False,
                message="S3 업로드에 실패했습니다.",
                file_name=file_name,
                s3_url=None
            )
            
    except Exception as e:
        return UploadReportResponse(
            success=False,
            message=f"업로드 중 오류가 발생했습니다: {str(e)}",
            file_name=file.filename or "",
            s3_url=None
        )


async def search_reports(request: SearchRequest):
    """
    보고서 유사도 검색
    
    사업아이디어와 핵심가치제안을 기반으로 벡터 임베딩을 생성하고,
    지정된 분야번호 내에서 가장 유사한 보고서를 검색합니다.
    
    Args:
        request: 검색 요청 (사업아이디어, 핵심가치제안, 분야번호, top_k)
        
    Returns:
        SearchResponse: 검색 결과 리스트
    """
    print("검색시작작")
    try:
        start_time = time.time()
        
        query_text = f"사업아이디어: {request.business_idea}\n핵심가치제안: {request.core_value}"
        
        openai_client = get_openai_client()
        if not openai_client:
            raise HTTPException(
                status_code=500,
                detail="OpenAI 클라이언트를 초기화할 수 없습니다. API 키를 확인해주세요."
            )
            
        response = openai_client.embeddings.create(
            input=query_text,
            model="text-embedding-3-small"
        )
        query_embedding = response.data[0].embedding
        
        supabase = get_supabase_client()
        if not supabase:
            raise HTTPException(
                status_code=500,
                detail="Supabase 클라이언트를 초기화할 수 없습니다. 환경변수를 확인해주세요."
            )
        
        search_result = supabase.rpc(
            "search_reports_by_similarity",
            {
                "query_embedding": query_embedding,
                "category_number": request.category_number,
                "match_count": request.top_k
            }
        ).execute()
        
        if not search_result.data:
            return SearchResponse(
                success=True,
                query=query_text,
                category_number=request.category_number,
                total_found=0,
                results=[]
            )
        
        results = [
            ReportResult(
                id=row["id"],
                번호=row["번호"],
                제목=row["제목"],
                분야=row["분야"],
                키워드=row["키워드"],
                보고서파일명=row["보고서파일명"],
                분야번호=row["분야번호"],
                similarity=float(row["similarity"])
            )
            for row in search_result.data
        ]
        
        elapsed_time = time.time() - start_time
        
        return SearchResponse(
            success=True,
            query=query_text,
            category_number=request.category_number,
            total_found=len(results),
            results=results
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"검색 중 오류가 발생했습니다: {str(e)}"
        )
