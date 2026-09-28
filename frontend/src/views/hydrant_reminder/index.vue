<template>
  <section class="page" data-module="hydrant_reminder">
    <header class="page-head">
      <div>
        <h2>消防栓维护提醒</h2>
        <p class="page-desc">
          按消防栓编号、口径规格、所在道路、出水压力生成巡检队列；压力骤降、道路地址缺失或 30 天内重复报修自动升级，
          重复工单自动抑制；巡检记录可回写维护建议，提醒中心、栓体档案与维护结果同步到期日与状态。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openReportModal">登记巡检记录</button>
        <button class="btn" type="button" @click="exportData">导出提醒清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in statCards" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="generate">
      <label class="filter-item">
        <span>消防栓编号</span>
        <input v-model="filters.keyword" placeholder="按编号检索" />
      </label>
      <label class="filter-item">
        <span>口径规格</span>
        <input v-model="filters.spec" placeholder="如 DN100" />
      </label>
      <label class="filter-item">
        <span>所在道路</span>
        <input v-model="filters.road" placeholder="按道路检索" />
      </label>
      <label class="filter-item">
        <span>出水压力下限(MPa)</span>
        <input v-model.number="filters.pressure_min" type="number" step="0.01" min="0" />
      </label>
      <label class="filter-item">
        <span>出水压力上限(MPa)</span>
        <input v-model.number="filters.pressure_max" type="number" step="0.01" min="0" />
      </label>
      <label class="filter-item">
        <span>级别</span>
        <select v-model="filters.level">
          <option value="">全部</option>
          <option value="常规">常规</option>
          <option value="升级">升级</option>
        </select>
      </label>
      <button class="btn primary" type="submit">生成巡检队列</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <p v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</p>

    <h3 class="section-title">巡检队列 · 提醒中心（共 {{ queueTotal }} 条）</h3>
    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in queueColumns" :key="column">{{ column === 'status' ? '提醒状态' : column }}</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in queue" :key="String(row.id)" :class="{ 'row-escalated': row['级别'] === '升级' }">
          <td v-for="column in queueColumns" :key="column">
            <template v-if="column === '级别'">
              <span :class="row[column] === '升级' ? 'tag tag-danger' : 'tag'">{{ row[column] }}</span>
            </template>
            <template v-else-if="column === '升级原因'">
              {{ formatReasons(row[column]) }}
            </template>
            <template v-else>{{ row[column] || '—' }}</template>
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="runQueueAction('开始巡检', row)">开始巡检</button>
            <button class="link" type="button" @click="runQueueAction('生成工单', row)">生成工单</button>
            <button class="link" type="button" @click="runQueueAction('开始维护', row)">开始维护</button>
            <button class="link" type="button" @click="runQueueAction('完成维护', row)">完成维护</button>
            <button class="link danger-link" type="button" @click="runQueueAction('关闭提醒', row)">关闭</button>
          </td>
        </tr>
        <tr v-if="!queue.length">
          <td :colspan="queueColumns.length + 1" class="empty-state">点击「生成巡检队列」加载消防栓提醒</td>
        </tr>
      </tbody>
    </table>

    <h3 class="section-title">巡检记录（试水检测 / 报修）</h3>
    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in reportColumns" :key="column">{{ column === 'status' ? '记录状态' : column }}</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in reports" :key="String(row.id)">
          <td v-for="column in reportColumns" :key="column">{{ row[column] || '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openAdviceModal(row)">回写维护建议</button>
          </td>
        </tr>
        <tr v-if="!reports.length">
          <td :colspan="reportColumns.length + 1" class="empty-state">暂无巡检记录</td>
        </tr>
      </tbody>
    </table>

    <h3 class="section-title">维护工单 · 维护结果</h3>
    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in workOrderColumns" :key="column">{{ column === 'status' ? '工单状态' : column }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in workOrders" :key="String(row.id)" :class="{ 'row-escalated': row['级别'] === '升级' }">
          <td v-for="column in workOrderColumns" :key="column">
            <template v-if="column === '升级原因'">{{ row[column] || '—' }}</template>
            <template v-else>{{ row[column] || '—' }}</template>
          </td>
        </tr>
        <tr v-if="!workOrders.length">
          <td :colspan="workOrderColumns.length" class="empty-state">暂无维护工单，升级或手动生成后出现</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>队列 {{ queueTotal }} 条 · 巡检记录 {{ reportTotal }} 条 · 工单 {{ workOrderTotal }} 条</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 登记巡检记录 -->
    <div v-if="reportModal.open" class="modal-mask" @click.self="closeReportModal">
      <div class="modal">
        <h4>登记巡检记录</h4>
        <label class="modal-field"><span>消防栓编号 *</span><input v-model="reportModal.form['消防栓编号']" placeholder="如 HYDR-1006" /></label>
        <label class="modal-field"><span>巡检日期</span><input v-model="reportModal.form['巡检日期']" type="date" /></label>
        <label class="modal-field"><span>巡检人员</span><input v-model="reportModal.form['巡检人员']" /></label>
        <label class="modal-field"><span>实测压力(MPa)</span><input v-model="reportModal.form['实测压力']" placeholder="如 0.26" /></label>
        <label class="modal-field">
          <span>是否报修</span>
          <select v-model="reportModal.form['是否报修']">
            <option value="false">否（试水检测）</option>
            <option value="true">是（报修）</option>
          </select>
        </label>
        <label class="modal-field"><span>问题描述</span><textarea v-model="reportModal.form['问题描述']" rows="2"></textarea></label>
        <label class="modal-field"><span>维护建议（可选）</span><textarea v-model="reportModal.form['维护建议']" rows="2"></textarea></label>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="closeReportModal">取消</button>
          <button class="btn primary" type="button" @click="submitReport">提交并重新评估</button>
        </div>
      </div>
    </div>

    <!-- 回写维护建议 -->
    <div v-if="adviceModal.open" class="modal-mask" @click.self="closeAdviceModal">
      <div class="modal">
        <h4>回写维护建议 · {{ adviceModal.form['记录编号'] }}</h4>
        <p class="page-desc">建议将同步到提醒中心与未完工单，栓体档案到期日与状态一并更新。</p>
        <label class="modal-field"><span>维护建议 *</span><textarea v-model="adviceModal.form['维护建议']" rows="3"></textarea></label>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="closeAdviceModal">取消</button>
          <button class="btn primary" type="button" @click="submitAdvice">确认回写</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

const ENDPOINT = '/api/hydrant-reminder'
type Row = Record<string, string | number | boolean | string[] | null>

const queueColumns = ['提醒编号', '消防栓编号', '口径规格', '所在道路', '出水压力', '级别', 'status', '到期日', '升级原因', '工单状态', '抑制次数', '维护建议']
const reportColumns = ['记录编号', '消防栓编号', '巡检日期', '巡检人员', '实测压力', '是否报修', '问题描述', '维护建议', 'status']
const workOrderColumns = ['工单编号', '消防栓编号', '口径规格', '所在道路', '级别', 'status', '升级原因', '维护建议', '开工日期', '完工日期', '到期日', '抑制次数', '最后抑制日']

const queue = ref<Row[]>([])
const reports = ref<Row[]>([])
const workOrders = ref<Row[]>([])
const queueTotal = ref(0)
const reportTotal = ref(0)
const workOrderTotal = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const statCards = ref<{ label: string; value: number }[]>([])

const filters = reactive({
  keyword: '',
  spec: '',
  road: '',
  pressure_min: '' as number | '',
  pressure_max: '' as number | '',
  level: '',
})

const reportModal = reactive({
  open: false,
  form: {
    消防栓编号: '',
    巡检日期: '',
    巡检人员: '',
    实测压力: '',
    是否报修: 'false',
    问题描述: '',
    维护建议: '',
  } as Record<string, string>,
})

const adviceModal = reactive({
  open: false,
  reportId: 0,
  form: { 记录编号: '', 维护建议: '' },
})

function formatReasons(value: unknown): string {
  return Array.isArray(value) ? value.join('；') : String(value || '')
}

function resetFilters() {
  filters.keyword = ''
  filters.spec = ''
  filters.road = ''
  filters.pressure_min = ''
  filters.pressure_max = ''
  filters.level = ''
  void generate()
}

async function generate() {
  errorMessage.value = ''
  noticeMessage.value = ''
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== '' && value !== null && value !== undefined) params.set(key, String(value))
  })
  try {
    const response = await request(`${ENDPOINT}/queue?${params.toString()}`)
    if (!response.ok) throw new Error('巡检队列生成失败')
    const payload = await response.json()
    queue.value = payload.items ?? []
    queueTotal.value = payload.total ?? 0
    await loadSideTables()
    const escalated = queue.value.filter((row) => row['级别'] === '升级').length
    noticeMessage.value = escalated
      ? `队列已生成：${escalated} 条升级提醒（压力骤降 / 地址缺失 / 重复报修），重复工单已抑制`
      : '巡检队列已生成，当前无升级提醒'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '巡检队列生成失败'
  }
}

