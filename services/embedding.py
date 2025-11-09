# -*- coding: utf-8 -*-
"""
멀티모달 RAG - PyMuPDF + Pytesseract 기반
Unstructured 대신 PyMuPDF와 Pytesseract를 직접 사용하여 ONNX Runtime 의존성 제거
"""

import os
import io
import re
import json
import uuid
import base64
from typing import List, Dict, Any, Tuple
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image
import pytesseract
from pdf2image import convert_from_path

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


# ============================================================================
# 유틸리티 함수들
# ============================================================================

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


# Tesseract 경로 설정
import platform

if platform.system() == "Windows":
    tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        print(f"✅ Tesseract 경로 설정 완료: {tesseract_path}")
else:
    tesseract_path = "/usr/bin/tesseract"
    if os.path.exists(tesseract_path):
        print(f"✅ Tesseract 경로 확인 완료: {tesseract_path}")

# 환경 변수에서 OpenAI API 키 가져오기
from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")


def extract_text_and_images_from_pdf(pdf_path: str, output_folder: str) -> Tuple[List[Dict], List[str]]:
    """
    PyMuPDF를 사용하여 PDF에서 텍스트와 이미지를 추출합니다.
    
    Args:
        pdf_path: PDF 파일 경로
        output_folder: 이미지 저장 폴더
        
    Returns:
        (텍스트 요소 리스트, 이미지 경로 리스트)
    """
    print(f"📄 PDF 파일 처리 중: {pdf_path}")
    
    # 이미지 저장 폴더 생성
    images_folder = os.path.join(output_folder, "images")
    os.makedirs(images_folder, exist_ok=True)
    
    text_elements = []
    image_paths = []
    
    # PyMuPDF로 PDF 열기
    doc = fitz.open(pdf_path)
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # 텍스트 추출
        text = page.get_text()
        if text.strip():
            text_elements.append({
                "type": "text",
                "content": text,
                "page": page_num + 1,
                "metadata": {"source": pdf_path, "page": page_num + 1}
            })
        
        # 페이지 전체를 하나의 이미지로 렌더링 (페이지당 1개 이미지)
        try:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2배 해상도
            image_filename = f"page_{page_num + 1}_full.png"
            image_path = os.path.join(images_folder, image_filename)
            pix.save(image_path)
            
            image_paths.append(image_path)
            print(f"  ✅ 페이지 렌더링: {image_filename}")
            
        except Exception as e:
            print(f"  ⚠️  페이지 렌더링 실패 (page {page_num + 1}): {e}")
    
    doc.close()
    
    # 텍스트가 없는 경우 OCR 수행
    if not text_elements or all(not elem["content"].strip() for elem in text_elements):
        print("📝 텍스트가 없습니다. OCR 수행 중...")
        text_elements = perform_ocr_on_pdf(pdf_path, output_folder)
    
    print(f"✅ 추출 완료: 텍스트 {len(text_elements)}개, 페이지 이미지 {len(image_paths)}개")
    return text_elements, image_paths


def perform_ocr_on_pdf(pdf_path: str, output_folder: str) -> List[Dict]:
    """
    pdf2image와 pytesseract를 사용하여 PDF에서 OCR을 수행합니다.
    
    Args:
        pdf_path: PDF 파일 경로
        output_folder: 작업 폴더
        
    Returns:
        텍스트 요소 리스트
    """
    print("🔍 OCR 처리 시작...")
    text_elements = []
    
    try:
        # PDF를 이미지로 변환
        images = convert_from_path(pdf_path, dpi=200)
        
        for page_num, image in enumerate(images, start=1):
            # Pytesseract로 OCR 수행 (한글 + 영어)
            text = pytesseract.image_to_string(image, lang='kor+eng')
            
            if text.strip():
                text_elements.append({
                    "type": "text",
                    "content": text,
                    "page": page_num,
                    "metadata": {"source": pdf_path, "page": page_num, "ocr": True}
                })
                print(f"  ✅ OCR 완료: 페이지 {page_num}")
        
        print(f"✅ OCR 처리 완료: {len(text_elements)}개 페이지")
        
    except Exception as e:
        print(f"❌ OCR 처리 실패: {e}")
    
    return text_elements


