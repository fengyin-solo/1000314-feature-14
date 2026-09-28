<template>
  <section class="page" data-module="hydrant-reminders">
    <header class="page-head">
      <div>
        <h2>消防栓提醒中心</h2>
        <p class="page-desc">压力骤降、道路地址缺失、7 日内重复报修自动升级；同一栓体存在未完工单时自动抑制重复派单。</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/hydrant">返回栓体档案</RouterLink>
        <button class="btn primary" type="button" @click="generateQueue">生成巡检队列</button>
        <button class="btn" type="button" @click="reload">刷新同步状态</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value" :class="item.tone">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="generateQueue">
      <label class="filter-item">
        <span>消防栓编号</span>
        <input v-model="queueFilters.keyword" placeholder="编号">
      </label>
      <label class="filter-item">
        <span>口径规格</span>
        <input v-model="queueFilters.caliber" placeholder="如 DN100">
      </label>
      <label class="filter-item">
        <span>所在道路</span>
        <input v-model="queueFilters.road" placeholder="道路地址">
      </label>
      <label class="filter-item">
        <span>最小压力</span>
        <input v-model="queueFilters.min_pressure" type="number" step="0.01">
      </label>
      <label class="filter-item">
        <span>最大压力</span>
        <input v-model="queueFilters.max_pressure" type="number" step="0.01">
      </label>
      <button class="btn primary" type="submit">按条件生成</button>
    </form>

    <div class="tab-row">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
        type="button"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}（{{ tabCounts[tab.key] }}）
      </button>
    </div>

    <div v-if="activeTab === 'reminders'" class="table-card">
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in reminderColumns" :key="column">{{ column }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in reminders" :key="String(row.id)">
            <td v-for="column in reminderColumns" :key="column">
              <span v-if="column === '优先级'" class="badge" :class="priorityClass(row[column])">{{ display(row[column]) }}</span>
              <span v-else>{{ display(row[column]) }}</span>
            </td>
          </tr>
          <tr v-if="!reminders.length"><td :colspan="reminderColumns.length" class="empty-state">暂无提醒，请先生成巡检队列</td></tr>
        </tbody>
      </table>
    </div>

    <div v-if="activeTab === 'inspections'" class="split-layout">
      <form class="editor-card" @submit.prevent="submitInspection">
        <h3>巡检记录回写维护建议</h3>
        <label class="filter-item">
          <span>消防栓 *</span>
          <select v-model="inspectionForm.hydrant_id" required>
            <option value="" disabled>请选择消防栓</option>
            <option v-for="hydrant in hydrants" :key="String(hydrant.id)" :value="String(hydrant.id)">
              {{ hydrant['消防栓编号'] }}｜{{ hydrant['所在道路'] || '地址缺失' }}
            </option>
          </select>
        </label>
        <label class="filter-item">
          <span>巡检日期</span>
          <input v-model="inspectionForm['巡检日期']" type="date">
        </label>
        <label class="filter-item">
          <span>巡检人员</span>
          <input v-model="inspectionForm['巡检人员']">
        </label>
        <label class="filter-item">
          <span>实测出水压力（MPa）</span>
          <input v-model="inspectionForm['出水压力']" type="number" step="0.01">
        </label>
        <label class="filter-item">
          <span>维护建议 *</span>
          <textarea v-model="inspectionForm['维护建议']" rows="3" required placeholder="如：压力骤降，建议更换密封件"></textarea>
        </label>
        <button class="btn primary" type="submit">提交巡检记录</button>
      </form>

      <table class="data-table">
        <thead><tr><th v-for="column in inspectionColumns" :key="column">{{ column }}</th></tr></thead>
        <tbody>
          <tr v-for="row in inspections" :key="String(row.id)">
            <td v-for="column in inspectionColumns" :key="column">{{ display(row[column]) }}</td>
          </tr>
          <tr v-if="!inspections.length"><td :colspan="inspectionColumns.length" class="empty-state">暂无巡检记录</td></tr>
        </tbody>
      </table>
    </div>

    <div v-if="activeTab === 'reports'" class="split-layout">
      <form class="editor-card" @submit.prevent="submitReport">
        <h3>登记故障报修</h3>
        <label class="filter-item">
          <span>消防栓 *</span>
          <select v-model="reportForm.hydrant_id" required>
            <option value="" disabled>请选择消防栓</option>
            <option v-for="hydrant in hydrants" :key="String(hydrant.id)" :value="String(hydrant.id)">
              {{ hydrant['消防栓编号'] }}｜{{ hydrant['所在道路'] || '地址缺失' }}
            </option>
          </select>
        </label>
        <label class="filter-item">
          <span>报修日期</span>
          <input v-model="reportForm['报修日期']" type="date">
        </label>
        <label class="filter-item">
          <span>报修人</span>
          <input v-model="reportForm['报修人']">
        </label>
        <label class="filter-item">
          <span>报修问题 *</span>
          <textarea v-model="reportForm['报修问题']" rows="3" required></textarea>
        </label>
        <button class="btn primary" type="submit">提交报修</button>
      </form>

      <table class="data-table">
        <thead><tr><th v-for="column in reportColumns" :key="column">{{ column }}</th></tr></thead>
        <tbody>
          <tr v-for="row in reports" :key="String(row.id)">
            <td v-for="column in reportColumns" :key="column">
              <span v-if="column === '是否抑制'">{{ row[column] ? '已抑制' : '新派单' }}</span>
              <span v-else>{{ display(row[column]) }}</span>
            </td>
          </tr>
          <tr v-if="!reports.length"><td :colspan="reportColumns.length" class="empty-state">暂无报修记录</td></tr>
        </tbody>
      </table>
    </div>

    <div v-if="activeTab === 'results'" class="split-layout">
      <form class="editor-card" @submit.prevent="submitResult">
        <h3>回写维护结果</h3>
        <label class="filter-item">
          <span>未完工单 *</span>
          <select v-model="resultForm.result_id" required>
            <option value="" disabled>请选择工单</option>
            <option v-for="result in activeResults" :key="String(result.id)" :value="String(result.id)">
              {{ result['工单编号'] }}｜{{ result['消防栓编号'] }}
            </option>
          </select>
        </label>
        <label class="filter-item">
          <span>完成日期</span>
          <input v-model="resultForm['完成日期']" type="date">
        </label>
        <label class="filter-item">
          <span>复检压力（MPa）</span>
          <input v-model="resultForm['出水压力']" type="number" step="0.01">
        </label>
        <label class="filter-item">
          <span>补录道路地址</span>
          <input v-model="resultForm['所在道路']">
        </label>
        <label class="filter-item">
          <span>维护单位</span>
          <input v-model="resultForm['维护单位']">
        </label>
        <label class="filter-item">
          <span>维护建议 *</span>
          <textarea v-model="resultForm['维护建议']" rows="3" required></textarea>
        </label>
        <button class="btn primary" type="submit">完成并同步</button>
      </form>

      <table class="data-table">
        <thead><tr><th v-for="column in resultColumns" :key="column">{{ column }}</th></tr></thead>
        <tbody>
          <tr v-for="row in results" :key="String(row.id)">
            <td v-for="column in resultColumns" :key="column">{{ display(row[column]) }}</td>
          </tr>
          <tr v-if="!results.length"><td :colspan="resultColumns.length" class="empty-state">暂无维修工单</td></tr>
        </tbody>
      </table>
    </div>

    <footer class="page-foot">
      <span>{{ feedback || '提醒中心、栓体档案和维护结果共享到期日与状态' }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null>
type TabKey = 'reminders' | 'inspections' | 'reports' | 'results'
type ListPayload = { items?: Row[]; total?: number }
type ActionPayload = { ok: boolean; message: string }

const ENDPOINT = '/api/hydrant'
const tabs: Array<{ key: TabKey; label: string }> = [
  { key: 'reminders', label: '提醒中心' },
  { key: 'inspections', label: '巡检记录' },
  { key: 'reports', label: '故障报修' },
  { key: 'results', label: '维护结果' },
]
const reminderColumns = ['提醒编号', '消防栓编号', '口径规格', '所在道路', '出水压力', '升级原因', '优先级', '到期日', '提醒状态', '工单编号', '报修次数']
const inspectionColumns = ['巡检记录编号', '消防栓编号', '所在道路', '出水压力', '巡检日期', '巡检人员', '维护建议', '巡检状态']
const reportColumns = ['报修编号', '消防栓编号', '报修日期', '报修问题', '报修人', '工单编号', '是否抑制', 'status']
const resultColumns = ['工单编号', '消防栓编号', '所在道路', '派单日期', '到期日', '完成日期', '问题来源', '维护建议', '维护单位', '工单状态']

const activeTab = ref<TabKey>('reminders')
const hydrants = ref<Row[]>([])
const reminders = ref<Row[]>([])
const inspections = ref<Row[]>([])
const reports = ref<Row[]>([])
const results = ref<Row[]>([])
const feedback = ref('')
const errorMessage = ref('')
const queueFilters = ref<Record<string, string>>({})
const inspectionForm = ref<Record<string, string>>({ hydrant_id: '', '巡检日期': '', '巡检人员': '', '出水压力': '', '维护建议': '' })
const reportForm = ref<Record<string, string>>({ hydrant_id: '', '报修日期': '', '报修人': '', '报修问题': '' })
const resultForm = ref<Record<string, string>>({ result_id: '', '完成日期': '', '出水压力': '', '所在道路': '', '维护单位': '', '维护建议': '' })

const activeResults = computed(() => results.value.filter((row) => row['工单状态'] === '待派单' || row['工单状态'] === '维修中'))
const stats = computed(() => [
  { label: '活动提醒', value: reminders.value.filter((row) => ['待巡检', '待派单', '维修中'].includes(String(row['提醒状态']))).length, tone: 'urgent' },
  { label: '紧急升级', value: reminders.value.filter((row) => row['优先级'] === '紧急').length, tone: 'urgent' },
  { label: '未完工单', value: activeResults.value.length, tone: 'warning' },
  { label: '已抑制报修', value: reports.value.filter((row) => Boolean(row['是否抑制'])).length, tone: '' },
])
const tabCounts = computed<Record<TabKey, number>>(() => ({
  reminders: reminders.value.length,
  inspections: inspections.value.length,
  reports: reports.value.length,
  results: results.value.length,
}))

function display(value: unknown): string {
  return value === null || value === undefined || value === '' ? '—' : String(value)
}

function priorityClass(value: unknown): string {
  if (value === '紧急') return 'urgent'
  if (value === '升级') return 'warning'
  return 'normal'
}

async function getList(path: string): Promise<Row[]> {
  const response = await request(path)
  if (!response.ok) {
    throw new Error(`读取失败：${path}`)
  }
  const payload = (await response.json()) as ListPayload
  return payload.items ?? []
}

async function post(path: string, values: Record<string, unknown>): Promise<ActionPayload> {
  const response = await request(path, {
    method: 'POST',
    body: JSON.stringify({ values }),
  })
  if (!response.ok) {
    throw new Error('接口未正常处理本次操作')
  }
  return (await response.json()) as ActionPayload
}

function cleanValues(values: Record<string, string>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(values).filter(([, value]) => value !== ''))
}

