"""消防栓管理接口：档案筛选、巡检队列、提醒升级、巡检回写与维修工单。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.hydrant import HydrantService

router = APIRouter(prefix="/api/hydrant", tags=["消防栓管理"])

service = HydrantService()

LIST_FIELDS = ["消防栓编号", "口径规格", "所在道路", "出水压力", "上次试水日", "下次试水到期日", "维护单位", "完好情况", "设施状态"]
STATUSES = ["完好", "待维修", "锈蚀", "无水", "已拆除"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按消防栓编号检索"),
    caliber: str | None = Query(default=None, description="按口径规格检索"),
    road: str | None = Query(default=None, description="按所在道路检索"),
    min_pressure: float | None = Query(default=None, description="最小出水压力，单位 MPa"),
    max_pressure: float | None = Query(default=None, description="最大出水压力，单位 MPa"),
    status: str | None = Query(default=None, description="完好、待维修、锈蚀、无水、已拆除"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按消防栓编号、口径规格、道路、压力与状态过滤消防栓档案。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(
        keyword=keyword,
        caliber=caliber,
        road=road,
        min_pressure=min_pressure,
        max_pressure=max_pressure,
        status=status,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/queue", response_model=dict)
def get_queue(
    keyword: str | None = Query(default=None, description="按消防栓编号检索"),
    caliber: str | None = Query(default=None, description="按口径规格检索"),
    road: str | None = Query(default=None, description="按所在道路检索"),
    min_pressure: float | None = Query(default=None, description="最小出水压力，单位 MPa"),
    max_pressure: float | None = Query(default=None, description="最大出水压力，单位 MPa"),
    status: str | None = Query(default=None, description="提醒状态"),
    priority: str | None = Query(default=None, description="常规、升级、紧急"),
    page: int = 1,
    size: int = 200,
) -> dict[str, Any]:
    """按档案条件读取消防栓巡检队列，紧急与升级提醒排在前面。"""
    items, total = service.list_queue(
        keyword=keyword,
        caliber=caliber,
        road=road,
        min_pressure=min_pressure,
        max_pressure=max_pressure,
        status=status,
        priority=priority,
        page=page,
        size=size,
    )
    return {"items": items, "total": total, "page": page, "size": size}


@router.post("/queue/generate", response_model=ActionResult)
@router.post("/queue", response_model=ActionResult)
def generate_queue(payload: EntryPayload) -> ActionResult:
    """按编号、口径、道路和压力生成巡检队列；风险会升级并抑制重复工单。"""
    filters = payload.values or {}
    result = service.generate_queue(
        keyword=_optional_str(filters.get("keyword") or filters.get("消防栓编号")),
        caliber=_optional_str(filters.get("caliber") or filters.get("口径规格")),
        road=_optional_str(filters.get("road") or filters.get("所在道路")),
        min_pressure=_optional_float(filters.get("min_pressure") or filters.get("最小压力")),
        max_pressure=_optional_float(filters.get("max_pressure") or filters.get("最大压力")),
        page=int(filters.get("page") or 1),
        size=int(filters.get("size") or 200),
    )
    return ActionResult(
        ok=True,
        message=(
            f"巡检队列已生成：新增 {result['generated']} 条，"
            f"升级 {result['escalated']} 条，抑制重复工单 {result['suppressed']} 张"
        ),
        entry=result,
    )


@router.get("/reminders", response_model=PageResult[dict])
def list_reminders(
    status: str | None = Query(default=None, description="待巡检、待派单、维修中、已完成、已取消"),
    priority: str | None = Query(default=None, description="常规、升级、紧急"),
    hydrant_id: int | None = Query(default=None, description="消防栓档案 id"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """读取提醒中心，字段与栓体档案、维修结果同步。"""
    items, total = service.list_reminders(
        status=status,
        priority=priority,
        hydrant_id=hydrant_id,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/inspections", response_model=PageResult[dict])
def list_inspections(
    hydrant_id: int | None = Query(default=None, description="消防栓档案 id"),
    status: str | None = None,
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """读取从消防栓巡检产生的巡检记录。"""
    items, total = service.list_inspections(hydrant_id=hydrant_id, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("/inspections", response_model=ActionResult)
def create_inspection(payload: EntryPayload) -> ActionResult:
    """从巡检记录回写维护建议，并同步提醒、工单与到期日。"""
    entry, message = service.create_inspection(payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/reports", response_model=PageResult[dict])
def list_reports(
    hydrant_id: int | None = Query(default=None, description="消防栓档案 id"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """读取消防栓报修记录及重复工单抑制结果。"""
    items, total = service.list_reports(hydrant_id=hydrant_id, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("/reports", response_model=ActionResult)
def register_report(payload: EntryPayload) -> ActionResult:
    """登记同一栓体报修；7 日内重复报修会升级，未完工单会被抑制。"""
    entry, message = service.register_report(payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/results", response_model=PageResult[dict])
def list_results(
    hydrant_id: int | None = Query(default=None, description="消防栓档案 id"),
    status: str | None = None,
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """读取消防栓维修工单和维护结果。"""
    items, total = service.list_results(hydrant_id=hydrant_id, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("/results/complete", response_model=ActionResult)
def complete_result(payload: EntryPayload) -> ActionResult:
    """回写维护结果，复检仍异常时重新升级提醒，正常时同步完成状态与下次到期日。"""
    entry, message = service.complete_result(payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出消防栓档案和提醒队列。"""
    items, total = service.list_entries(page=1, size=10000)
    reminders, reminder_total = service.list_reminders(page=1, size=10000)
    return {"module": "hydrant", "total": total, "items": items, "reminders": reminders, "reminder_total": reminder_total}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条消防栓明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"消防栓 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条消防栓；道路缺失会立即形成升级提醒。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="消防栓已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条消防栓执行试水检测、安排维修、登记拆除，并同步提醒与工单。"""
    action = str(payload.action or payload.values.get("action") or "").strip()
    values = {key: value for key, value in payload.values.items() if key != "action"}
    entry, message = service.run_action(entry_id, action, values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


def _optional_str(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
