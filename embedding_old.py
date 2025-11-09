# -*- coding: utf-8 -*-
"""
멀티모달 RAG를 사용하여 지역수요5.pdf를 분석하고
procedure.json의 분야번호 1번 소목차들에 대해 retrieve 수행

노트북 파일(10-Multi_modal_RAG-GPT-4o.ipynb)의 접근 방식을 기반으로 재구성
"""

import os
import io
import re
import json
import uuid
import base64
from typing import List, Dict, Any, Tuple
from pathlib import Path

from PIL import Image
from unstructured.partition.pdf import partition_pdf
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.stores import InMemoryStore
from langchain_core.documents import Document
from langchain.retrievers import MultiVectorRetriever
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_text_splitters import CharacterTextSplitter

# Tesseract 경로 설정 (Windows/Linux 자동 감지)
import unstructured_pytesseract
import platform

# 운영체제에 따라 Tesseract 경로 설정
if platform.system() == "Windows":
    tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(tesseract_path):
        unstructured_pytesseract.pytesseract.tesseract_cmd = tesseract_path
        print(f"Tesseract 경로 설정 완료: {tesseract_path}")
    else:
        print(f"경고: Tesseract를 찾을 수 없습니다: {tesseract_path}")
else:
    # Linux/Docker 환경에서는 기본 경로 사용 (apt-get으로 설치됨)
    tesseract_path = "/usr/bin/tesseract"
    if os.path.exists(tesseract_path):
        print(f"Tesseract 경로 확인 완료: {tesseract_path}")
    else:
        print(f"경고: Tesseract를 찾을 수 없습니다: {tesseract_path}")

# .env 파일이 있으면 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("python-dotenv가 설치되지 않았습니다. 환경 변수를 직접 설정하세요.")

# OpenAI API 키 확인
if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = "sk-proj-..."  # 실제 API 키로 변경 필요
    print("주의: OpenAI API 키를 .env 파일에 설정하거나 코드에서 직접 설정하세요.")

# ============================================================================
# 유틸리티 함수들
# ============================================================================