async function generateQueue() {
  errorMessage.value = ''
  try {
    const result = await post(`${ENDPOINT}/queue/generate`, cleanValues(queueFilters.value))
    if (!result.ok) throw new Error(result.message)
    feedback.value = result.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '巡检队列生成失败'
  }
}

async function submitInspection() {
  errorMessage.value = ''
  try {
    const result = await post(`${ENDPOINT}/inspections`, cleanValues(inspectionForm.value))
    if (!result.ok) throw new Error(result.message)
    feedback.value = result.message
    inspectionForm.value = { hydrant_id: '', '巡检日期': '', '巡检人员': '', '出水压力': '', '维护建议': '' }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '巡检记录回写失败'
  }
}

async function submitReport() {
  errorMessage.value = ''
  try {
    const result = await post(`${ENDPOINT}/reports`, cleanValues(reportForm.value))
    if (!result.ok) throw new Error(result.message)
    feedback.value = result.message
    reportForm.value = { hydrant_id: '', '报修日期': '', '报修人': '', '报修问题': '' }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '故障报修失败'
  }
}

async function submitResult() {
  errorMessage.value = ''
  try {
    const result = await post(`${ENDPOINT}/results/complete`, cleanValues(resultForm.value))
    if (!result.ok) throw new Error(result.message)
    feedback.value = result.message
    resultForm.value = { result_id: '', '完成日期': '', '出水压力': '', '所在道路': '', '维护单位': '', '维护建议': '' }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '维护结果回写失败'
  }
}

