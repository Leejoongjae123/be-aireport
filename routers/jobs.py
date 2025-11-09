"""
작업(Job) 상태 조회 API 라우터

Celery 태스크의 상태를 조회하는 기능을 제공합니다.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from celery.result import AsyncResult
from celery_config import celery_app
import redis
import json
import os


router = APIRouter(
    prefix="/api/jobs",
    tags=["Jobs"],
    responses={404: {"description": "Not found"}},
)


class JobStatusResponse(BaseModel):
    """작업 상태 응답 모델"""
    task_id: str
    status: str = Field(..., description="PENDING, STARTED, PROGRESS, SUCCESS, FAILURE, RETRY")
    result: Optional[Any] = None
    error: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class JobListResponse(BaseModel):
    """작업 목록 응답 모델"""
    active: list = Field(default_factory=list, description="실행 중인 작업 목록")
    scheduled: list = Field(default_factory=list, description="예약된 작업 목록")
    reserved: list = Field(default_factory=list, description="예약된 작업 목록")
    queued: list = Field(default_factory=list, description="큐에 대기 중인 작업 목록")


@router.get("/status/{task_id}", response_model=JobStatusResponse)
async def get_job_status(task_id: str):
    """
    특정 작업의 상태를 조회합니다.
    
    **작업 상태:**
    - **PENDING**: 작업이 대기 중
    - **STARTED**: 작업이 시작됨
    - **PROGRESS**: 작업이 진행 중
    - **SUCCESS**: 작업이 성공적으로 완료됨
    - **FAILURE**: 작업이 실패함
    - **RETRY**: 작업이 재시도 중
    
    **사용 예시:**
    ```
    GET /api/jobs/status/abc123-task-id
    ```
    
    Args:
        task_id: Celery 태스크 ID
        
    Returns:
        작업 상태 정보
    """
    try:
        # AsyncResult를 사용하여 작업 상태 조회
        task_result = AsyncResult(task_id, app=celery_app)
        
        response = JobStatusResponse(
            task_id=task_id,
            status=task_result.state,
            result=None,
            error=None,
            meta=None
        )
        
        if task_result.state == "PENDING":
            response.meta = {"status": "작업이 대기 중입니다."}
        elif task_result.state == "STARTED":
            response.meta = {"status": "작업이 시작되었습니다."}
        elif task_result.state == "PROGRESS":
            response.meta = task_result.info
        elif task_result.state == "SUCCESS":
            # 태스크 결과를 그대로 반환
            result_data = task_result.result
            response.result = result_data
            
            # 결과가 딕셔너리이고 success 키가 있으면 상세 정보 추가
            if isinstance(result_data, dict):
                response.meta = {
                    "status": "작업이 완료되었습니다.",
                    "success": result_data.get("success", True),
                    "message": result_data.get("message", ""),
                }
            else:
                response.meta = {"status": "작업이 완료되었습니다."}
        elif task_result.state == "FAILURE":
            response.error = str(task_result.info)
            response.meta = {"status": "작업이 실패했습니다."}
        elif task_result.state == "RETRY":
            response.meta = {"status": "작업이 재시도 중입니다."}
        else:
            response.meta = {"status": f"알 수 없는 상태: {task_result.state}"}
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"작업 상태 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/list", response_model=JobListResponse)
async def list_jobs():
    """
    현재 실행 중이거나 예약된 작업 목록을 조회합니다.
    
    **반환 정보:**
    - **active**: 현재 실행 중인 작업 목록
    - **scheduled**: 예약된 작업 목록
    - **reserved**: 예약된 작업 목록
    
    **사용 예시:**
    ```
    GET /api/jobs/list
    ```
    
    Returns:
        작업 목록
    """
    try:
        # Celery inspect를 사용하여 작업 목록 조회
        inspect = celery_app.control.inspect()
        
        active_tasks = inspect.active() or {}
        scheduled_tasks = inspect.scheduled() or {}
        reserved_tasks = inspect.reserved() or {}
        
        # 모든 워커의 작업을 하나의 리스트로 병합
        active_list = []
        for worker, tasks in active_tasks.items():
            for task in tasks:
                active_list.append({
                    "worker": worker,
                    "task_id": task.get("id"),
                    "name": task.get("name"),
                    "args": task.get("args"),
                    "kwargs": task.get("kwargs"),
                })
        
        scheduled_list = []
        for worker, tasks in scheduled_tasks.items():
            for task in tasks:
                scheduled_list.append({
                    "worker": worker,
                    "task_id": task.get("id"),
                    "name": task.get("name"),
                    "args": task.get("args"),
                    "kwargs": task.get("kwargs"),
                })
        
        reserved_list = []
        for worker, tasks in reserved_tasks.items():
            for task in tasks:
                reserved_list.append({
                    "worker": worker,
                    "task_id": task.get("id"),
                    "name": task.get("name"),
                    "args": task.get("args"),
                    "kwargs": task.get("kwargs"),
                })
        
        # Redis에서 대기 중인 작업 조회
        queued_list = []
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            redis_client = redis.from_url(redis_url)
            
            # 각 큐에서 대기 중인 작업 조회
            for queue_name in ["celery", "report_generation", "report_embedding"]:
                queue_length = redis_client.llen(queue_name)
                if queue_length > 0:
                    # 큐의 모든 작업 가져오기
                    tasks = redis_client.lrange(queue_name, 0, -1)
                    for task_data in tasks:
                        try:
                            task_json = json.loads(task_data)
                            headers = task_json.get("headers", {})
                            queued_list.append({
                                "queue": queue_name,
                                "task_id": headers.get("id"),
                                "name": headers.get("task"),
                                "args": headers.get("argsrepr"),
                                "kwargs": headers.get("kwargsrepr"),
                            })
                        except:
                            pass
        except Exception as e:
            print(f"Redis 큐 조회 중 오류: {e}")
        
        return JobListResponse(
            active=active_list,
            scheduled=scheduled_list,
            reserved=reserved_list,
            queued=queued_list
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"작업 목록 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.delete("/cancel/{task_id}")
async def cancel_job(task_id: str):
    """
    실행 중인 작업을 취소합니다.
    
    **주의:**
    - 이미 시작된 작업은 즉시 중단되지 않을 수 있습니다.
    - 작업이 완료된 후에는 취소할 수 없습니다.
    
    **사용 예시:**
    ```
    DELETE /api/jobs/cancel/abc123-task-id
    ```
    
    Args:
        task_id: Celery 태스크 ID
        
    Returns:
        취소 결과
    """
    try:
        # AsyncResult를 사용하여 작업 취소
        task_result = AsyncResult(task_id, app=celery_app)
        
        if task_result.state in ["SUCCESS", "FAILURE"]:
            return {
                "success": False,
                "message": f"작업이 이미 완료되었습니다 (상태: {task_result.state})",
                "task_id": task_id
            }
        
        # 작업 취소
        task_result.revoke(terminate=True, signal="SIGKILL")
        
        return {
            "success": True,
            "message": "작업 취소 요청이 전송되었습니다.",
            "task_id": task_id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"작업 취소 중 오류가 발생했습니다: {str(e)}"
        )