def encode_image(image_path: str) -> str:
    """이미지 파일을 base64 문자열로 인코딩합니다."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def looks_like_base64(sb: str) -> bool:
    """문자열이 base64로 보이는지 확인합니다."""
    return re.match("^[A-Za-z0-9+/]+[=]{0,2}$", sb) is not None


def is_image_data(b64data: str) -> bool:
    """base64 데이터가 이미지인지 시작 부분을 보고 확인합니다."""
    image_signatures = {
        b"\xff\xd8\xff": "jpg",
        b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a": "png",
        b"\x47\x49\x46\x38": "gif",
        b"\x52\x49\x46\x46": "webp",
    }
    try:
        header = base64.b64decode(b64data)[:8]
        for sig, format in image_signatures.items():
            if header.startswith(sig):
                return True
        return False
    except Exception:
        return False


def resize_base64_image(base64_string: str, size=(1300, 600)) -> str:
    """Base64 문자열로 인코딩된 이미지의 크기를 조정합니다."""
    img_data = base64.b64decode(base64_string)
    img = Image.open(io.BytesIO(img_data))
    
    resized_img = img.resize(size, Image.LANCZOS)
    
    buffered = io.BytesIO()
    resized_img.save(buffered, format=img.format)
    
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def split_image_text_types(docs: List) -> Dict[str, List]:
    """base64로 인코딩된 이미지와 텍스트를 분리합니다."""
    b64_images = []
    texts = []
    
    for doc in docs:
        if isinstance(doc, Document):
            doc = doc.page_content
        if looks_like_base64(doc) and is_image_data(doc):
            doc = resize_base64_image(doc, size=(1300, 600))
            b64_images.append(doc)
        else:
            texts.append(doc)
    
    return {"images": b64_images, "texts": texts}


# ============================================================================
# PDF 처리 함수들
# ============================================================================

def extract_pdf_elements(pdf_path: str, image_output_path: str) -> Tuple[List, List]:
    """
    PDF 파일에서 이미지, 테이블, 그리고 텍스트 조각을 추출합니다.
    
    Args:
        pdf_path: PDF 파일의 전체 경로
        image_output_path: 이미지(.jpg)를 저장할 디렉토리 경로
        
    Returns:
        raw_pdf_elements: 추출된 원본 요소들
    """
    print(f"PDF 파일 파티셔닝 중: {pdf_path}")
    
    return partition_pdf(
        filename=pdf_path,
        strategy="fast",  # onnxruntime 없이 작동하는 fast 전략 사용
        extract_images_in_pdf=True,  # PDF 내 이미지 추출 활성화
        infer_table_structure=True,  # 테이블 구조 추론 활성화
        chunking_strategy="by_title",  # 제목별로 텍스트 조각화
        max_characters=4000,  # 최대 문자 수
        new_after_n_chars=3800,  # 이 문자 수 이후에 새로운 조각 생성
        combine_text_under_n_chars=2000,  # 이 문자 수 이하의 텍스트는 결합
        image_output_dir_path=image_output_path,  # 이미지 출력 디렉토리 경로
        languages=["kor", "eng"],  # OCR 언어 설정 (한국어, 영어)
    )


def categorize_elements(raw_pdf_elements: List) -> Tuple[List[str], List[str]]:
    """
    PDF에서 추출된 요소를 테이블과 텍스트로 분류합니다.
    
    Args:
        raw_pdf_elements: unstructured.documents.elements의 리스트
        
    Returns:
        texts: 텍스트 요소 리스트
        tables: 테이블 요소 리스트
    """
    tables = []
    texts = []
    
    for element in raw_pdf_elements:
        if "unstructured.documents.elements.Table" in str(type(element)):
            tables.append(str(element))
        elif "unstructured.documents.elements.CompositeElement" in str(type(element)):
            texts.append(str(element))
    
    return texts, tables


# ============================================================================
# 요약 생성 함수들
# ============================================================================

def generate_text_summaries(texts: List[str], tables: List[str], summarize_texts=False) -> Tuple[List[str], List[str]]:
    """
    텍스트 요소 요약
    
    Args:
        texts: 문자열 리스트
        tables: 문자열 리스트
        summarize_texts: 텍스트 요약 여부를 결정. True/False
        
    Returns:
        text_summaries: 텍스트 요약 리스트
        table_summaries: 테이블 요약 리스트
    """
    print("\n텍스트 및 테이블 요약 생성 중...")
    
    # 프롬프트 설정
    prompt_text = """You are an assistant tasked with summarizing tables and text for retrieval. \
    These summaries will be embedded and used to retrieve the raw text or table elements. \
    Give a concise summary of the table or text that is well optimized for retrieval. Table or text: {element} """
    prompt = ChatPromptTemplate.from_template(prompt_text)
    
    # 텍스트 요약 체인
    model = ChatOpenAI(temperature=0, model="gpt-4")
    summarize_chain = {"element": lambda x: x} | prompt | model | StrOutputParser()
    
    # 요약을 위한 빈 리스트 초기화
    text_summaries = []
    table_summaries = []
    
    # 제공된 텍스트에 대해 요약이 요청되었을 경우 적용
    if texts and summarize_texts:
        print(f"  텍스트 {len(texts)}개 요약 중...")
        text_summaries = summarize_chain.batch(texts, {"max_concurrency": 5})
    elif texts:
        text_summaries = texts
    
    # 제공된 테이블에 적용
    if tables:
        print(f"  테이블 {len(tables)}개 요약 중...")
        table_summaries = summarize_chain.batch(tables, {"max_concurrency": 5})
    
    print(f"요약 완료 - 텍스트: {len(text_summaries)}, 테이블: {len(table_summaries)}")
    
    return text_summaries, table_summaries


def image_summarize(img_base64: str, prompt: str) -> str:
    """이미지 요약을 생성합니다."""
    chat = ChatOpenAI(model="gpt-4o", max_tokens=2048)
    
    msg = chat.invoke(
        [
            HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"},
                    },
                ]
            )
        ]
    )
    return msg.content


def generate_img_summaries(path: str) -> Tuple[List[str], List[str]]:
    """
    이미지에 대한 요약과 base64 인코딩된 문자열을 생성합니다.
    
    Args:
        path: Unstructured에 의해 추출된 .jpg 파일 목록의 경로
        
    Returns:
        img_base64_list: base64로 인코딩된 이미지 리스트
        image_summaries: 이미지 요약 리스트
    """
    print("\n이미지 요약 생성 중...")
    
    # base64로 인코딩된 이미지를 저장할 리스트
    img_base64_list = []
    
    # 이미지 요약을 저장할 리스트
    image_summaries = []
    
    # 경로가 존재하지 않거나 비어있는 경우 처리
    if not os.path.exists(path):
        print(f"경고: 이미지 경로가 존재하지 않습니다: {path}")
        return img_base64_list, image_summaries
    
    # 경로 내 파일 목록 가져오기
    try:
        files = os.listdir(path)
    except Exception as e:
        print(f"경고: 이미지 경로를 읽을 수 없습니다: {path}, 오류: {e}")
        return img_base64_list, image_summaries
    
    # jpg 파일 필터링
    jpg_files = [f for f in files if f.endswith(".jpg")]
    
    if not jpg_files:
        print(f"경고: {path}에 .jpg 파일이 없습니다.")
        return img_base64_list, image_summaries
    
    # 요약을 위한 프롬프트
    prompt = """You are an assistant tasked with summarizing images for retrieval. \
    These summaries will be embedded and used to retrieve the raw image. \
    Give a concise summary of the image that is well optimized for retrieval."""
    
    # 이미지에 적용
    for img_file in sorted(jpg_files):
        img_path = os.path.join(path, img_file)
        base64_image = encode_image(img_path)
        img_base64_list.append(base64_image)
        image_summaries.append(image_summarize(base64_image, prompt))
    
    print(f"이미지 요약 완료 - {len(image_summaries)}개")
    
    return img_base64_list, image_summaries


# ============================================================================
# 멀티 벡터 검색기 생성
# ============================================================================

def create_multi_vector_retriever(
    vectorstore, 
    text_summaries: List[str], 
    texts: List[str], 
    table_summaries: List[str], 
    tables: List[str], 
    image_summaries: List[str], 
    images: List[str]
) -> MultiVectorRetriever:
    """
    요약을 색인화하지만 원본 이미지나 텍스트를 반환하는 검색기를 생성합니다.
    
    Args:
        vectorstore: 벡터 스토어
        text_summaries: 텍스트 요약 리스트
        texts: 원본 텍스트 리스트
        table_summaries: 테이블 요약 리스트
        tables: 원본 테이블 리스트
        image_summaries: 이미지 요약 리스트
        images: 원본 이미지(base64) 리스트
        
    Returns:
        retriever: MultiVectorRetriever 객체
    """
    print("\n멀티 벡터 검색기 생성 중...")
    
    # 저장 계층 초기화
    store = InMemoryStore()
    id_key = "doc_id"
    
    # 멀티 벡터 검색기 생성
    retriever = MultiVectorRetriever(
        vectorstore=vectorstore,
        docstore=store,
        id_key=id_key,
    )
    
    # 문서를 벡터 저장소와 문서 저장소에 추가하는 헬퍼 함수
    def add_documents(retriever, doc_summaries, doc_contents):
        doc_ids = [str(uuid.uuid4()) for _ in doc_contents]
        summary_docs = [
            Document(page_content=s, metadata={id_key: doc_ids[i]})
            for i, s in enumerate(doc_summaries)
        ]
        retriever.vectorstore.add_documents(summary_docs)
        retriever.docstore.mset(list(zip(doc_ids, doc_contents)))
    
    # 텍스트, 테이블, 이미지 추가
    if text_summaries:
        print(f"  텍스트 {len(text_summaries)}개 추가 중...")
        add_documents(retriever, text_summaries, texts)
    
    if table_summaries:
        print(f"  테이블 {len(table_summaries)}개 추가 중...")
        add_documents(retriever, table_summaries, tables)
    
    if image_summaries:
        print(f"  이미지 {len(image_summaries)}개 추가 중...")
        add_documents(retriever, image_summaries, images)
    
    print("검색기 생성 완료")
    return retriever


# ============================================================================
# RAG 체인 구성
# ============================================================================

def img_prompt_func(data_dict: Dict) -> List[HumanMessage]:
    """
    컨텍스트를 단일 문자열로 결합하고 이미지와 텍스트를 포함한 메시지를 생성합니다.
    
    Args:
        data_dict: question과 context를 포함한 딕셔너리
        
    Returns:
        messages: HumanMessage 리스트
    """
    formatted_texts = "\n".join(data_dict["context"]["texts"])
    messages = []
    
    # 이미지가 있으면 메시지에 추가
    if data_dict["context"]["images"]:
        for image in data_dict["context"]["images"]:
            image_message = {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image}"},
            }
            messages.append(image_message)
    
    # 분석을 위한 텍스트 추가
    text_message = {
        "type": "text",
        "text": (
            "당신은 비즈니스 및 기술 분야의 전문 분석가입니다.\n"
            "텍스트, 테이블, 이미지(차트나 그래프 등)가 혼합된 정보를 제공받을 것입니다.\n"
            "이 정보를 활용하여 사용자의 질문에 대해 한국어로 답변하세요.\n\n"
            f"사용자 질문: {data_dict['question']}\n\n"
            "제공된 텍스트 및 테이블:\n"
            f"{formatted_texts}"
        ),
    }
    messages.append(text_message)
    return [HumanMessage(content=messages)]


def multi_modal_rag_chain(retriever: MultiVectorRetriever):
    """
    멀티모달 RAG 체인을 생성합니다.
    
    Args:
        retriever: MultiVectorRetriever 객체
        
    Returns:
        chain: RAG 체인
    """
    # 멀티모달 LLM
    model = ChatOpenAI(temperature=0, model="gpt-4o", max_tokens=2048)
    
    # RAG 파이프라인
    chain = (
        {
            "context": retriever | RunnableLambda(split_image_text_types),
            "question": RunnablePassthrough(),
        }
        | RunnableLambda(img_prompt_func)
        | model
        | StrOutputParser()
    )
    
    return chain


# ============================================================================
# procedure.json 처리 함수들
# ============================================================================

def load_procedure_json(file_path: str) -> Dict:
    """procedure.json 파일을 로드합니다."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_all_subsections(procedure_data: Dict) -> List[Dict]:
    """
    procedure.json의 모든 subsections를 추출합니다.
    
    Args:
        procedure_data: procedure.json 데이터
        
    Returns:
        subsections: 모든 subsection 정보 리스트
    """
    subsections = []
    
    for section in procedure_data.get('sections', []):
        section_id = section.get('id')
        section_name = section.get('name')
        
        for subsection in section.get('subsections', []):
            if subsection.get('enabled', True):
                subsections.append({
                    'id': subsection.get('id'),
                    'name': subsection.get('name'),
                    'section_id': section_id,
                    'section_name': section_name,
                    'order': subsection.get('order'),
                    'maxChar': subsection.get('maxChar'),
                    'minChar': subsection.get('minChar')
                })
    
    return subsections


