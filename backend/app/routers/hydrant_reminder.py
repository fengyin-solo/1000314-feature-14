"""消防栓维护提醒接口：巡检队列、巡检记录回写、升级工单与维护结果同步。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.hydrant_reminder import REMINDER_STATUSES, HydrantReminderService

router = APIRouter(prefix="/api/hydrant-reminder", tags=["消防栓维护提醒"])

service = HydrantReminderService()


@router.get("/stats")
def reminder_stats() -> dict[str, int]:
    """提醒中心卡片统计：待处理、升级、待维护工单与被抑制的重复工单。"""
    return service.stats()


@router.get("/queue", response_model=PageResult[dict])
def get_queue(
    keyword: str | None = Query(default=None, description="按消防栓编号检索"),
    spec: str | None = Query(default=None, description="按口径规格检索"),
    road: str | None = Query(default=None, description="按所在道路检索"),
    pressure_min: float | None = Query(default=None, description="出水压力下限（MPa）"),
    pressure_max: float | None = Query(default=None, description="出水压力上限（MPa）"),
    level: str | None = Query(default=None, description="常规、升级"),
    status: str | None = Query(default=None, description="、".join(REMINDER_STATUSES)),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按消防栓编号、口径规格、所在道路、出水压力生成巡检队列。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_queue(
        keyword=keyword,
        spec=spec,
        road=road,
        pressure_min=pressure_min,
        pressure_max=pressure_max,
        level=level,
        status=status,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("/queue/generate", response_model=ActionResult)
def generate_queue(payload: EntryPayload) -> ActionResult:
    """按筛选条件重新生成巡检队列，并即时评估压力骤降、地址缺失、重复报修三类升级。"""
    values = payload.values
    items, total, messages = service.generate_queue(values)
    message = "；".join(messages) if messages else f"巡检队列已生成，共 {total} 只消防栓"
    return ActionResult(ok=True, message=message, entry={"total": total, "items": items[:50], "升级条数": len(messages)})


@router.get("/reports", response_model=PageResult[dict])
def list_reports(
    keyword: str | None = Query(default=None, description="按记录编号或消防栓编号检索"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """巡检记录列表：按记录编号、消防栓编号过滤。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_reports(keyword=keyword, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("/reports", response_model=ActionResult)
def create_report(payload: EntryPayload) -> ActionResult:
    """登记试水检测/报修巡检记录；命中升级规则时自动升级并抑制重复工单。"""
    report, message = service.create_report(payload.values)
    if report is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=report)


@router.post("/reports/{report_id}/write-back", response_model=ActionResult)
def write_back_advice(report_id: int, payload: EntryPayload) -> ActionResult:
    """从巡检记录回写维护建议，同步到提醒中心与未完工单。"""
    report, message = service.write_back_advice(report_id, payload.values)
    if report is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=report)


@router.get("/work-orders", response_model=PageResult[dict])
def list_work_orders(
    keyword: str | None = Query(default=None, description="按工单编号或消防栓编号检索"),
    status: str | None = Query(default=None, description="待派单、维护中、已完成、已取消"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """维护工单（维护结果）列表。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_work_orders(keyword=keyword, status_filter=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """提醒中心动作：开始巡检、生成工单、开始维护、完成维护、关闭提醒。

    三方（提醒中心 / 栓体档案 / 维护工单）到期日与状态随动作同步。
    """
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/export")
def export_queue() -> dict[str, Any]:
    """导出当前巡检队列与工单全量数据。"""
    queue_items, queue_total = service.list_queue(page=1, size=10000)
    work_items, work_total = service.list_work_orders(page=1, size=10000)
    report_items, report_total = service.list_reports(page=1, size=10000)
    return {
        "module": "hydrant_reminder",
        "queue_total": queue_total,
        "queue": queue_items,
        "work_order_total": work_total,
        "work_orders": work_items,
        "report_total": report_total,
        "reports": report_items,
    }