async function reload() {
  errorMessage.value = ''
  try {
    const [hydrantRows, reminderRows, inspectionRows, reportRows, resultRows] = await Promise.all([
      getList(`${ENDPOINT}?size=200`),
      getList(`${ENDPOINT}/reminders?size=200`),
      getList(`${ENDPOINT}/inspections?size=200`),
      getList(`${ENDPOINT}/reports?size=200`),
      getList(`${ENDPOINT}/results?size=200`),
    ])
    hydrants.value = hydrantRows
    reminders.value = reminderRows
    inspections.value = inspectionRows
    reports.value = reportRows
    results.value = resultRows
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '提醒中心数据读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.btn { text-decoration: none; display: inline-flex; align-items: center; }
.tab-row { display: flex; gap: 8px; margin: 12px 0; }
.tab-btn { border: 1px solid var(--border); background: #fff; border-radius: 6px 6px 0 0; padding: 8px 12px; cursor: pointer; }
.tab-btn.active { background: var(--brand); color: #fff; border-color: var(--brand); }
.table-card, .split-layout { overflow-x: auto; }
.split-layout { display: grid; grid-template-columns: 320px 1fr; gap: 12px; align-items: start; }
.editor-card { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 12px; display: flex; flex-direction: column; gap: 10px; }
.editor-card h3 { margin: 0; font-size: 15px; }
.editor-card textarea, .editor-card input, .editor-card select { width: 100%; padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; }
.form-actions { display: flex; gap: 8px; }
.badge { border-radius: 999px; padding: 2px 8px; font-size: 12px; }
.badge.urgent { background: #fee4e2; color: #b42318; }
.badge.warning { background: #fef0c7; color: #b54708; }
.badge.normal { background: #e2e8f0; color: #475569; }
.stat-value.urgent { color: #b42318; }
.stat-value.warning { color: #b54708; }
@media (max-width: 960px) { .split-layout { grid-template-columns: 1fr; } }
</style>
