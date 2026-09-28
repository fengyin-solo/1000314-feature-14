"""业务模块路由汇总。

这里统一按别名导入再暴露 ROUTERS：模块名有可能和内置名撞车（某个业务模块就叫 dict、list
这种名字时），按名字直接 import 会把内置类型覆盖掉，函数注解在运行时求值就会报
'module' object is not subscriptable。
"""
from __future__ import annotations

from app.routers import pipe_section as router_pipe_section
from app.routers import inspect as router_inspect
from app.routers import defect as router_defect
from app.routers import cctv as router_cctv
from app.routers import valve as router_valve
from app.routers import maintenance as router_maintenance
from app.routers import emergency as router_emergency
from app.routers import excavation as router_excavation
from app.routers import well as router_well
from app.routers import drainage as router_drainage
from app.routers import gas_detect as router_gas_detect
from app.routers import leak as router_leak
from app.routers import meter_record as router_meter_record
from app.routers import hydrant as router_hydrant
from app.routers import hydrant_reminder as router_hydrant_reminder
from app.routers import trench as router_trench
from app.routers import road_occupy as router_road_occupy
from app.routers import backfill as router_backfill
from app.routers import corrosion as router_corrosion

ROUTERS = [router_pipe_section, router_inspect, router_defect, router_cctv, router_valve, router_maintenance, router_emergency, router_excavation, router_well, router_drainage, router_gas_detect, router_leak, router_meter_record, router_hydrant, router_hydrant_reminder, router_trench, router_road_occupy, router_backfill, router_corrosion]