def encode_image_to_base64(image_path: str) -> str:
    """이미지를 base64로 인코딩합니다."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def summarize_text_with_gpt(text: str, model: str = "gpt-4o-mini") -> str:
    """
    GPT를 사용하여 텍스트를 요약합니다.
    
    Args:
        text: 요약할 텍스트
        model: 사용할 GPT 모델
        
    Returns:
        요약된 텍스트
    """
    prompt = f"""다음 텍스트를 간결하게 요약해주세요. 핵심 내용만 추출하세요:

{text}

요약:"""
    
    llm = ChatOpenAI(model=model, temperature=0)
    response = llm.invoke(prompt)
    return response.content


def summarize_image_with_gpt(image_path: str, model: str = "gpt-4o") -> str:
    """
    GPT-4 Vision을 사용하여 이미지를 요약합니다.
    
    Args:
        image_path: 이미지 파일 경로
        model: 사용할 GPT 모델 (gpt-4o 또는 gpt-4-vision-preview)
        
    Returns:
        이미지 설명
    """
    base64_image = encode_image_to_base64(image_path)
    
    llm = ChatOpenAI(model=model, max_tokens=1024, temperature=0)
    
    msg = llm.invoke(
        [
            HumanMessage(
                content=[
                    {"type": "text", "text": "이 이미지의 내용을 상세하게 설명해주세요. 텍스트, 도표, 그래프 등 모든 정보를 포함하세요."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ]
            )
        ]
    )
    return msg.content


def create_text_summaries(texts: List[Dict], summarize: bool = True) -> Tuple[List[str], List[str]]:
    """
    텍스트 요소들을 요약하고 ID를 생성합니다.
    
    Args:
        texts: 텍스트 요소 리스트
        summarize: 요약 수행 여부
        
    Returns:
        (요약 리스트, ID 리스트)
    """
    text_summaries = []
    text_ids = []
    
    for idx, text_elem in enumerate(texts):
        text_content = text_elem["content"]
        
        if summarize and len(text_content) > 500:
            try:
                summary = summarize_text_with_gpt(text_content)
                text_summaries.append(summary)
                print(f"  ✅ 텍스트 {idx + 1} 요약 완료")
            except Exception as e:
                print(f"  ⚠️  텍스트 {idx + 1} 요약 실패: {e}")
                text_summaries.append(text_content[:500] + "...")
        else:
            text_summaries.append(text_content)
        
        text_ids.append(str(uuid.uuid4()))
    
    return text_summaries, text_ids


def create_image_summaries(image_paths: List[str]) -> Tuple[List[str], List[str]]:
    """
    이미지들을 GPT-4 Vision으로 요약합니다.
    
    Args:
        image_paths: 이미지 경로 리스트
        
    Returns:
        (요약 리스트, ID 리스트)
    """
    image_summaries = []
    image_ids = []
    
    for idx, image_path in enumerate(image_paths):
        try:
            summary = summarize_image_with_gpt(image_path)
            image_summaries.append(summary)
            image_ids.append(str(uuid.uuid4()))
            print(f"  ✅ 이미지 {idx + 1} 요약 완료")
        except Exception as e:
            print(f"  ⚠️  이미지 {idx + 1} 요약 실패: {e}")
    
    return image_summaries, image_ids


def create_multi_vector_retriever(
    text_summaries: List[str],
    texts: List[Dict],
    text_ids: List[str],
    image_summaries: List[str],
    image_paths: List[str],
    image_ids: List[str],
    collection_name: str = "multi_modal_rag"
) -> MultiVectorRetriever:
    """
    멀티벡터 리트리버를 생성합니다.
    
    Args:
        text_summaries: 텍스트 요약 리스트
        texts: 원본 텍스트 요소 리스트
        text_ids: 텍스트 ID 리스트
        image_summaries: 이미지 요약 리스트
        image_paths: 이미지 경로 리스트
        image_ids: 이미지 ID 리스트
        collection_name: Chroma 컬렉션 이름
        
    Returns:
        MultiVectorRetriever
    """
    print("🔧 멀티벡터 리트리버 생성 중...")
    
    # Chroma 벡터스토어 생성
    vectorstore = Chroma(
        collection_name=collection_name,
        embedding_function=OpenAIEmbeddings()
    )
    
    # 문서 저장소 생성
    store = InMemoryStore()
    id_key = "doc_id"
    
    # 리트리버 생성
    retriever = MultiVectorRetriever(
        vectorstore=vectorstore,
        docstore=store,
        id_key=id_key,
    )
    
    # 텍스트 문서 추가
    if text_summaries:
        doc_ids_text = text_ids
        summary_texts = [
            Document(page_content=s, metadata={id_key: doc_ids_text[i]})
            for i, s in enumerate(text_summaries)
        ]
        retriever.vectorstore.add_documents(summary_texts)
        retriever.docstore.mset(list(zip(doc_ids_text, [t["content"] for t in texts])))
        print(f"  ✅ 텍스트 문서 {len(text_summaries)}개 추가")
    
    # 이미지 문서 추가
    if image_summaries:
        doc_ids_images = image_ids
        summary_images = [
            Document(page_content=s, metadata={id_key: doc_ids_images[i]})
            for i, s in enumerate(image_summaries)
        ]
        retriever.vectorstore.add_documents(summary_images)
        retriever.docstore.mset(list(zip(doc_ids_images, image_paths)))
        print(f"  ✅ 이미지 문서 {len(image_summaries)}개 추가")
    
    print("✅ 멀티벡터 리트리버 생성 완료")
    return retriever


def process_single_folder_by_name(
    folder_name: str,
    base_data_path: str = "./data",
    summarize_texts: bool = False,
    collection_name: str = None
) -> MultiVectorRetriever:
    """
    폴더명으로 PDF를 찾아서 처리하고 멀티벡터 리트리버를 생성합니다.
    
    Args:
        folder_name: 폴더 이름 (예: "성적증명서2222")
        base_data_path: 기본 데이터 경로
        summarize_texts: 텍스트 요약 수행 여부
        collection_name: Chroma 컬렉션 이름
        
    Returns:
        MultiVectorRetriever
    """
    print(f"\n{'='*60}")
    print(f"📁 폴더 처리 시작: {folder_name}")
    print(f"{'='*60}\n")
    
    # 폴더 경로 설정
    folder_path = os.path.join(base_data_path, folder_name)
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"폴더를 찾을 수 없습니다: {folder_path}")
    
    # PDF 파일 찾기
    pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]
    if not pdf_files:
        raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {folder_path}")
    
    pdf_path = os.path.join(folder_path, pdf_files[0])
    print(f"📄 PDF 파일: {pdf_path}")
    
    # 1. PDF에서 텍스트와 이미지 추출
    texts, image_paths = extract_text_and_images_from_pdf(pdf_path, folder_path)
    
    # 2. 텍스트 요약
    print("\n📝 텍스트 처리 중...")
    text_summaries, text_ids = create_text_summaries(texts, summarize=summarize_texts)
    
    # 3. 이미지 요약
    print("\n🖼️  이미지 처리 중...")
    image_summaries, image_ids = create_image_summaries(image_paths)
    
    # 4. 멀티벡터 리트리버 생성
    if collection_name is None:
        # Chroma는 영문자, 숫자, 언더스코어, 하이픈만 허용
        # 한글 및 특수문자를 제거하고 embed_id 사용
        import re
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '', folder_name)
        if not safe_name or len(safe_name) < 3:
            # 안전한 이름이 없으면 타임스탬프 사용
            import time
            safe_name = f"collection_{int(time.time())}"
        collection_name = f"rag_{safe_name}"
    
    retriever = create_multi_vector_retriever(
        text_summaries=text_summaries,
        texts=texts,
        text_ids=text_ids,
        image_summaries=image_summaries,
        image_paths=image_paths,
        image_ids=image_ids,
        collection_name=collection_name
    )
    
    print(f"\n{'='*60}")
    print(f"✅ 폴더 처리 완료: {folder_name}")
    print(f"{'='*60}\n")
    
    # 성공 정보를 포함한 딕셔너리 반환
    return {
        "success": True,
        "retriever": retriever,
        "text_count": len(text_summaries),
        "image_count": len(image_summaries),
        "collection_name": collection_name
    }


def retrieve_and_generate(query: str, retriever: MultiVectorRetriever, model: str = "gpt-4o") -> str:
    """
    쿼리에 대해 검색하고 답변을 생성합니다.
    
    Args:
        query: 검색 쿼리
        retriever: MultiVectorRetriever
        model: 사용할 GPT 모델
        
    Returns:
        생성된 답변
    """
    print(f"\n🔍 검색 쿼리: {query}")
    
    # 관련 문서 검색
    docs = retriever.get_relevant_documents(query, top_k=5)
    
    # 컨텍스트 구성
    context_parts = []
    for i, doc in enumerate(docs, 1):
        if isinstance(doc, str):
            if doc.endswith(('.png', '.jpg', '.jpeg')):
                # 이미지인 경우
                context_parts.append(f"[이미지 {i}]: {doc}")
            else:
                # 텍스트인 경우
                context_parts.append(f"[문서 {i}]:\n{doc}\n")
    
    context = "\n\n".join(context_parts)
    
    # 프롬프트 생성
    prompt = f"""다음 컨텍스트를 바탕으로 질문에 답변해주세요:

