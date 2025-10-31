"""
보고서 생성 및 임베딩 관련 Celery 태스크
"""

from celery import Task
from celery_config import celery_app
from services.report import (
    GenerateReportRequest,
    EmbedReportRequest,
    process_report_generation,
    process_embed_report
)
import traceback


class CallbackTask(Task):
    """
    작업 상태 변경 시 콜백을 제공하는 커스텀 Task 클래스
    """
    
    def on_success(self, retval, task_id, args, kwargs):
        """작업 성공 시 호출"""
        print(f"✅ Task {task_id} succeeded: {retval}")
        return super().on_success(retval, task_id, args, kwargs)
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """작업 실패 시 호출"""
        print(f"❌ Task {task_id} failed: {exc}")
        print(f"Traceback: {einfo}")
        return super().on_failure(exc, task_id, args, kwargs, einfo)
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """작업 재시도 시 호출"""
        print(f"🔄 Task {task_id} retrying: {exc}")
        return super().on_retry(exc, task_id, args, kwargs, einfo)


@celery_app.task(
    bind=True,
    base=CallbackTask,
    name="tasks.report_tasks.generate_report_task",
    max_retries=3,
    default_retry_delay=60
)
def generate_report_task(self, business_idea: str, core_value: str, file_name: str, report_id: str):
    """
    전체 사업계획서 생성 태스크
    
    Args:
        self: Celery task instance
        business_idea: 사업 아이디어
        core_value: 핵심 가치
        file_name: 참고 PDF 파일명
        report_id: Supabase report_create 테이블의 UUID
        
    Returns:
        dict: 생성 결과
    """
    try:
        print(f"\n{'='*60}")
        print(f"📊 Celery Task 시작: 보고서 생성")
        print(f"{'='*60}")
        print(f"Task ID: {self.request.id}")
        print(f"Report ID: {report_id}")
        print(f"{'='*60}\n")
        
        # 작업 상태를 PROGRESS로 업데이트
        self.update_state(
            state="PROGRESS",
            meta={
                "status": "보고서 생성 중...",
                "report_id": report_id,
                "current": 0,
                "total": 100
            }
        )
        
        # GenerateReportRequest 객체 생성
        request = GenerateReportRequest(
            business_idea=business_idea,
            core_value=core_value,
            file_name=file_name,
            report_id=report_id
        )
        
        # 보고서 생성 실행
        result = process_report_generation(request)
        
        if result.success:
            print(f"\n{'='*60}")
            print(f"✅ Celery Task 완료: 보고서 생성")
            print(f"{'='*60}")
            print(f"Task ID: {self.request.id}")
            print(f"Report ID: {report_id}")
            print(f"생성된 섹션: {len(result.generated_sections)}개")
            print(f"{'='*60}\n")
            
            return {
                "success": True,
                "message": result.message,
                "report_id": result.report_id,
                "generated_sections": result.generated_sections,
                "elapsed_time": result.elapsed_time,
                "task_id": self.request.id
            }
        else:
            print(f"\n{'='*60}")
            print(f"❌ Celery Task 실패: 보고서 생성")
            print(f"{'='*60}")
            print(f"Task ID: {self.request.id}")
            print(f"Report ID: {report_id}")
            print(f"오류: {result.message}")
            print(f"{'='*60}\n")
            
            return {
                "success": False,
                "message": result.message,
                "report_id": result.report_id,
                "generated_sections": result.generated_sections,
                "elapsed_time": result.elapsed_time,
                "task_id": self.request.id
            }
            
    except Exception as exc:
        print(f"\n{'='*60}")
        print(f"❌ Celery Task 예외 발생: 보고서 생성")
        print(f"{'='*60}")
        print(f"Task ID: {self.request.id}")
        print(f"Report ID: {report_id}")
        print(f"예외: {str(exc)}")
        print(f"Traceback:\n{traceback.format_exc()}")
        print(f"{'='*60}\n")
        
        # 재시도 로직
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {
                "success": False,
                "message": f"최대 재시도 횟수 초과: {str(exc)}",
                "report_id": report_id,
                "generated_sections": [],
                "elapsed_time": 0,
                "task_id": self.request.id
            }


@celery_app.task(
    bind=True,
    base=CallbackTask,
    name="tasks.report_tasks.embed_report_task",
    max_retries=3,
    default_retry_delay=60
)
def embed_report_task(self, file_name: str, embed_id: str):
    """
    보고서 멀티모달 임베딩 처리 태스크
    
    Args:
        self: Celery task instance
        file_name: S3에 저장된 PDF 파일명
        embed_id: Supabase report_embed 테이블의 ID
        
    Returns:
        dict: 임베딩 결과
    """
    try:
        print(f"\n{'='*60}")
        print(f"📊 Celery Task 시작: 보고서 임베딩")
        print(f"{'='*60}")
        print(f"Task ID: {self.request.id}")
        print(f"Embed ID: {embed_id}")
        print(f"File Name: {file_name}")
        print(f"{'='*60}\n")
        
        # 작업 상태를 PROGRESS로 업데이트
        self.update_state(
            state="PROGRESS",
            meta={
                "status": "임베딩 처리 중...",
                "embed_id": embed_id,
                "file_name": file_name,
                "current": 0,
                "total": 100
            }
        )
        
        # EmbedReportRequest 객체 생성
        request = EmbedReportRequest(
            file_name=file_name,
            embed_id=embed_id
        )
        
        # 임베딩 처리 실행
        process_embed_report(request)
        
        print(f"\n{'='*60}")
        print(f"✅ Celery Task 완료: 보고서 임베딩")
        print(f"{'='*60}")
        print(f"Task ID: {self.request.id}")
        print(f"Embed ID: {embed_id}")
        print(f"{'='*60}\n")
        
        return {
            "success": True,
            "message": "임베딩 처리 완료",
            "embed_id": embed_id,
            "file_name": file_name,
            "task_id": self.request.id
        }
        
    except Exception as exc:
        print(f"\n{'='*60}")
        print(f"❌ Celery Task 예외 발생: 보고서 임베딩")
        print(f"{'='*60}")
        print(f"Task ID: {self.request.id}")
        print(f"Embed ID: {embed_id}")
        print(f"예외: {str(exc)}")
        print(f"Traceback:\n{traceback.format_exc()}")
        print(f"{'='*60}\n")
        
        # 재시도 로직
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {
                "success": False,
                "message": f"최대 재시도 횟수 초과: {str(exc)}",
                "embed_id": embed_id,
                "file_name": file_name,
                "task_id": self.request.id
            }
