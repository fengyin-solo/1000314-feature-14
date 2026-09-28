"""消防栓管理业务规则：巡检队列、风险升级、工单抑制与三方状态同步。"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.store import store

MODULE = "hydrant"
REMINDER_MODULE = "hydrant_reminder"
INSPECTION_MODULE = "hydrant_inspection"
REPORT_MODULE = "hydrant_repair_report"
RESULT_MODULE = "hydrant_maintenance_result"

REQUIRED_FIELDS = ["消防栓编号", "口径规格"]
STATUS_ORDER = ["完好", "待维修", "锈蚀", "无水", "已拆除"]
ACTION_RULES = {"试水检测": "完好", "安排维修": "待维修", "登记拆除": "已拆除"}

REMINDER_STATUSES = ["待巡检", "待派单", "维修中", "已完成", "已取消"]
RESULT_STATUSES = ["待派单", "维修中", "已完工", "已取消"]
PRIORITIES = ["常规", "升级", "紧急"]
REPEAT_REPORT_DAYS = 7
ROUTINE_DUE_DAYS = 15
MAINTAINED_DUE_DAYS = 30
PRESSURE_DROP_RATIO = 0.8
ACTIVE_RESULT_STATUSES = {"待派单", "维修中"}
ACTIVE_REMINDER_STATUSES = {"待巡检", "待派单", "维修中"}
REPAIR_KEYWORDS = ("维修", "抢修", "更换", "漏水", "无水", "锈蚀", "故障")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _parse_date(value: Any) -> date | None:
    text = _text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _parse_pressure(value: Any) -> float | None:
    text = _text(value).replace("MPa", "").replace("mpa", "").strip()
    if not text:
        return None
    try:
        pressure = float(text)
    except ValueError:
        return None
    return pressure if pressure >= 0 else None


def _next_id(rows: list[dict[str, Any]]) -> int:
    return max((int(row.get("id", 0)) for row in rows), default=0) + 1


def _code(prefix: str, value: int) -> str:
    return f"{prefix}-{value:04d}"


class HydrantService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        caliber: str | None = None,
        road: str | None = None,
        min_pressure: float | None = None,
        max_pressure: float | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("消防栓编号", ""))]
        if caliber:
            rows = [row for row in rows if caliber in str(row.get("口径规格", ""))]
        if road:
            rows = [row for row in rows if road in str(row.get("所在道路", ""))]
        if min_pressure is not None:
            rows = [
                row for row in rows
                if (pressure := _parse_pressure(row.get("出水压力"))) is not None and pressure >= min_pressure
            ]
        if max_pressure is not None:
            rows = [
                row for row in rows
                if (pressure := _parse_pressure(row.get("出水压力"))) is not None and pressure <= max_pressure
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not _text(values.get(field))]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        hydrant_no = _text(values.get("消防栓编号"))
        if any(_text(row.get("消防栓编号")) == hydrant_no for row in rows):
            return None, ["消防栓编号已存在"]

        today = date.today()
        pressure = _parse_pressure(values.get("出水压力"))
        entry: dict[str, Any] = {
            "id": _next_id(rows),
            "消防栓编号": hydrant_no,
            "口径规格": _text(values.get("口径规格")),
            "所在道路": _text(values.get("所在道路")),
            "出水压力": "" if pressure is None else pressure,
            "基线压力": _parse_pressure(values.get("基线压力")) if _text(values.get("基线压力")) else pressure,
            "上次试水日": today.isoformat(),
            "下次试水到期日": (today + timedelta(days=MAINTAINED_DUE_DAYS)).isoformat(),
            "维护单位": _text(values.get("维护单位")),
            "完好情况": _text(values.get("完好情况")) or "新建待检",
            "设施状态": STATUS_ORDER[0],
            "维护建议": "",
            "最近报修次数": 0,
            "status": STATUS_ORDER[0],
            "pending": True,
            "abnormal": False,
        }
        rows.append(entry)
        self._sync_from_hydrant(entry, today)
        self._raise_for_hydrant(entry, today)
        return entry, []

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        values = values or {}
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"消防栓 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于消防栓管理可执行范围"

        today = date.today()
        if action == "试水检测":
            pressure = _parse_pressure(values.get("出水压力"))
            if pressure is not None:
                entry["出水压力"] = pressure
                if entry.get("基线压力") in (None, ""):
                    entry["基线压力"] = pressure
            entry["上次试水日"] = _text(values.get("上次试水日")) or today.isoformat()
            test_date = _parse_date(entry.get("上次试水日")) or today
            entry["下次试水到期日"] = (test_date + timedelta(days=MAINTAINED_DUE_DAYS)).isoformat()
            self._sync_from_hydrant(entry, today)
            self._raise_for_hydrant(entry, today)
            return entry, "消防栓试水检测已登记，提醒到期日已同步"

        if action == "安排维修":
            entry["status"] = "待维修"
            entry["设施状态"] = "待维修"
            entry["pending"] = True
            entry["abnormal"] = True
            reminder = self._active_reminder(entry_id)
            if reminder is None:
                reminder = self._create_reminder(entry, ["人工安排维修"], today, "升级")
            result, suppressed = self._ensure_work_order(reminder, entry, today, "人工安排维修")
            result["工单状态"] = "维修中"
            result["status"] = "维修中"
            reminder["工单编号"] = result["工单编号"]
            reminder["status"] = "维修中"
            reminder["提醒状态"] = "维修中"
            message = "维修工单已安排" if not suppressed else "已有维修工单，已抑制重复派单"
            return entry, message

        entry["status"] = "已拆除"
        entry["设施状态"] = "已拆除"
        entry["pending"] = False
        entry["abnormal"] = False
        entry["下次试水到期日"] = ""
        for reminder in self._active_reminders(entry_id):
            reminder["status"] = "已取消"
            reminder["提醒状态"] = "已取消"
            reminder["到期日"] = ""
        for result in self._active_results(entry_id):
            result["status"] = "已取消"
            result["工单状态"] = "已取消"
        return entry, "消防栓已拆除，未完成提醒与工单已同步取消"

    def list_queue(
        self,
        *,
        keyword: str | None = None,
        caliber: str | None = None,
        road: str | None = None,
        min_pressure: float | None = None,
        max_pressure: float | None = None,
        status: str | None = None,
        priority: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        hydrants, _ = self.list_entries(
            keyword=keyword,
            caliber=caliber,
            road=road,
            min_pressure=min_pressure,
            max_pressure=max_pressure,
            page=1,
            size=10000,
        )
        hydrant_ids = {int(row["id"]) for row in hydrants}
        rows = [row for row in store.rows(REMINDER_MODULE) if int(row.get("hydrant_id", 0)) in hydrant_ids]
        if status:
            rows = [row for row in rows if row.get("提醒状态") == status or row.get("status") == status]
        if priority:
            rows = [row for row in rows if row.get("优先级") == priority]
        rows = sorted(rows, key=lambda row: (self._reminder_sort_key(row), _text(row.get("到期日"))))
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def list_reminders(
        self,
        *,
        status: str | None = None,
        priority: str | None = None,
        hydrant_id: int | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(REMINDER_MODULE)
        if status:
            rows = [row for row in rows if row.get("提醒状态") == status or row.get("status") == status]
        if priority:
            rows = [row for row in rows if row.get("优先级") == priority]
        if hydrant_id is not None:
            rows = [row for row in rows if int(row.get("hydrant_id", 0)) == hydrant_id]
        rows = sorted(rows, key=lambda row: (self._reminder_sort_key(row), _text(row.get("到期日"))))
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def generate_queue(
        self,
        *,
        keyword: str | None = None,
        caliber: str | None = None,
        road: str | None = None,
        min_pressure: float | None = None,
        max_pressure: float | None = None,
        page: int = 1,
        size: int = 200,
    ) -> dict[str, Any]:
        hydrants, _ = self.list_entries(
            keyword=keyword,
            caliber=caliber,
            road=road,
            min_pressure=min_pressure,
            max_pressure=max_pressure,
            page=1,
            size=10000,
        )
        today = date.today()
        generated = 0
        escalated = 0
        suppressed = 0

        for hydrant in hydrants:
            if hydrant.get("status") == "已拆除":
                continue
            reasons = self._risk_reasons(hydrant, today)
            priority = self._priority(reasons)
            reminder = self._active_reminder(int(hydrant["id"]))
            created = reminder is None
            if reminder is None:
                reminder = self._create_reminder(hydrant, reasons, today, priority)
                generated += 1
            else:
                old_priority = _text(reminder.get("优先级"))
                old_reasons = _text(reminder.get("升级原因"))
                self._update_reminder(reminder, hydrant, reasons, priority, today)
                if priority != "常规" and (
                    PRIORITIES.index(priority) > PRIORITIES.index(old_priority or "常规")
                    or old_reasons != reminder.get("升级原因")
                ):
                    escalated += 1

            active_result = self._active_result(int(hydrant["id"]))
            if priority == "常规":
                if not active_result:
                    reminder["status"] = "待巡检"
                    reminder["提醒状态"] = "待巡检"
                continue

            if active_result is not None:
                suppressed += 1
                active_status = str(active_result.get("工单状态") or active_result.get("status") or "维修中")
                reminder["工单编号"] = active_result["工单编号"]
                reminder["status"] = active_status
                reminder["提醒状态"] = active_status
            else:
                self._ensure_work_order(reminder, hydrant, today, "、".join(reasons))
                reminder["status"] = "待派单"
                reminder["提醒状态"] = "待派单"
            if created and active_result is not None:
                suppressed += 1
            self._sync_hydrant_flags(hydrant, True)

        queue_rows = [
            row for row in store.rows(REMINDER_MODULE)
            if int(row.get("hydrant_id", 0)) in {int(hydrant["id"]) for hydrant in hydrants}
        ]
        queue_rows = sorted(queue_rows, key=lambda row: (self._reminder_sort_key(row), _text(row.get("到期日"))))
        start = max(page - 1, 0) * size
        items, total = queue_rows[start:start + size], len(queue_rows)
        return {
            "items": items,
            "total": total,
            "page": page,
            "size": size,
            "generated": generated,
            "escalated": escalated,
            "suppressed": suppressed,
        }

    def list_inspections(
        self,
        *,
        hydrant_id: int | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(INSPECTION_MODULE)
        if hydrant_id is not None:
            rows = [row for row in rows if int(row.get("hydrant_id", 0)) == hydrant_id]
        if status:
            rows = [row for row in rows if row.get("巡检状态") == status or row.get("status") == status]
        rows = sorted(rows, key=lambda row: _text(row.get("巡检日期")), reverse=True)
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def create_inspection(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        hydrant_id = values.get("hydrant_id") or values.get("消防栓id")
        try:
            hydrant_id = int(hydrant_id)
        except (TypeError, ValueError):
            return None, "缺少有效的消防栓 id"
        hydrant = store.find(MODULE, hydrant_id)
        if hydrant is None:
            return None, f"消防栓 {hydrant_id} 不存在或已归档"

        today = date.today()
        inspection_date = _parse_date(values.get("巡检日期")) or today
        pressure = _parse_pressure(values.get("出水压力"))
        advice = _text(values.get("维护建议") or values.get("处置建议"))
        road = _text(values.get("所在道路")) or _text(hydrant.get("所在道路"))
        inspector = _text(values.get("巡检人员")) or "巡检班组"

        if pressure is not None:
            hydrant["出水压力"] = pressure
            if hydrant.get("基线压力") in (None, ""):
                hydrant["基线压力"] = pressure
        if road:
            hydrant["所在道路"] = road
        if advice:
            hydrant["维护建议"] = advice
        hydrant["上次试水日"] = inspection_date.isoformat()
        hydrant["下次试水到期日"] = (inspection_date + timedelta(days=MAINTAINED_DUE_DAYS)).isoformat()
        self._sync_from_hydrant(hydrant, today)

        reasons = self._risk_reasons(hydrant, today)
        needs_repair = bool(reasons) or any(keyword in advice for keyword in REPAIR_KEYWORDS)
        inspection_status = "已完成"
        rows = store.rows(INSPECTION_MODULE)
        inspection_id = _next_id(rows)
        entry = {
            "id": inspection_id,
            "巡检记录编号": _code("HYIN", inspection_id),
            "hydrant_id": hydrant_id,
            "消防栓编号": hydrant.get("消防栓编号"),
            "口径规格": hydrant.get("口径规格"),
            "所在道路": road,
            "出水压力": hydrant.get("出水压力", ""),
            "巡检日期": inspection_date.isoformat(),
            "巡检人员": inspector,
            "维护建议": advice,
            "巡检状态": inspection_status,
            "status": inspection_status,
            "pending": needs_repair,
            "abnormal": bool(reasons),
        }
        rows.append(entry)

        reminder: dict[str, Any] | None = None
        if needs_repair:
            all_reasons = reasons or ["巡检建议维修"]
            priority = self._priority(all_reasons)
            reminder = self._active_reminder(hydrant_id) or self._create_reminder(hydrant, all_reasons, today, priority)
            self._update_reminder(reminder, hydrant, all_reasons, priority, today)
            active_result = self._active_result(hydrant_id)
            if active_result is None:
                self._ensure_work_order(reminder, hydrant, today, "巡检回写维护建议")
                reminder["提醒状态"] = "待派单"
                reminder["status"] = "待派单"
            else:
                active_status = str(active_result.get("工单状态") or active_result.get("status") or "维修中")
                reminder["工单编号"] = active_result["工单编号"]
                reminder["提醒状态"] = active_status
                reminder["status"] = active_status
        else:
            active_result = self._active_result(hydrant_id)
            for existing in self._active_reminders(hydrant_id):
                if active_result is not None:
                    active_status = str(active_result.get("工单状态") or active_result.get("status") or "维修中")
                    existing["工单编号"] = active_result["工单编号"]
                    existing["提醒状态"] = active_status
                    existing["status"] = active_status
                elif existing.get("提醒状态") in {"待巡检", "待派单"}:
                    existing["提醒状态"] = "已完成"
                    existing["status"] = "已完成"
                    existing["pending"] = False
                    existing["abnormal"] = False
                    existing["到期日"] = hydrant.get("下次试水到期日", "")

        return entry, "巡检记录已回写，维护建议与提醒状态已同步"

    def list_reports(
        self,
        *,
        hydrant_id: int | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(REPORT_MODULE)
        if hydrant_id is not None:
            rows = [row for row in rows if int(row.get("hydrant_id", 0)) == hydrant_id]
        rows = sorted(rows, key=lambda row: _text(row.get("报修日期")), reverse=True)
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def register_report(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        hydrant_id = values.get("hydrant_id") or values.get("消防栓id")
        try:
            hydrant_id = int(hydrant_id)
        except (TypeError, ValueError):
            return None, "缺少有效的消防栓 id"
        hydrant = store.find(MODULE, hydrant_id)
        if hydrant is None:
            return None, f"消防栓 {hydrant_id} 不存在或已归档"
        if hydrant.get("status") == "已拆除":
            return None, "已拆除消防栓不再接受报修"

        today = date.today()
        report_date = _parse_date(values.get("报修日期")) or today
        rows = store.rows(REPORT_MODULE)
        report_id = _next_id(rows)
        reasons = self._risk_reasons(hydrant, today) + ["人工故障报修"]
        reminder = self._active_reminder(hydrant_id) or self._create_reminder(hydrant, reasons, today, "紧急")
        result = self._active_result(hydrant_id)
        suppressed = result is not None
        work_order = result["工单编号"] if result is not None else reminder.get("工单编号")

        entry = {
            "id": report_id,
            "报修编号": _code("HYRP", report_id),
            "hydrant_id": hydrant_id,
            "消防栓编号": hydrant.get("消防栓编号"),
            "所在道路": hydrant.get("所在道路", ""),
            "报修日期": report_date.isoformat(),
            "报修问题": _text(values.get("报修问题")) or "故障报修",
            "报修人": _text(values.get("报修人")) or "巡查人员",
            "工单编号": work_order or "",
            "关联工单id": int(result["id"]) if result is not None else 0,
            "是否抑制": suppressed,
            "status": "已受理" if not suppressed else "已并入工单",
        }
        rows.append(entry)

        self._update_reminder(reminder, hydrant, reasons, "紧急", today)
        if result is None:
            result, _ = self._ensure_work_order(reminder, hydrant, today, "故障报修")
        entry["工单编号"] = result["工单编号"]
        entry["关联工单id"] = int(result["id"])
        active_status = str(result.get("工单状态") or result.get("status") or "维修中")
        reminder["工单编号"] = result["工单编号"]
        reminder["提醒状态"] = active_status
        reminder["status"] = active_status

        report_count = len(self._recent_reports(hydrant_id, today))
        repeat_reasons = self._risk_reasons(hydrant, today) + ["人工故障报修"]
        self._update_reminder(reminder, hydrant, repeat_reasons, "紧急", today)
        reminder["工单编号"] = result["工单编号"]
        reminder["提醒状态"] = active_status
        reminder["status"] = active_status
        hydrant["最近报修次数"] = report_count
        hydrant["status"] = "待维修"
        hydrant["设施状态"] = "待维修"
        self._sync_hydrant_flags(hydrant, True)
        message = "报修已受理并生成维修工单" if not suppressed else "同一栓体已有未完工单，已抑制重复派单"
        return entry, message

    def list_results(
        self,
        *,
        hydrant_id: int | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(RESULT_MODULE)
        if hydrant_id is not None:
            rows = [row for row in rows if int(row.get("hydrant_id", 0)) == hydrant_id]
        if status:
            rows = [row for row in rows if row.get("工单状态") == status or row.get("status") == status]
        rows = sorted(rows, key=lambda row: _text(row.get("完成日期") or row.get("派单日期")), reverse=True)
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def complete_result(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        result_id = values.get("result_id") or values.get("工单id")
        hydrant_id = values.get("hydrant_id") or values.get("消防栓id")
        advice = _text(values.get("维护建议") or values.get("处置建议"))
        if not advice:
            return None, "请填写维护建议"
        result = None
        if result_id:
            try:
                result = store.find(RESULT_MODULE, int(result_id))
            except (TypeError, ValueError):
                result = None
        elif hydrant_id:
            try:
                result = self._active_result(int(hydrant_id))
            except (TypeError, ValueError):
                result = None
        if result is None:
            return None, "未找到可回写的维修工单"

        hydrant = store.find(MODULE, int(result.get("hydrant_id", 0)))
        if hydrant is None:
            return None, "工单关联的消防栓不存在"
        today = date.today()
        finish_date = _parse_date(values.get("完成日期")) or today
        pressure = _parse_pressure(values.get("出水压力"))
        road = _text(values.get("所在道路"))
        if pressure is not None:
            hydrant["出水压力"] = pressure
            if hydrant.get("基线压力") in (None, ""):
                hydrant["基线压力"] = pressure
            hydrant["上次试水日"] = finish_date.isoformat()
        if road:
            hydrant["所在道路"] = road
        hydrant["维护建议"] = advice
        hydrant["维护单位"] = _text(values.get("维护单位")) or hydrant.get("维护单位", "")
        hydrant["下次试水到期日"] = (finish_date + timedelta(days=MAINTAINED_DUE_DAYS)).isoformat()

        result.update({
            "完成日期": finish_date.isoformat(),
            "维护建议": advice,
            "维护单位": hydrant.get("维护单位", ""),
            "出水压力": hydrant.get("出水压力", ""),
            "工单状态": "已完工",
            "status": "已完工",
            "到期日": hydrant.get("下次试水到期日", ""),
            "pending": False,
            "abnormal": False,
        })
        remaining = self._risk_reasons(hydrant, today)
        active_reminders = self._active_reminders(int(hydrant["id"]))
        follow_up: dict[str, Any] | None = None
        for reminder in active_reminders:
            reminder["工单编号"] = result["工单编号"]
            if remaining:
                self._update_reminder(reminder, hydrant, remaining, self._priority(remaining), today)
                if follow_up is None:
                    follow_up, _ = self._ensure_work_order(reminder, hydrant, today, "复检未通过")
                reminder["工单编号"] = follow_up["工单编号"]
                reminder["提醒状态"] = "待派单"
                reminder["status"] = "待派单"
            else:
                reminder["提醒状态"] = "已完成"
                reminder["status"] = "已完成"
                reminder["pending"] = False
                reminder["abnormal"] = False
                reminder["到期日"] = hydrant.get("下次试水到期日", "")
        if remaining and not active_reminders:
            reminder = self._create_reminder(hydrant, remaining, today, self._priority(remaining))
            follow_up, _ = self._ensure_work_order(reminder, hydrant, today, "复检未通过")
            reminder["工单编号"] = follow_up["工单编号"]
            reminder["提醒状态"] = "待派单"
            reminder["status"] = "待派单"
            active_reminders = [reminder]
        self._sync_from_hydrant(hydrant, today)
        if remaining:
            return result, f"维护结果已回写，但风险仍在：{'、'.join(remaining)}"
        return result, "维护结果已回写，提醒中心与栓体档案已同步"

    def _risk_reasons(self, hydrant: dict[str, Any], today: date) -> list[str]:
        reasons: list[str] = []
        pressure = _parse_pressure(hydrant.get("出水压力"))
        baseline = _parse_pressure(hydrant.get("基线压力"))
        if pressure is not None and baseline:
            if pressure <= baseline * PRESSURE_DROP_RATIO or baseline - pressure >= 0.05:
                reasons.append("压力骤降")
        if not _text(hydrant.get("所在道路")):
            reasons.append("道路地址缺失")
        if len(self._recent_reports(int(hydrant.get("id", 0)), today)) >= 2:
            reasons.append("同一栓体短期内重复报修")
        due = _parse_date(hydrant.get("下次试水到期日"))
        last_test = _parse_date(hydrant.get("上次试水日"))
        if due is not None and due < today:
            reasons.append("到期未试水")
        elif last_test is not None and last_test + timedelta(days=MAINTAINED_DUE_DAYS) < today:
            reasons.append("到期未试水")
        return reasons

    def _priority(self, reasons: list[str]) -> str:
        urgent = {"压力骤降", "道路地址缺失", "同一栓体短期内重复报修"}
        if any(reason in urgent for reason in reasons):
            return "紧急"
        if reasons:
            return "升级"
        return "常规"

    def _recent_reports(self, hydrant_id: int, today: date) -> list[dict[str, Any]]:
        start = today - timedelta(days=REPEAT_REPORT_DAYS)
        reports = []
        latest_result_date = self._latest_result_date(hydrant_id)
        latest_result_id = self._latest_completed_result_id(hydrant_id)
        for row in store.rows(REPORT_MODULE):
            if int(row.get("hydrant_id", 0)) != hydrant_id:
                continue
            reported = _parse_date(row.get("报修日期"))
            if reported is None or not start <= reported <= today:
                continue
            linked_result_id = int(row.get("关联工单id") or 0)
            if linked_result_id:
                active_result = store.find(RESULT_MODULE, linked_result_id)
                if active_result is None or active_result.get("工单状态") not in ACTIVE_RESULT_STATUSES:
                    if linked_result_id <= latest_result_id:
                        continue
            elif latest_result_date is not None and reported <= latest_result_date:
                continue
            reports.append(row)
        return reports

    def _latest_result_date(self, hydrant_id: int) -> date | None:
        dates = [
            parsed for row in store.rows(RESULT_MODULE)
            if int(row.get("hydrant_id", 0)) == hydrant_id
            and row.get("工单状态") not in ACTIVE_RESULT_STATUSES
            and (parsed := _parse_date(row.get("完成日期"))) is not None
        ]
        return max(dates, default=None)

    def _latest_completed_result_id(self, hydrant_id: int) -> int:
        return max(
            (
                int(row.get("id", 0))
                for row in store.rows(RESULT_MODULE)
                if int(row.get("hydrant_id", 0)) == hydrant_id
                and row.get("工单状态") not in ACTIVE_RESULT_STATUSES
            ),
            default=0,
        )

    def _active_reminder(self, hydrant_id: int) -> dict[str, Any] | None:
        for row in store.rows(REMINDER_MODULE):
            if int(row.get("hydrant_id", 0)) == hydrant_id and row.get("提醒状态") in ACTIVE_REMINDER_STATUSES:
                return row
        return None

    def _active_reminders(self, hydrant_id: int) -> list[dict[str, Any]]:
        return [
            row for row in store.rows(REMINDER_MODULE)
            if int(row.get("hydrant_id", 0)) == hydrant_id and row.get("提醒状态") in ACTIVE_REMINDER_STATUSES
        ]

    def _latest_reminder(self, hydrant_id: int) -> dict[str, Any] | None:
        rows = [
            row for row in store.rows(REMINDER_MODULE)
            if int(row.get("hydrant_id", 0)) == hydrant_id
        ]
        return max(rows, key=lambda row: int(row.get("id", 0)), default=None)

    def _active_result(self, hydrant_id: int) -> dict[str, Any] | None:
        for row in store.rows(RESULT_MODULE):
            if int(row.get("hydrant_id", 0)) == hydrant_id and row.get("工单状态") in ACTIVE_RESULT_STATUSES:
                return row
        return None

    def _active_results(self, hydrant_id: int) -> list[dict[str, Any]]:
        return [
            row for row in store.rows(RESULT_MODULE)
            if int(row.get("hydrant_id", 0)) == hydrant_id and row.get("工单状态") in ACTIVE_RESULT_STATUSES
        ]

    def _reminder_sort_key(self, row: dict[str, Any]) -> int:
        priority = _text(row.get("优先级")) or "常规"
        return PRIORITIES.index(priority) if priority in PRIORITIES else len(PRIORITIES)

    def _due_date(self, priority: str, today: date, hydrant: dict[str, Any]) -> str:
        if priority == "紧急":
            return today.isoformat()
        if priority == "升级":
            return (today + timedelta(days=3)).isoformat()
        current = _parse_date(hydrant.get("下次试水到期日"))
        if current is not None and current > today:
            return current.isoformat()
        return (today + timedelta(days=ROUTINE_DUE_DAYS)).isoformat()

    def _create_reminder(
        self,
        hydrant: dict[str, Any],
        reasons: list[str],
        today: date,
        priority: str,
    ) -> dict[str, Any]:
        rows = store.rows(REMINDER_MODULE)
        reminder_id = _next_id(rows)
        status = "待派单" if priority == "紧急" else "待巡检"
        reminder = {
            "id": reminder_id,
            "提醒编号": _code("HYRM", reminder_id),
            "hydrant_id": hydrant["id"],
            "消防栓编号": hydrant.get("消防栓编号"),
            "口径规格": hydrant.get("口径规格"),
            "所在道路": hydrant.get("所在道路", ""),
            "出水压力": hydrant.get("出水压力", ""),
            "升级原因": "、".join(reasons) if reasons else "常规巡检",
            "优先级": priority,
            "到期日": self._due_date(priority, today, hydrant),
            "提醒状态": status,
            "工单编号": "",
            "报修次数": len(self._recent_reports(int(hydrant.get("id", 0)), today)),
            "status": status,
            "pending": True,
            "abnormal": priority != "常规",
        }
        rows.append(reminder)
        return reminder

    def _update_reminder(
        self,
        reminder: dict[str, Any],
        hydrant: dict[str, Any],
        reasons: list[str],
        priority: str,
        today: date,
    ) -> None:
        old_priority = _text(reminder.get("优先级")) or "常规"
        reminder.update({
            "消防栓编号": hydrant.get("消防栓编号"),
            "口径规格": hydrant.get("口径规格"),
            "所在道路": hydrant.get("所在道路", ""),
            "出水压力": hydrant.get("出水压力", ""),
            "升级原因": "、".join(reasons) if reasons else "常规巡检",
            "优先级": priority,
            "到期日": self._due_date(priority, today, hydrant),
            "报修次数": len(self._recent_reports(int(hydrant.get("id", 0)), today)),
            "abnormal": priority != "常规",
            "pending": True,
        })
        if PRIORITIES.index(priority) > PRIORITIES.index(old_priority):
            reminder["升级次数"] = int(reminder.get("升级次数", 0)) + 1
        current_status = _text(reminder.get("提醒状态"))
        if current_status not in {"维修中", "已完成", "已取消"}:
            reminder["提醒状态"] = "待派单" if priority == "紧急" else "待巡检"
            reminder["status"] = reminder["提醒状态"]

    def _ensure_work_order(
        self,
        reminder: dict[str, Any],
        hydrant: dict[str, Any],
        today: date,
        source: str,
    ) -> tuple[dict[str, Any], bool]:
        existing = self._active_result(int(hydrant["id"]))
        if existing is not None:
            reminder["工单编号"] = existing["工单编号"]
            return existing, True
        rows = store.rows(RESULT_MODULE)
        result_id = _next_id(rows)
        entry = {
            "id": result_id,
            "工单编号": _code("HYWO", result_id),
            "hydrant_id": hydrant["id"],
            "消防栓编号": hydrant.get("消防栓编号"),
            "口径规格": hydrant.get("口径规格"),
            "所在道路": hydrant.get("所在道路", ""),
            "派单日期": today.isoformat(),
            "完成日期": "",
            "到期日": self._due_date("紧急", today, hydrant),
            "问题来源": source,
            "维护建议": "",
            "维护单位": hydrant.get("维护单位", ""),
            "工单状态": "待派单",
            "status": "待派单",
            "pending": True,
            "abnormal": True,
        }
        rows.append(entry)
        reminder["工单编号"] = entry["工单编号"]
        hydrant["pending"] = True
        hydrant["abnormal"] = True
        return entry, False

    def _sync_from_hydrant(self, hydrant: dict[str, Any], today: date) -> None:
        reasons = self._risk_reasons(hydrant, today)
        priority = self._priority(reasons)
        has_active_work = self._active_result(int(hydrant.get("id", 0))) is not None
        if hydrant.get("status") == "已拆除":
            self._sync_hydrant_flags(hydrant, False)
            return
        if has_active_work:
            hydrant["status"] = "待维修"
            hydrant["设施状态"] = "待维修"
        elif reasons:
            hydrant["status"] = "无水" if "压力骤降" in reasons else "待维修"
            hydrant["设施状态"] = hydrant["status"]
        else:
            hydrant["status"] = "完好"
            hydrant["设施状态"] = "完好"
        self._sync_hydrant_flags(hydrant, bool(reasons) or has_active_work)

        for reminder in self._active_reminders(int(hydrant.get("id", 0))):
            self._update_reminder(reminder, hydrant, reasons, priority, today)
            active_result = self._active_result(int(hydrant["id"]))
            if active_result is not None:
                active_status = str(active_result.get("工单状态") or active_result.get("status") or "维修中")
                reminder["工单编号"] = active_result["工单编号"]
                reminder["提醒状态"] = active_status
                reminder["status"] = active_status
            elif not reasons and reminder.get("提醒状态") in {"待巡检", "待派单"}:
                reminder["提醒状态"] = "已完成"
                reminder["status"] = "已完成"
                reminder["到期日"] = hydrant.get("下次试水到期日", "")
                reminder["pending"] = False
                reminder["abnormal"] = False

    def _raise_for_hydrant(self, hydrant: dict[str, Any], today: date) -> None:
        """登记或试水后立即承接硬风险，避免必须再点一次“生成队列”。"""
        reasons = self._risk_reasons(hydrant, today)
        priority = self._priority(reasons)
        if priority == "常规":
            return
        reminder = self._active_reminder(int(hydrant["id"])) or self._latest_reminder(int(hydrant["id"]))
        if reminder is None:
            reminder = self._create_reminder(hydrant, reasons, today, priority)
        self._update_reminder(reminder, hydrant, reasons, priority, today)
        reminder["提醒状态"] = "待派单"
        reminder["status"] = "待派单"
        reminder["pending"] = True
        result, _ = self._ensure_work_order(reminder, hydrant, today, "、".join(reasons))
        reminder["工单编号"] = result["工单编号"]
        reminder["提醒状态"] = "待派单"
        reminder["status"] = "待派单"

    def _sync_hydrant_flags(self, hydrant: dict[str, Any], abnormal: bool) -> None:
        hydrant["abnormal"] = abnormal
        hydrant["pending"] = abnormal and hydrant.get("status") != "已拆除"