컨텍스트:
{context}

질문: {query}

답변:"""
    
    # GPT로 답변 생성
    llm = ChatOpenAI(model=model, temperature=0)
    response = llm.invoke(prompt)
    
    print(f"✅ 답변 생성 완료")
    return response.content


def load_procedure_json(file_path: str = "./procedure.json") -> Dict:
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
    
    # procedure.json의 field_number와 field_name 가져오기
    field_number = procedure_data.get('field_number')
    field_name = procedure_data.get('field_name', '')
    
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
                    'field_number': field_number,
                    'field_name': field_name,
                    'order': subsection.get('order'),
                    'maxChar': subsection.get('maxChar'),
                    'minChar': subsection.get('minChar')
                })
    
    return subsections


def retrieve_for_subsections(
    retriever: MultiVectorRetriever, 
    subsections: List[Dict], 
    output_dir: str = "./output",
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
    
    print(f"\n📋 총 {len(subsections)}개의 subsection에 대해 retrieval 수행 중...\n")
    
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
        
        # Retrieval 수행 (텍스트 최소 개수 확보를 위해 더 많이 가져옴)
        try:
            # 이미지 필터링을 고려하여 top_k * 3 개 가져옴
            docs = retriever.get_relevant_documents(subsection_name)[:(top_k * 3)]
        except Exception as e:
            print(f"  ⚠️  Retrieval 실패: {e}")
            continue
        
        # Context 추출 (텍스트만, 최대 top_k개)
        contexts = []
        all_contents = []  # 모든 컨텐츠 저장 (필터링 전)
        rank = 1
        
        for doc in docs:
            # Document 객체에서 page_content 추출
            if hasattr(doc, 'page_content'):
                content = doc.page_content
            elif isinstance(doc, str):
                content = doc
            else:
                content = str(doc)
            
            all_contents.append(content)
            
            # 이미 충분한 텍스트를 확보했으면 중단
            if len(contexts) >= top_k:
                continue
            
            # 이미지는 제외하고 텍스트만 저장
            # base64 이미지 또는 이미지 경로 제외
            is_base64_image = looks_like_base64(content) and is_image_data(content)
            is_image_path = content.endswith(('.png', '.jpg', '.jpeg', '.gif'))
            
            if not is_base64_image and not is_image_path:
                contexts.append({
                    "rank": rank,
                    "type": "text",
                    "content": content
                })
                rank += 1
        
        # contexts가 비어있으면 가장 유사한 것 1개라도 포함
        if len(contexts) == 0 and len(all_contents) > 0:
            print(f"  ⚠️  텍스트 context가 없어 가장 유사한 결과 1개 포함")
            contexts.append({
                "rank": 1,
                "type": "text",
                "content": all_contents[0]
            })
        
        # 각 subsection별로 JSON 파일 저장
        result_data = {
            "subsection_id": subsection_id,
            "subsection_name": subsection_name,
            "section_id": subsection['section_id'],
            "section_name": subsection['section_name'],
            "field_number": subsection.get('field_number'),
            "field_name": subsection.get('field_name', ''),
            "query": subsection_name,
            "retrieved_count": len(contexts),
            "contexts": contexts
        }
        
        # 파일명: subsection_id.json (예: 1-1.json)
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
