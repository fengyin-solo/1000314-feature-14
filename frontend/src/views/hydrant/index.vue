<template>
  <section class="page" data-module="hydrant">
    <header class="page-head">
      <div>
        <h2>消防栓管理</h2>
        <p class="page-desc">按消防栓编号、口径规格、所在道路、出水压力建立档案与巡检队列，并从巡检和维修结果回写状态。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="showCreate = !showCreate">登记消防栓</button>
        <RouterLink class="btn" to="/hydrant-reminders">进入提醒中心</RouterLink>
        <button class="btn" type="button" @click="exportRows">导出清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form v-if="showCreate" class="editor-card" @submit.prevent="submitCreate">
      <h3>登记消防栓</h3>
      <div class="form-grid">
        <label v-for="field in createFields" :key="field.name" class="filter-item">
          <span>{{ field.label }}{{ field.required ? ' *' : '' }}</span>
          <input v-model="createForm[field.name]" :placeholder="field.label" :type="field.type">
        </label>
      </div>
      <div class="form-actions">
        <button class="btn primary" type="submit">保存档案</button>
        <button class="btn ghost" type="button" @click="showCreate = false">取消</button>
      </div>
    </form>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>消防栓编号</span>
        <input v-model="filters.keyword" placeholder="按消防栓编号检索">
      </label>
      <label class="filter-item">
        <span>口径规格</span>
        <input v-model="filters.caliber" placeholder="如 DN100">
      </label>
      <label class="filter-item">
        <span>所在道路</span>
        <input v-model="filters.road" placeholder="按道路地址检索">
      </label>
      <label class="filter-item">
        <span>最小压力</span>
        <input v-model="filters.min_pressure" type="number" step="0.01" placeholder="MPa">
      </label>
      <label class="filter-item">
        <span>最大压力</span>
        <input v-model="filters.max_pressure" type="number" step="0.01" placeholder="MPa">
      </label>
      <label class="filter-item">
        <span>状态</span>
        <select v-model="filters.status">
          <option value="">全部</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ display(row[column]) }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openPressure(row)">试水检测</button>
            <button class="link" type="button" @click="runAction('安排维修', row, {})">安排维修</button>
            <button class="link danger" type="button" @click="runAction('登记拆除', row, {})">登记拆除</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无符合条件的消防栓档案</td>
        </tr>
      </tbody>
    </table>

    <form v-if="pressureRow" class="editor-card" @submit.prevent="submitPressure">
      <h3>试水检测：{{ pressureRow['消防栓编号'] }}</h3>
      <div class="form-grid">
        <label class="filter-item">
          <span>出水压力（MPa）*</span>
          <input v-model="pressureForm['出水压力']" type="number" step="0.01" required>
        </label>
        <label class="filter-item">
          <span>试水日期</span>
          <input v-model="pressureForm['上次试水日']" type="date">
        </label>
      </div>
      <div class="form-actions">
        <button class="btn primary" type="submit">提交试水</button>
        <button class="btn ghost" type="button" @click="pressureRow = null">取消</button>
      </div>
    </form>

    <footer class="page-foot">
      <span>共 {{ total }} 条消防栓档案</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null>
type FormValue = string | number
type ApiResponse = { items?: Row[]; total?: number }
type ActionResponse = { ok: boolean; message: string }

const ENDPOINT = '/api/hydrant'
const columns = ['消防栓编号', '口径规格', '所在道路', '出水压力', '基线压力', '上次试水日', '下次试水到期日', '维护单位', '完好情况', '设施状态']
const statuses = ['完好', '待维修', '锈蚀', '无水', '已拆除']
const createFields = [
  { name: '消防栓编号', label: '消防栓编号', required: true, type: 'text' },
  { name: '口径规格', label: '口径规格', required: true, type: 'text' },
  { name: '所在道路', label: '所在道路', required: false, type: 'text' },
  { name: '出水压力', label: '出水压力（MPa）', required: false, type: 'number' },
  { name: '维护单位', label: '维护单位', required: false, type: 'text' },
]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const showCreate = ref(false)
const pressureRow = ref<Row | null>(null)
const filters = ref<Record<string, string>>({})
const createForm = ref<Record<string, FormValue>>({})
const pressureForm = ref<Record<string, string>>({ '出水压力': '', '上次试水日': '' })
const stats = ref([
  { label: '档案总数', value: 0 },
  { label: '待维修', value: 0 },
  { label: '异常/到期', value: 0 },
])

function display(value: unknown): string {
  return value === null || value === undefined || value === '' ? '—' : String(value)
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openPressure(row: Row) {
  pressureRow.value = row
  pressureForm.value = {
    '出水压力': String(row['出水压力'] ?? ''),
    '上次试水日': '',
  }
}

async function postJson(path: string, values: Record<string, unknown>): Promise<ActionResponse> {
  const response = await request(path, {
    method: 'POST',
    body: JSON.stringify({ values }),
  })
  if (!response.ok) {
    throw new Error('接口未正常处理本次操作')
  }
  return (await response.json()) as ActionResponse
}

async function submitCreate() {
  errorMessage.value = ''
  try {
    const result = await postJson(ENDPOINT, { ...createForm.value })
    if (!result.ok) {
      throw new Error(result.message)
    }
    showCreate.value = false
    createForm.value = {}
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '消防栓登记失败'
  }
}

async function submitPressure() {
  if (!pressureRow.value) return
  errorMessage.value = ''
  try {
    const result = await postJson(`${ENDPOINT}/${pressureRow.value.id}/actions`, {
      action: '试水检测',
      ...pressureForm.value,
    })
    if (!result.ok) {
      throw new Error(result.message)
    }
    pressureRow.value = null
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '试水检测提交失败'
  }
}

async function runAction(action: string, row: Row, extra: Record<string, unknown>) {
  errorMessage.value = ''
  try {
    const result = await postJson(`${ENDPOINT}/${row.id}/actions`, { action, ...extra })
    if (!result.ok) {
      throw new Error(result.message)
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '消防栓操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  Object.entries(filters.value).forEach(([key, value]) => {
    if (value) params.set(key, value)
  })
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      throw new Error('消防栓列表读取失败')
    }
    const payload = (await response.json()) as ApiResponse
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    stats.value = [
      { label: '档案总数', value: total.value },
      { label: '待维修', value: rows.value.filter((row) => row.status === '待维修').length },
      { label: '异常/到期', value: rows.value.filter((row) => Boolean(row.abnormal)).length },
    ]
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '消防栓列表读取失败'
  }
}

onMounted(reload)
</script>
