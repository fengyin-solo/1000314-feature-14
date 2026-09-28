"""接口出入参模型：列表分页、动作结果与各模块的明细结构。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    size: int = 20


class ActionResult(BaseModel):
    ok: bool
    message: str
    entry: dict[str, Any] | None = None


class EntryPayload(BaseModel):
    """登记或修改一条业务记录时提交的字段集合。"""

    values: dict[str, Any] = Field(default_factory=dict)
    action: str | None = None
    remark: str | None = None



class PipeSectionEntry(BaseModel):
    """管段明细结构。"""

    field_0: str | None = None  # 管段编号
    field_1: str | None = None  # 管线类型
    field_2: str | None = None  # 材质规格
    field_3: str | None = None  # 埋设深度
    field_4: str | None = None  # 建设年代
    field_5: str | None = None  # 产权单位
    field_6: str | None = None  # 所在道路
    field_7: str | None = None  # 管段状态

class InspectEntry(BaseModel):
    """巡查记录单明细结构。"""

    field_0: str | None = None  # 巡查编号
    field_1: str | None = None  # 巡查路段
    field_2: str | None = None  # 巡查人员
    field_3: str | None = None  # 巡查日期
    field_4: str | None = None  # 管线类型
    field_5: str | None = None  # 发现隐患
    field_6: str | None = None  # 处置建议
    field_7: str | None = None  # 巡查状态

class DefectEntry(BaseModel):
    """病害记录明细结构。"""

    field_0: str | None = None  # 病害编号
    field_1: str | None = None  # 关联管段
    field_2: str | None = None  # 病害类型
    field_3: str | None = None  # 发现方式
    field_4: str | None = None  # 严重程度
    field_5: str | None = None  # 定位坐标
    field_6: str | None = None  # 现场照片
    field_7: str | None = None  # 病害状态

class CctvEntry(BaseModel):
    """检测报告明细结构。"""

    field_0: str | None = None  # 报告编号
    field_1: str | None = None  # 检测管段
    field_2: str | None = None  # 检测方式
    field_3: str | None = None  # 检测日期
    field_4: str | None = None  # 缺陷等级
    field_5: str | None = None  # 缺陷位置
    field_6: str | None = None  # 检测班组
    field_7: str | None = None  # 报告状态

class ValveEntry(BaseModel):
    """阀门设备明细结构。"""

    field_0: str | None = None  # 阀门编号
    field_1: str | None = None  # 阀门类型
    field_2: str | None = None  # 口径规格
    field_3: str | None = None  # 所属管段
    field_4: str | None = None  # 启闭状态
    field_5: str | None = None  # 操作力矩
    field_6: str | None = None  # 上次操作日
    field_7: str | None = None  # 阀门状态

class MaintenanceEntry(BaseModel):
    """养护计划明细结构。"""

    field_0: str | None = None  # 计划编号
    field_1: str | None = None  # 养护管段
    field_2: str | None = None  # 养护类型
    field_3: str | None = None  # 计划日期
    field_4: str | None = None  # 养护班组
    field_5: str | None = None  # 工程预算
    field_6: str | None = None  # 验收日期
    field_7: str | None = None  # 计划状态

class EmergencyEntry(BaseModel):
    """抢修任务明细结构。"""

    field_0: str | None = None  # 抢修编号
    field_1: str | None = None  # 管道类型
    field_2: str | None = None  # 事故地点
    field_3: str | None = None  # 接报时间
    field_4: str | None = None  # 到场时间
    field_5: str | None = None  # 完成时间
    field_6: str | None = None  # 停水区域
    field_7: str | None = None  # 抢修状态

class ExcavationEntry(BaseModel):
    """开挖申请明细结构。"""

    field_0: str | None = None  # 申请编号
    field_1: str | None = None  # 申请单位
    field_2: str | None = None  # 施工地点
    field_3: str | None = None  # 施工范围
    field_4: str | None = None  # 涉及管线
    field_5: str | None = None  # 开挖深度
    field_6: str | None = None  # 审批意见
    field_7: str | None = None  # 申请状态

class WellEntry(BaseModel):
    """检查井明细结构。"""

    field_0: str | None = None  # 井盖编号
    field_1: str | None = None  # 井盖类型
    field_2: str | None = None  # 所在道路
    field_3: str | None = None  # 井盖材质
    field_4: str | None = None  # 安装日期
    field_5: str | None = None  # 完好情况
    field_6: str | None = None  # 巡查人
    field_7: str | None = None  # 井盖状态

class DrainageEntry(BaseModel):
    """清疏任务明细结构。"""

    field_0: str | None = None  # 清疏编号
    field_1: str | None = None  # 清疏管段
    field_2: str | None = None  # 淤积程度
    field_3: str | None = None  # 清疏方式
    field_4: str | None = None  # 计划日期
    field_5: str | None = None  # 清疏班组
    field_6: str | None = None  # 清出淤泥量
    field_7: str | None = None  # 清疏状态

class GasDetectEntry(BaseModel):
    """监测点位明细结构。"""

    field_0: str | None = None  # 点位编号
    field_1: str | None = None  # 监测气体
    field_2: str | None = None  # 所在管沟
    field_3: str | None = None  # 当前浓度
    field_4: str | None = None  # 报警阈值
    field_5: str | None = None  # 上次标定日
    field_6: str | None = None  # 监测时间
    field_7: str | None = None  # 点位状态

class LeakEntry(BaseModel):
    """漏水记录明细结构。"""

    field_0: str | None = None  # 记录编号
    field_1: str | None = None  # 检测管段
    field_2: str | None = None  # 检测方法
    field_3: str | None = None  # 疑似漏点
    field_4: str | None = None  # 漏量估算
    field_5: str | None = None  # 定位精度
    field_6: str | None = None  # 检测日期
    field_7: str | None = None  # 记录状态

class MeterRecordEntry(BaseModel):
    """贸易结算表明细结构。"""

    field_0: str | None = None  # 表具编号
    field_1: str | None = None  # 表具类型
    field_2: str | None = None  # 口径规格
    field_3: str | None = None  # 安装位置
    field_4: str | None = None  # 上次示数
    field_5: str | None = None  # 当前示数
    field_6: str | None = None  # 抄表员
    field_7: str | None = None  # 表具状态

class HydrantEntry(BaseModel):
    """消防栓明细结构。"""

    field_0: str | None = None  # 消防栓编号
    field_1: str | None = None  # 口径规格
    field_2: str | None = None  # 所在道路
    field_3: str | None = None  # 出水压力
    field_4: str | None = None  # 上次试水日
    field_5: str | None = None  # 维护单位
    field_6: str | None = None  # 完好情况
    field_7: str | None = None  # 设施状态

class TrenchEntry(BaseModel):
    """管沟段明细结构。"""

    field_0: str | None = None  # 管沟编号
    field_1: str | None = None  # 管沟位置
    field_2: str | None = None  # 沟内管线
    field_3: str | None = None  # 积水情况
    field_4: str | None = None  # 盖板完好
    field_5: str | None = None  # 气体浓度
    field_6: str | None = None  # 巡检日期
    field_7: str | None = None  # 管沟状态

class RoadOccupyEntry(BaseModel):
    """占道申请明细结构。"""

    field_0: str | None = None  # 申请编号
    field_1: str | None = None  # 施工路段
    field_2: str | None = None  # 占道面积
    field_3: str | None = None  # 占道起止日
    field_4: str | None = None  # 作业单位
    field_5: str | None = None  # 交通疏导
    field_6: str | None = None  # 审批单位
    field_7: str | None = None  # 占道状态

class BackfillEntry(BaseModel):
    """回填记录明细结构。"""

    field_0: str | None = None  # 回填编号
    field_1: str | None = None  # 修复路段
    field_2: str | None = None  # 管沟深度
    field_3: str | None = None  # 回填材料
    field_4: str | None = None  # 压实度
    field_5: str | None = None  # 路面恢复
    field_6: str | None = None  # 验收日期
    field_7: str | None = None  # 回填状态

class CorrosionEntry(BaseModel):
    """防腐记录明细结构。"""

    field_0: str | None = None  # 记录编号
    field_1: str | None = None  # 检测管段
    field_2: str | None = None  # 防腐层类型
    field_3: str | None = None  # 破损点数量
    field_4: str | None = None  # 管地电位
    field_5: str | None = None  # 检测日期
    field_6: str | None = None  # 检测人员
    field_7: str | None = None  # 记录状态
