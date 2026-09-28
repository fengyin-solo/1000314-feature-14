"""消防栓维护提醒业务规则：巡检队列生成、升级判定、工单抑制与三方状态同步都收在这里。

模块边界：
- ``hydrant``（栓体档案）：消防栓编号、口径规格、所在道路、出水压力等基础台账。
- ``hydrant_reminder``（提醒中心）：每只有待处理风险的栓体对应一条提醒，记录级别、到期日、工单状态。
- ``hydrant_report``（巡检记录）：巡检员提交的试水/报修记录，可回写维护建议。
- ``hydrant_work_order``（维护工单/维护结果）：提醒升级后生成，记录处置结果；重复升级只抑制不重复开单。

提醒中心（reminder）、栓体档案（hydrant）与维护结果（work_order）通过 :meth:`_sync_due_status`
保持到期日与状态一致。
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from app.store import store

REMINDER_MODULE = "hydrant_reminder"
REPORT_MODULE = "hydrant_report"
WORK_ORDER_MODULE = "hydrant_work_order"
HYDRANT_MODULE = "hydrant"

# 提醒级别与状态
LEVEL_NORMAL = "常规"
LEVEL_ESCALATED = "升级"
REMINDER_STATUSES = ["待巡检", "巡检中", "待维护", "维护中", "已维护", "已关闭"]
OPEN_REMINDER_STATUSES = ["待巡检", "巡检中", "待维护", "维护中"]

# 工单状态（维护结果）
OPEN_WORK_ORDER_STATUSES = ["待派单", "维护中"]

# 巡检记录状态
REPORT_STATUSES = ["待处置", "已回写建议", "已维护"]

# 到期口径：常规巡检 7 天，升级提醒 2 天
DUE_DAYS_NORMAL = 7
DUE_DAYS_ESCALATED = 2
# 压力骤降阈值：较台账出水压力下降 20% 及以上
PRESSURE_DROP_RATIO = 0.20
# 同一栓体短期重复报修窗口：30 天内 2 次及以上报修即升级
REPEAT_REPORT_DAYS = 30
REPEAT_REPORT_LIMIT = 2

# 提醒中心可执行动作
REMINDER_ACTIONS = ["开始巡检", "生成工单", "开始维护", "完成维护", "关闭提醒"]

_PRESSURE_RE = re.compile(r"\d+\.\d+")


def _today() -> date:
    return date.today()


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _parse_pressure(value: Any) -> float | None:
    """从「0.35MPa」这类字段里提取数值；台账里是占位文案时返回 None，不参与压力比较。"""
    if value is None:
        return None
    match = _PRESSURE_RE.search(str(value))
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


class HydrantReminderService:
    # ------------------------------------------------------------------ 列表查询
    def list_queue(
        self,
        *,
        keyword: str | None = None,
        spec: str | None = None,
        road: str | None = None,
        pressure_min: float | None = None,
        pressure_max: float | None = None,
        level: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """巡检队列：在重新评估风险的提醒集合上，按编号/口径/道路/出水压力过滤。"""
        rows = self._collect_reminders()
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("消防栓编号", ""))]
        if spec:
            rows = [row for row in rows if spec in str(row.get("口径规格", ""))]
        if road:
            rows = [row for row in rows if road in str(row.get("所在道路", ""))]
        if pressure_min is not None or pressure_max is not None:
            filtered: list[dict[str, Any]] = []
            for row in rows:
                pressure = _parse_pressure(row.get("出水压力"))
                if pressure is None:
                    continue  # 台账压力无法解析时，不进入按出水压力筛选的队列
                if pressure_min is not None and pressure < pressure_min:
                    continue
                if pressure_max is not None and pressure > pressure_max:
                    continue
                filtered.append(row)
            rows = filtered
        if level:
            rows = [row for row in rows if row.get("级别") == level]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        # 升级、临期优先，便于巡检排班
        rows.sort(
            key=lambda row: (
                row.get("级别") != LEVEL_ESCALATED,
                str(row.get("到期日") or "9999-12-31"),
                int(row.get("hydrant_id", 0)),
            )
        )
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def list_reports(
        self,
        *,
        keyword: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(REPORT_MODULE)
        if keyword:
            rows = [
                row
                for row in rows
                if keyword in str(row.get("记录编号", ""))
                or keyword in str(row.get("消防栓编号", ""))
            ]
        rows = sorted(rows, key=lambda row: -int(row.get("id", 0)))
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def list_work_orders(
        self,
        *,
        keyword: str | None = None,
        status_filter: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(WORK_ORDER_MODULE)
        if keyword:
            rows = [
                row
                for row in rows
                if keyword in str(row.get("工单编号", ""))
                or keyword in str(row.get("消防栓编号", ""))
            ]
        if status_filter:
            rows = [row for row in rows if row.get("status") == status_filter]
        rows = sorted(rows, key=lambda row: -int(row.get("id", 0)))
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def stats(self) -> dict[str, int]:
        """提醒中心卡片：总量、升级量、待维护工单数、今日被抑制的重复报修。"""
        reminders = self._collect_reminders()
        work_orders = store.rows(WORK_ORDER_MODULE)
        today = _today().isoformat()
        return {
            "待处理提醒": sum(1 for row in reminders if row.get("status") in OPEN_REMINDER_STATUSES),
            "升级提醒": sum(1 for row in reminders if row.get("级别") == LEVEL_ESCALATED),
            "待维护工单": sum(1 for row in work_orders if row.get("status") in OPEN_WORK_ORDER_STATUSES),
            "今日抑制重复工单": sum(
                1
                for row in work_orders
                if row.get("最后抑制日") == today and int(row.get("抑制次数", 0)) > 0
            ),
        }

    # ------------------------------------------------------------------ 队列生成
    def generate_queue(self, filters: dict[str, Any]) -> tuple[list[dict[str, Any]], int, list[str]]:
        """按编号/口径/道路/出水压力生成巡检队列，并对队列内栓体重新评估升级条件。

        返回 (队列条目, 总数, 本次评估说明)，说明里列出新触发的升级，方便前端提示。
        """
        def _float(name: str) -> float | None:
            raw = filters.get(name)
            if raw in (None, ""):
                return None
            try:
                return float(raw)
            except (TypeError, ValueError):
                return None

        before = {
            int(row.get("hydrant_id")): list(row.get("升级原因", []))
            for row in store.rows(REMINDER_MODULE)
        }
        items, total = self.list_queue(
            keyword=_text(filters.get("keyword")),
            spec=_text(filters.get("spec")),
            road=_text(filters.get("road")),
            pressure_min=_float("pressure_min"),
            pressure_max=_float("pressure_max"),
            page=int(filters.get("page") or 1),
            size=int(filters.get("size") or 200),
        )
        messages: list[str] = []
        for row in items:
            hydrant_id = int(row.get("hydrant_id", 0))
            new_reasons = [
                reason
                for reason in row.get("升级原因", [])
                if reason not in before.get(hydrant_id, [])
            ]
            for reason in new_reasons:
                messages.append(f"{row.get('消防栓编号')} 触发升级：{reason}")
        return items, total, messages

    # ------------------------------------------------------------------ 巡检记录
    def create_report(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """登记一条巡检记录（试水检测/报修），随后立即按三类规则重新评估升级。

        压力骤降或短期重复报修都会升级；已有未完工单时只累加抑制计数，不重复开单。
        """
        hydrant_number = str(values.get("消防栓编号") or "").strip()
        if not hydrant_number:
            return None, "缺少必填字段：消防栓编号"
        hydrant = self._find_hydrant_by_number(hydrant_number)
        if hydrant is None:
            return None, f"消防栓编号 {hydrant_number} 不在栓体档案中，无法登记巡检记录"

        report_date = str(values.get("巡检日期") or _today().isoformat()).strip()
        is_repair = bool(values.get("是否报修")) or str(values.get("是否报修", "")).strip() in ("true", "True", "1", "是")
        rows = store.rows(REPORT_MODULE)
        report = {
            "id": self._next_id(rows),
            "status": REPORT_STATUSES[0],
            "pending": True,
            "abnormal": False,
            "记录编号": self._next_code(rows, "HREP"),
            "hydrant_id": int(hydrant["id"]),
            "消防栓编号": hydrant_number,
            "巡检日期": report_date,
            "巡检人员": str(values.get("巡检人员") or "").strip(),
            "实测压力": str(values.get("实测压力") or "").strip(),
            "是否报修": "是" if is_repair else "否",
            "问题描述": str(values.get("问题描述") or "").strip(),
            "维护建议": str(values.get("维护建议") or "").strip(),
        }
        rows.append(report)

        reminder, new_reasons, suppressed = self._evaluate_hydrant(hydrant)
        # 升级处置中的栓体再次报修、且本次评估没有触发新的升级：只记一次重复工单抑制。
        if (
            is_repair
            and not suppressed
            and not new_reasons
            and reminder.get("级别") == LEVEL_ESCALATED
            and self._open_work_order(reminder) is not None
        ):
            work_order = self._open_work_order(reminder)
            assert work_order is not None
            work_order["抑制次数"] = int(work_order.get("抑制次数", 0)) + 1
            work_order["最后抑制日"] = _today().isoformat()
            self._sync_due_status(reminder)
        return report, self._report_message(reminder, [])

    def write_back_advice(self, report_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """从巡检记录回写维护建议：更新巡检记录，并同步到提醒中心与未完工单。"""
        report = store.find(REPORT_MODULE, report_id)
        if report is None:
            return None, f"巡检记录 {report_id} 不存在或已归档"
        advice = str(values.get("维护建议") or "").strip()
        if not advice:
            return None, "维护建议为空，无法回写"
        report["维护建议"] = advice
        if report.get("status") == REPORT_STATUSES[0]:
            report["status"] = REPORT_STATUSES[1]
        hydrant = store.find(HYDRANT_MODULE, int(report.get("hydrant_id", 0)))
        reminder = self._ensure_reminder(hydrant) if hydrant else None
        if reminder is not None:
            reminder["维护建议"] = advice
            if reminder.get("status") == "待巡检":
                reminder["status"] = "待维护"
                reminder["pending"] = True
            work_order = self._open_work_order(reminder)
            if work_order is not None:
                work_order["维护建议"] = advice
                self._sync_due_status(reminder)
        return report, f"巡检记录 {report['记录编号']} 的维护建议已回写至提醒中心"

    # ------------------------------------------------------------------ 提醒动作
    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        reminder = store.find(REMINDER_MODULE, entry_id)
        if reminder is None:
            return None, f"提醒 {entry_id} 不存在或已关闭归档"
        if action not in REMINDER_ACTIONS:
            return None, f"动作「{action}」不属于提醒中心可执行范围"

        current = str(reminder.get("status"))
        if action == "开始巡检":
            if current not in ("待巡检",):
                return None, f"提醒当前为「{current}」，不能重复开始巡检"
            reminder["status"] = "巡检中"
        elif action == "生成工单":
            work_order, created = self._ensure_work_order(reminder)
            if created:
                reminder["status"] = "待维护"
            self._sync_due_status(reminder)
            return reminder, (
                f"已为 {reminder.get('消防栓编号')} 生成维护工单 {work_order['工单编号']}"
                if created
                else f"{reminder.get('消防栓编号')} 已有未完工单 {work_order['工单编号']}，已抑制重复工单"
            )
        elif action == "开始维护":
            if current not in ("待维护", "巡检中", "待巡检"):
                return None, f"提醒当前为「{current}」，暂不能开始维护"
            work_order, _ = self._ensure_work_order(reminder)
            work_order["status"] = "维护中"
            reminder["status"] = "维护中"
        elif action == "完成维护":
            if current not in ("待维护", "维护中", "巡检中"):
                return None, f"提醒当前为「{current}」，没有待完成的维护"
            return self._complete_maintenance(reminder)
        else:  # 关闭提醒
            if current not in OPEN_REMINDER_STATUSES:
                return None, f"提醒当前为「{current}」，无需关闭"
            reminder["status"] = "已关闭"
            for work_order in self._work_orders_for(reminder):
                if work_order.get("status") in OPEN_WORK_ORDER_STATUSES:
                    work_order["status"] = "已取消"
            hydrant = store.find(HYDRANT_MODULE, int(reminder.get("hydrant_id", 0)))
            if hydrant is not None:
                hydrant["pending"] = False
                hydrant["abnormal"] = reminder.get("级别") == LEVEL_ESCALATED
            reminder["pending"] = False
            return reminder, f"提醒 {reminder.get('提醒编号')} 已关闭，未完工单一并取消"

        self._sync_due_status(reminder)
        return reminder, f"提醒已{action}"

    # ------------------------------------------------------------------ 风险评估
    def _evaluate_hydrant(self, hydrant: dict[str, Any]) -> tuple[dict[str, Any], list[str], bool]:
        """评估单只栓体：道路缺失、压力骤降、短期重复报修，命中任一即升级。

        返回 (提醒, 本次新增的升级原因, 是否抑制了重复工单)。
        """
        reminder = self._ensure_reminder(hydrant)
        new_reasons: list[str] = []
        reasons: list[str] = list(reminder.get("升级原因", []))

        def _add_reason(reason: str) -> None:
            if reason not in reasons:
                reasons.append(reason)
                new_reasons.append(reason)

        if not str(hydrant.get("所在道路") or "").strip():
            _add_reason("所在道路/地址缺失")

        baseline = _parse_pressure(hydrant.get("出水压力"))
        latest = self._latest_report_pressure(reminder)
        if baseline is not None and latest is not None and baseline > 0:
            if (baseline - latest) / baseline >= PRESSURE_DROP_RATIO:
                _add_reason(f"出水压力骤降（台账 {baseline:g} → 实测 {latest:g}）")

        if self._recent_repair_count(reminder) >= REPEAT_REPORT_LIMIT:
            _add_reason(f"{REPEAT_REPORT_DAYS} 天内重复报修")

        suppressed = False
        if new_reasons:
            reminder["升级原因"] = reasons
            suppressed = self._escalate(reminder, reasons)
        return reminder, new_reasons, suppressed

    def _escalate(self, reminder: dict[str, Any], reasons: list[str]) -> bool:
        """升级提醒：缩短到期日、回写栓体状态。

        无未完工单时开单并返回 False；已有未完工单时不开新单、累加抑制计数并返回 True。
        """
        reminder["级别"] = LEVEL_ESCALATED
        reminder["升级原因"] = reasons
        reminder["触发时间"] = _today().isoformat()
        reminder["到期日"] = (_today() + timedelta(days=DUE_DAYS_ESCALATED)).isoformat()
        reminder["abnormal"] = True
        reminder["pending"] = True
        hydrant = store.find(HYDRANT_MODULE, int(reminder.get("hydrant_id", 0)))
        if hydrant is not None and hydrant.get("status") != "已拆除":
            hydrant["status"] = "待维修"
            hydrant["pending"] = True
            hydrant["abnormal"] = True

        work_order = self._open_work_order(reminder)
        if work_order is None:
            self._open_work_order_row(reminder, reasons)
            self._sync_due_status(reminder)
            return False
        work_order["抑制次数"] = int(work_order.get("抑制次数", 0)) + 1
        work_order["最后抑制日"] = _today().isoformat()
        self._sync_due_status(reminder)
        return True

    # ------------------------------------------------------------------ 内部工具
    def _collect_reminders(self) -> list[dict[str, Any]]:
        """确保每只在册栓体都有提醒，并重新评估全部风险后返回提醒快照。"""
        for hydrant in store.rows(HYDRANT_MODULE):
            self._evaluate_hydrant(hydrant)
        return list(store.rows(REMINDER_MODULE))
    def _ensure_reminder(self, hydrant: dict[str, Any]) -> dict[str, Any]:
        rows = store.rows(REMINDER_MODULE)
        for row in rows:
            if int(row.get("hydrant_id", 0)) == int(hydrant["id"]):
                return row
        reminder = {
            "id": self._next_id(rows),
            "status": "待巡检",
            "pending": True,
            "abnormal": False,
            "提醒编号": self._next_code(rows, "HREM"),
            "hydrant_id": int(hydrant["id"]),
            "消防栓编号": hydrant.get("消防栓编号"),
            "口径规格": hydrant.get("口径规格"),
            "所在道路": hydrant.get("所在道路"),
            "出水压力": hydrant.get("出水压力"),
            "级别": LEVEL_NORMAL,
            "升级原因": [],
            "到期日": (_today() + timedelta(days=DUE_DAYS_NORMAL)).isoformat(),
            "触发时间": "",
            "维护建议": "",
            "工单状态": "",
            "抑制次数": 0,
        }
        rows.append(reminder)
        return reminder

    def _latest_report_pressure(self, reminder: dict[str, Any]) -> float | None:
        pressures: list[tuple[str, float]] = []
        for report in self._reports_for(reminder):
            pressure = _parse_pressure(report.get("实测压力"))
            if pressure is not None:
                pressures.append((str(report.get("巡检日期") or ""), pressure))
        if not pressures:
            return None
        pressures.sort(key=lambda item: item[0])
        return pressures[-1][1]

    def _recent_repair_count(self, reminder: dict[str, Any]) -> int:
        cutoff = _today() - timedelta(days=REPEAT_REPORT_DAYS)
        count = 0
        for report in self._reports_for(reminder):
            if str(report.get("是否报修")) != "是":
                continue
            report_date = _parse_date(report.get("巡检日期"))
            if report_date is None or report_date >= cutoff:
                count += 1
        return count

    def _reports_for(self, reminder: dict[str, Any]) -> list[dict[str, Any]]:
        hydrant_id = int(reminder.get("hydrant_id", 0))
        return [
            row
            for row in store.rows(REPORT_MODULE)
            if int(row.get("hydrant_id", 0)) == hydrant_id
        ]

    def _work_orders_for(self, reminder: dict[str, Any]) -> list[dict[str, Any]]:
        hydrant_id = int(reminder.get("hydrant_id", 0))
        return [
            row
            for row in store.rows(WORK_ORDER_MODULE)
            if int(row.get("hydrant_id", 0)) == hydrant_id
        ]

    def _open_work_order(self, reminder: dict[str, Any]) -> dict[str, Any] | None:
        for work_order in self._work_orders_for(reminder):
            if work_order.get("status") in OPEN_WORK_ORDER_STATUSES:
                return work_order
        return None

    def _ensure_work_order(self, reminder: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        work_order = self._open_work_order(reminder)
        if work_order is not None:
            work_order["抑制次数"] = int(work_order.get("抑制次数", 0)) + 1
            work_order["最后抑制日"] = _today().isoformat()
            return work_order, False
        return self._open_work_order_row(reminder, reminder.get("升级原因", [])), True

    def _open_work_order_row(self, reminder: dict[str, Any], reasons: list[Any]) -> dict[str, Any]:
        rows = store.rows(WORK_ORDER_MODULE)
        work_order = {
            "id": self._next_id(rows),
            "status": "待派单",
            "pending": True,
            "abnormal": reminder.get("级别") == LEVEL_ESCALATED,
            "工单编号": self._next_code(rows, "HWO"),
            "hydrant_id": int(reminder.get("hydrant_id", 0)),
            "消防栓编号": reminder.get("消防栓编号"),
            "口径规格": reminder.get("口径规格"),
            "所在道路": reminder.get("所在道路"),
            "级别": reminder.get("级别", LEVEL_NORMAL),
            "升级原因": "；".join(str(reason) for reason in reasons),
            "维护建议": reminder.get("维护建议", ""),
            "开工日期": "",
            "完工日期": "",
            "到期日": reminder.get("到期日"),
            "抑制次数": 0,
            "最后抑制日": "",
        }
        rows.append(work_order)
        self._sync_due_status(reminder)
        return work_order

    def _complete_maintenance(self, reminder: dict[str, Any]) -> tuple[dict[str, Any], str]:
        """维护结果回写：工单完工、提醒置为已维护、栓体恢复完好，三方状态/到期日同步。"""
        today = _today().isoformat()
        work_order = self._open_work_order(reminder)
        if work_order is None:
            work_order, _ = self._ensure_work_order(reminder)
        work_order["status"] = "已完成"
        work_order["pending"] = False
        work_order["abnormal"] = False
        work_order["完工日期"] = today
        work_order["到期日"] = today
        if not work_order.get("开工日期"):
            work_order["开工日期"] = today

        reminder["status"] = "已维护"
        reminder["pending"] = False
        reminder["abnormal"] = False
        reminder["到期日"] = today

        hydrant = store.find(HYDRANT_MODULE, int(reminder.get("hydrant_id", 0)))
        if hydrant is not None and hydrant.get("status") != "已拆除":
            hydrant["status"] = "完好"
            hydrant["pending"] = False
            hydrant["abnormal"] = False
        for report in self._reports_for(reminder):
            if report.get("status") != REPORT_STATUSES[2]:
                report["status"] = REPORT_STATUSES[2]
                report["pending"] = False
        self._sync_due_status(reminder)
        return reminder, f"维护结果已登记，工单 {work_order['工单编号']} 完工，栓体档案已同步"

    def _sync_due_status(self, reminder: dict[str, Any]) -> None:
        """提醒中心 → 栓体档案 / 维护结果：到期日与状态保持一致。"""
        hydrant = store.find(HYDRANT_MODULE, int(reminder.get("hydrant_id", 0)))
        if hydrant is not None:
            hydrant["到期日"] = reminder.get("到期日")
            hydrant["提醒级别"] = reminder.get("级别")
            hydrant["提醒状态"] = reminder.get("status")
            hydrant["维护建议"] = reminder.get("维护建议", "")
            hydrant["pending"] = bool(reminder.get("pending"))
            hydrant["abnormal"] = bool(reminder.get("abnormal"))
        work_order = self._open_work_order(reminder)
        if work_order is not None:
            # 同一套到期口径；维护中工单跟随提醒状态。已完工单保留完工日，不回写。
            work_order["级别"] = reminder.get("级别")
            if reminder.get("status") != "已维护":
                work_order["到期日"] = reminder.get("到期日")
            reminder["工单状态"] = work_order.get("status")
            reminder["抑制次数"] = work_order.get("抑制次数", 0)
        else:
            finished = [
                row
                for row in self._work_orders_for(reminder)
                if row.get("status") == "已完成"
            ]
            reminder["工单状态"] = finished[-1]["status"] if finished else ""

    def _find_hydrant_by_number(self, number: str) -> dict[str, Any] | None:
        for row in store.rows(HYDRANT_MODULE):
            if str(row.get("消防栓编号", "")).strip() == number:
                return row
        return None

    @staticmethod
    def _next_id(rows: list[dict[str, Any]]) -> int:
        return max((int(row.get("id", 0)) for row in rows), default=0) + 1

    @staticmethod
    def _next_code(rows: list[dict[str, Any]], prefix: str) -> str:
        return f"{prefix}-{max((int(row.get('id', 0)) for row in rows), default=0) + 1:04d}"

    @staticmethod
    def _report_message(reminder: dict[str, Any], reasons: list[str]) -> str:
        if reasons:
            return f"巡检记录已登记，提醒已升级（{'；'.join(reasons)}），重复工单已抑制"
        if reminder.get("级别") == LEVEL_ESCALATED:
            return "巡检记录已登记，该栓体已在升级处置中，未重复生成工单"
        return "巡检记录已登记，已纳入巡检队列"


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