async function loadSideTables() {
  const [reportRes, workRes, statsRes] = await Promise.all([
    request(`${ENDPOINT}/reports?size=100`),
    request(`${ENDPOINT}/work-orders?size=100`),
    request(`${ENDPOINT}/stats`),
  ])
  if (reportRes.ok) {
    const data = await reportRes.json()
    reports.value = data.items ?? []
    reportTotal.value = data.total ?? 0
  }
  if (workRes.ok) {
    const data = await workRes.json()
    workOrders.value = data.items ?? []
    workOrderTotal.value = data.total ?? 0
  }
  if (statsRes.ok) {
    const stats = await statsRes.json()
    statCards.value = [
      { label: '待处理提醒', value: stats['待处理提醒'] ?? 0 },
      { label: '升级提醒', value: stats['升级提醒'] ?? 0 },
      { label: '待维护工单', value: stats['待维护工单'] ?? 0 },
      { label: '今日抑制重复工单', value: stats['今日抑制重复工单'] ?? 0 },
    ]
  }
}

async function runQueueAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message || '提醒动作未生效')
    }
    noticeMessage.value = payload.message
    await generate()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '提醒动作失败'
  }
}

function openReportModal() {
  reportModal.open = true
  reportModal.form = {
    消防栓编号: '',
    巡检日期: new Date().toISOString().slice(0, 10),
    巡检人员: '',
    实测压力: '',
    是否报修: 'false',
    问题描述: '',
    维护建议: '',
  }
}

