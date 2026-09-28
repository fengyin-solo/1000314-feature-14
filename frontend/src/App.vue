<template>
  <div class="app-shell">
    <aside class="app-side">
      <h1 class="app-title">城市地下管网养护管理平台</h1>
      <nav class="nav-list">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item">
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="app-main">
      <header class="app-head">
        <span class="head-desc">面向市政供排水、燃气、供热、电力管线等地下管网的普查建档、巡检养护、病害修复、开挖审批与应急抢修的综合管理后台。</span>
        <span class="head-user">当前值班：{{ store.operator }} · {{ store.shiftLabel }}</span>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useSessionStore } from '@/stores/session'

const store = useSessionStore()

const navItems = [{ label: "运营概览", path: "/" }, { label: "管段档案", path: "/pipe_section" }, { label: "巡查记录", path: "/inspect" }, { label: "病害管理", path: "/defect" }, { label: "CCTV检测", path: "/cctv" }, { label: "阀门管理", path: "/valve" }, { label: "养护计划", path: "/maintenance" }, { label: "应急抢修", path: "/emergency" }, { label: "开挖审批", path: "/excavation" }, { label: "井盖管理", path: "/well" }, { label: "排水清疏", path: "/drainage" }, { label: "气体监测", path: "/gas_detect" }, { label: "漏水检测", path: "/leak" }, { label: "水表管理", path: "/meter_record" }, { label: "消防栓管理", path: "/hydrant" }, { label: "消防栓提醒", path: "/hydrant-reminders" }, { label: "管沟巡检", path: "/trench" }, { label: "占道施工", path: "/road_occupy" }, { label: "回填修复", path: "/backfill" }, { label: "防腐检测", path: "/corrosion" }]
</script>