def retrieve_for_subsections(
    retriever: MultiVectorRetriever, 
    subsections: List[Dict], 
    output_dir: str = "output",
    top_k: int = 3
) -> Dict:
    """
    각 subsection에 대해 retrieval을 수행하고 개별 JSON 파일로 저장합니다.
    
    Args:
        retriever: MultiVectorRetriever 객체
        subsections: subsection 정보 리스트
        output_dir: 출력 디렉토리
        top_k: 반환할 최대 문서 수 (기본값: 3)
        
    Returns:
        summary: 전체 처리 요약
    """
    # 출력 디렉토리 생성
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\n총 {len(subsections)}개의 subsection에 대해 retrieval 수행 중...\n")
    
    summary = {
        "total_subsections": len(subsections),
        "processed": 0,
        "output_directory": output_dir,
        "subsections": []
    }
    
    for idx, subsection in enumerate(subsections, 1):
        subsection_id = subsection['id']
        subsection_name = subsection['name']
        
        print(f"[{idx}/{len(subsections)}] {subsection_id}: {subsection_name}")
        
        # Retrieval 수행
        docs = retriever.invoke(subsection_name, limit=top_k)
        
        # Context 추출 (최대 3개)
        contexts = []
        for i, doc in enumerate(docs[:top_k], 1):
            # 문서 타입 확인
            if isinstance(doc, str):
                # base64 이미지인지 확인
                if looks_like_base64(doc) and is_image_data(doc):
                    doc_type = "image"
                    # 이미지는 전체 base64 저장
                    content = doc
                else:
                    doc_type = "text"
                    content = doc
            else:
                doc_type = "text"
                content = str(doc)
            
            contexts.append({
                "rank": i,
                "type": doc_type,
                "content": content
            })
        
        # 각 subsection별로 JSON 파일 저장
        result_data = {
            "subsection_id": subsection_id,
            "subsection_name": subsection_name,
            "section_id": subsection['section_id'],
            "section_name": subsection['section_name'],
            "order": subsection['order'],
            "maxChar": subsection['maxChar'],
            "minChar": subsection['minChar'],
            "query": subsection_name,
            "retrieved_count": len(contexts),
            "contexts": contexts
        }
        
        # 파일명: subsection_id.json (예: 1-1.json, 1-2.json)
        output_file = os.path.join(output_dir, f"{subsection_id}.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        print(f"  → {len(contexts)}개 context 추출 완료")
        print(f"  → 저장: {output_file}\n")
        
        # 요약 정보 추가
        summary['subsections'].append({
            "id": subsection_id,
            "name": subsection_name,
            "contexts_count": len(contexts),
            "output_file": output_file
        })
        summary['processed'] += 1
    
    return summary


def save_summary(summary: Dict, output_file: str):
    """전체 처리 요약을 JSON 파일로 저장합니다."""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n전체 요약이 저장되었습니다: {output_file}")


# ============================================================================
# 메인 실행 함수
# ============================================================================

def process_single_folder_by_name(folder_name: str, procedure_file: str = "procedure.json") -> Dict[str, Any]:
    """
    폴더명으로 단일 폴더를 처리하는 함수 (외부 호출용)
    
    Args:
        folder_name: 처리할 폴더명 (data 폴더 내의 하위 폴더명)
        procedure_file: procedure.json 파일 경로 (기본값: "procedure.json")
    
    Returns:
        처리 결과 딕셔너리
    """
    print(f"\n🔍 process_single_folder_by_name 호출됨")
    print(f"   folder_name: {folder_name}")
    print(f"   procedure_file: {procedure_file}")
    
    current_dir = Path.cwd()
    data_dir = current_dir / "data"
    folder_path = data_dir / folder_name
    
    print(f"   current_dir: {current_dir}")
    print(f"   data_dir: {data_dir}")
    print(f"   folder_path: {folder_path}")
    print(f"   folder_path.exists(): {folder_path.exists()}")
    
    if not folder_path.exists():
        error_msg = f"폴더를 찾을 수 없습니다: {folder_path}"
        print(f"❌ {error_msg}")
        return {
            "folder": folder_name,
            "success": False,
            "error": error_msg
        }
    
    print(f"✅ 폴더 존재 확인 완료, process_single_folder 호출...")
    return process_single_folder(folder_path, procedure_file)


def process_single_folder(folder_path: Path, procedure_file: str) -> Dict[str, Any]:
    """단일 폴더를 처리하는 함수"""
    folder_name = folder_path.name
    print(f"\n{'='*60}")
    print(f"📁 처리 중: {folder_name}")
    print(f"{'='*60}")
    
    # 현재 작업 디렉토리 저장
    original_cwd = os.getcwd()
    
    try:
        # 폴더로 이동
        os.chdir(folder_path)
        
        # figures와 output 폴더 생성 (현재 디렉토리 기준)
        figures_dir = Path("figures")
        output_dir = Path("output")
        
        figures_dir.mkdir(exist_ok=True)
        output_dir.mkdir(exist_ok=True)
        
        # PDF 파일 찾기 (현재 디렉토리에서)
        pdf_files = list(Path(".").glob("*.pdf"))
        if not pdf_files:
            return {
                "folder": folder_name,
                "success": False,
                "error": "PDF 파일을 찾을 수 없습니다"
            }
        
        pdf_file = pdf_files[0].name
        print(f"📄 PDF 파일: {pdf_file}")
        
        # 파일 경로 설정 (모두 상대 경로)
        pdf_full_path = pdf_file  # PDF 파일 (현재 디렉토리)
        image_output_path = "figures"  # 이미지를 저장할 경로
        summary_file = output_dir / "_summary.json"
        
        # 1. PDF 요소 추출
        print("\n[1/10] PDF 요소 추출 중...")
        raw_pdf_elements = extract_pdf_elements(pdf_full_path, image_output_path)
        
        # 2. 텍스트와 테이블 추출
        print("\n[2/10] 텍스트와 테이블 분류 중...")
        texts, tables = categorize_elements(raw_pdf_elements)
        print(f"추출 완료 - 텍스트: {len(texts)}개, 테이블: {len(tables)}개")
        
        # 3. 텍스트에 대해 특정 토큰 크기 적용
        print("\n[3/10] 텍스트 분할 중...")
        text_splitter = CharacterTextSplitter.from_tiktoken_encoder(
            chunk_size=4000, 
            chunk_overlap=0
        )
        joined_texts = " ".join(texts)
        texts_4k_token = text_splitter.split_text(joined_texts)
        print(f"텍스트 분할 완료 - {len(texts_4k_token)}개 청크")
        
        # 4. 텍스트 및 테이블 요약 생성
        print("\n[4/10] 텍스트 및 테이블 요약 생성 중...")
        text_summaries, table_summaries = generate_text_summaries(
            texts_4k_token, 
            tables, 
            summarize_texts=True
        )
        
        # 5. 이미지 요약 생성
        print("\n[5/10] 이미지 요약 생성 중...")
        img_base64_list, image_summaries = generate_img_summaries(image_output_path)
        
        # 6. 벡터 스토어 생성
        print("\n[6/10] 벡터 스토어 생성 중...")
        # Chroma collection 이름은 영문, 숫자, 언더스코어, 하이픈, 점만 허용
        # 한글 폴더명을 안전한 이름으로 변환 (UUID 사용)
        import hashlib
        safe_collection_name = f"rag_{hashlib.md5(folder_name.encode()).hexdigest()[:16]}"
        vectorstore = Chroma(
            collection_name=safe_collection_name, 
            embedding_function=OpenAIEmbeddings()
        )
        
        # 7. 멀티 벡터 검색기 생성
        print("\n[7/10] 멀티 벡터 검색기 생성 중...")
        retriever = create_multi_vector_retriever(
            vectorstore,
            text_summaries,
            texts_4k_token,
            table_summaries,
            tables,
            image_summaries,
            img_base64_list,
        )
        
        # 8. RAG 체인 생성
        print("\n[8/10] RAG 체인 생성 중...")
        chain = multi_modal_rag_chain(retriever)
        print("멀티모달 RAG 체인 생성 완료")
        
        # 9. procedure.json에서 모든 subsection 추출
        print("\n[9/10] procedure.json 로드 및 subsection 추출 중...")
        # 루트 디렉토리의 procedure.json 사용
        root_procedure_file = Path(original_cwd) / procedure_file
        procedure_data = load_procedure_json(str(root_procedure_file))
        subsections = extract_all_subsections(procedure_data)
        print(f"총 {len(subsections)}개의 subsection 추출 완료")
        
        # 10. 각 subsection에 대해 retrieval 수행 및 개별 파일로 저장
        print("\n[10/10] 각 subsection별 retrieval 수행 및 저장 중...")
        summary = retrieve_for_subsections(
            retriever, 
            subsections, 
            output_dir=str(output_dir),
            top_k=3
        )
        
        # 11. 전체 요약 저장
        save_summary(summary, str(summary_file))
        
        # 결과 요약 출력
        print(f"\n{'='*60}")
        print(f"✅ {folder_name} 처리 완료!")
        print(f"{'='*60}")
        print(f"총 처리된 subsection: {summary['processed']}개")
        print(f"출력 디렉토리: {output_dir}")
        
        return {
            "folder": folder_name,
            "success": True,
            "processed": summary['processed'],
            "output_dir": str(output_dir)
        }
        
    except Exception as e:
        print(f"❌ {folder_name} 처리 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "folder": folder_name,
            "success": False,
            "error": str(e)
        }
    finally:
        # 원래 작업 디렉토리로 복귀
        os.chdir(original_cwd)


def main():
    """메인 실행 함수 - data 폴더 순회 및 조건부 처리"""
    print("=" * 80)
    print("🔄 data 폴더 순회 및 멀티모달 RAG 처리")
    print("figures와 output 폴더가 없는 경우에만 처리 수행")
    print("=" * 80)
    
    # data 폴더 경로
    data_dir = Path("data")
    if not data_dir.exists():
        print(f"❌ data 폴더를 찾을 수 없습니다: {data_dir}")
        return
    
    # procedure.json 파일 경로 (루트에 있다고 가정)
    procedure_file = "procedure.json"
    if not os.path.exists(procedure_file):
        print(f"❌ procedure.json 파일을 찾을 수 없습니다: {procedure_file}")
        return
    
    # data 폴더 내의 모든 하위 폴더 순회
    folders = [f for f in data_dir.iterdir() if f.is_dir()]
    folders.sort()  # 이름순 정렬
    
    print(f"\n📂 총 {len(folders)}개의 폴더를 발견했습니다.")
    
    processed_folders = []
    skipped_folders = []
    error_folders = []
    
    for idx, folder in enumerate(folders, 1):
        print(f"\n{'='*80}")
        print(f"진행 상황: [{idx}/{len(folders)}]")
        print(f"{'='*80}")
        
        figures_dir = folder / "figures"
        output_dir = folder / "output"
        
        # figures 폴더나 output 폴더 중 하나라도 존재하면 건너뛰기
        figures_exists = figures_dir.exists()
        output_exists = output_dir.exists()
        
        if figures_exists or output_exists:
            skip_reason = []
            if figures_exists:
                skip_reason.append("figures")
            if output_exists:
                skip_reason.append("output")
            print(f"⏭️  건너뛰기: {folder.name} ({', '.join(skip_reason)} 폴더가 이미 존재)")
            skipped_folders.append(folder.name)
            continue
        
        # PDF 파일 확인
        pdf_files = list(folder.glob("*.pdf"))
        if not pdf_files:
            print(f"⚠️  건너뛰기: {folder.name} (PDF 파일 없음)")
            skipped_folders.append(folder.name)
            continue
        
        # 처리 수행
        result = process_single_folder(folder, procedure_file)
        
        if result["success"]:
            processed_folders.append(result)
        else:
            error_folders.append(result)
    
    # 최종 결과 요약
    print(f"\n{'='*80}")
    print("📊 최종 처리 결과")
    print(f"{'='*80}")
    print(f"✅ 성공적으로 처리: {len(processed_folders)}개")
    print(f"⏭️  건너뛴 폴더: {len(skipped_folders)}개")
    print(f"❌ 오류 발생: {len(error_folders)}개")
    
    if processed_folders:
        print(f"\n✅ 처리된 폴더 목록:")
        for result in processed_folders:
            print(f"  - {result['folder']}: {result['processed']}개 subsection 처리")
    
    if skipped_folders:
        print(f"\n⏭️  건너뛴 폴더 목록:")
        for folder_name in skipped_folders[:10]:  # 처음 10개만 표시
            print(f"  - {folder_name}")
        if len(skipped_folders) > 10:
            print(f"  ... 외 {len(skipped_folders) - 10}개")
    
    if error_folders:
        print(f"\n❌ 오류 발생 폴더:")
        for result in error_folders:
            print(f"  - {result['folder']}: {result['error']}")
    
    print(f"\n{'='*80}")


if __name__ == "__main__":
    main()

