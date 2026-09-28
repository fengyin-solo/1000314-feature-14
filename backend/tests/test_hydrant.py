import unittest
from datetime import date

from app.services.hydrant import HydrantService
from app.store import store


class HydrantMaintenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        store.reset()
        self.service = HydrantService()

    def test_queue_filters_and_escalates_pressure_drop(self) -> None:
        queue = self.service.generate_queue(caliber="DN150")
        self.assertEqual({row["消防栓编号"] for row in queue["items"]}, {"HYDR-0002"})
        self.assertEqual(queue["items"][0]["优先级"], "紧急")
        self.assertIn("道路地址缺失", queue["items"][0]["升级原因"])

        hydrant, missing = self.service.create_entry({
            "消防栓编号": "HYDR-TEST-1",
            "口径规格": "DN100",
            "所在道路": "测试路",
            "出水压力": "0.20",
        })
        self.assertEqual(missing, [])
        self.service.run_action(hydrant["id"], "试水检测", {"出水压力": "0.15"})
        reminders, _ = self.service.list_reminders(hydrant_id=hydrant["id"])
        self.assertEqual(reminders[0]["优先级"], "紧急")
        self.assertIn("压力骤降", reminders[0]["升级原因"])
        self.assertTrue(reminders[0]["工单编号"])

    def test_repeat_report_upgrades_and_suppresses_duplicate_work_order(self) -> None:
        hydrant, _ = self.service.create_entry({
            "消防栓编号": "HYDR-TEST-2",
            "口径规格": "DN100",
            "所在道路": "测试路",
            "出水压力": "0.20",
        })
        first, _ = self.service.register_report({
            "hydrant_id": hydrant["id"],
            "报修问题": "接口漏水",
        })
        second, _ = self.service.register_report({
            "hydrant_id": hydrant["id"],
            "报修问题": "仍然漏水",
        })
        self.assertFalse(first["是否抑制"])
        self.assertTrue(second["是否抑制"])
        self.assertEqual(first["工单编号"], second["工单编号"])
        reminders, _ = self.service.list_reminders(hydrant_id=hydrant["id"])
        active = [row for row in reminders if row["提醒状态"] in {"待派单", "维修中"}]
        self.assertIn("同一栓体短期内重复报修", active[0]["升级原因"])
        results, total = self.service.list_results(hydrant_id=hydrant["id"])
        self.assertEqual(total, 1)
        self.assertEqual(results[0]["工单编号"], second["工单编号"])

    def test_inspection_and_completion_sync_status_and_due_date(self) -> None:
        inspection, _ = self.service.create_inspection({
            "hydrant_id": 2,
            "所在道路": "滨河路 88 号",
            "出水压力": "0.21",
            "维护建议": "地址已补录，现场正常",
        })
        self.assertEqual(inspection["巡检状态"], "已完成")
        hydrant = self.service.get_entry(2)
        self.assertEqual(hydrant["所在道路"], "滨河路 88 号")

        result, _ = self.service.complete_result({
            "result_id": 2,
            "维护建议": "补录地址并完成检修",
            "出水压力": "0.21",
            "所在道路": "滨河路 88 号",
        })
        self.assertEqual(result["工单状态"], "已完工")
        hydrant = self.service.get_entry(2)
        reminders, _ = self.service.list_reminders(hydrant_id=2)
        self.assertEqual(reminders[-1]["提醒状态"], "已完成")
        self.assertEqual(reminders[-1]["到期日"], hydrant["下次试水到期日"])
        self.assertEqual(result["到期日"], hydrant["下次试水到期日"])
        self.assertEqual((date.fromisoformat(result["完成日期"]) - date.today()).days, 0)


if __name__ == "__main__":
    unittest.main()