function closeReportModal() {
  reportModal.open = false
}

async function submitReport() {
  errorMessage.value = ''
  try {
    const values: Record<string, unknown> = { ...reportModal.form }
    values['是否报修'] = reportModal.form['是否报修'] === 'true'
    const response = await request(`${ENDPOINT}/reports`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) throw new Error(payload.message || '巡检记录登记失败')
    closeReportModal()
    noticeMessage.value = payload.message
    await generate()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '巡检记录登记失败'
  }
}

function openAdviceModal(row: Row) {
  adviceModal.open = true
  adviceModal.reportId = Number(row.id)
  adviceModal.form = {
    记录编号: String(row['记录编号'] ?? ''),
    维护建议: String(row['维护建议'] ?? ''),
  }
}

function closeAdviceModal() {
  adviceModal.open = false
}

async function submitAdvice() {
  errorMessage.value = ''
  if (!adviceModal.form['维护建议'].trim()) {
    errorMessage.value = '维护建议不能为空'
    return
  }
  try {
    const response = await request(`${ENDPOINT}/reports/${adviceModal.reportId}/write-back`, {
      method: 'POST',
      body: JSON.stringify({ values: { 维护建议: adviceModal.form['维护建议'] } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) throw new Error(payload.message || '维护建议回写失败')
    closeAdviceModal()
    noticeMessage.value = payload.message
    await generate()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '维护建议回写失败'
  }
}

function exportData() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

onMounted(generate)
</script>

<style scoped>
.section-title {
  margin: 18px 0 8px;
  font-size: 15px;
}
.notice-text {
  margin: 8px 0;
  padding: 8px 10px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  border-radius: 6px;
  color: #9a3412;
  font-size: 13px;
}
.row-escalated {
  background: #fef2f2;
}
.tag {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 10px;
  background: #e2e8f0;
  font-size: 12px;
}
.tag-danger {
  background: #fee2e2;
  color: #b42318;
}
.danger-link {
  color: #b42318;
}
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal {
  width: 460px;
  max-height: 86vh;
  overflow: auto;
  background: #fff;
  border-radius: 10px;
  padding: 18px 20px;
}
.modal h4 {
  margin: 0 0 10px;
}
.modal-field {
  display: block;
  margin-bottom: 10px;
  font-size: 12px;
  color: var(--muted);
}
.modal-field input,
.modal-field select,
.modal-field textarea {
  width: 100%;
  margin-top: 4px;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font: inherit;
  color: #1f2937;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}
</style>
