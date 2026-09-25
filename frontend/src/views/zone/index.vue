<template>
  <section class="page" data-module="zone">
    <header class="page-head">
      <div>
        <h2>安全区域管控</h2>
        <p class="page-desc">按作业地点圈定电子围栏并给角色分配授权区域；越界告警单独列出并提醒值班人，不混入普通告警。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="showCreate = !showCreate">圈定安全区域</button>
        <button class="btn" type="button" @click="exportRows">导出安全区域清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <p class="scope-note">当前角色：{{ store.role }} · 仅显示授权区域内的安全区域与越界告警</p>

    <form v-if="showCreate" class="create-form" @submit.prevent="createZone">
      <label v-for="field in createFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="createForm[field]" :placeholder="`请输入${field}`" />
      </label>
      <button class="btn primary" type="submit">提交圈定</button>
      <button class="btn ghost" type="button" @click="showCreate = false">取消</button>
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
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="adjustBoundary(row)">调整围栏</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">当前角色没有可见的安全区域</td>
        </tr>
      </tbody>
    </table>

    <section class="boundary-board">
      <h3 class="boundary-title">越界告警看板</h3>
      <p class="page-desc">越界告警单独标出并提醒值班人，不会显示成普通告警。</p>
      <table class="data-table boundary-table">
        <thead>
          <tr>
            <th v-for="column in alarmColumns" :key="column">{{ column }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in boundaryAlarms" :key="String(row.id)" class="boundary-row">
            <td v-for="column in alarmColumns" :key="column">
              <span v-if="column === '告警类型'" class="tag boundary-tag">越界</span>
              <template v-else>{{ row[column] ?? '—' }}</template>
            </td>
          </tr>
          <tr v-if="!boundaryAlarms.length">
            <td :colspan="alarmColumns.length" class="empty-state">授权区域内暂无越界告警</td>
          </tr>
        </tbody>
      </table>
    </section>

    <footer class="page-foot">
      <span>共 {{ total }} 片授权安全区域 · {{ boundaryAlarms.length }} 条越界告警</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, string | number | boolean | null>

const ENDPOINT = '/api/zone'
const columns = ["区域编号", "区域名称", "作业地点", "围栏范围", "授权角色", "值班人", "区域状态"]
const alarmColumns = ["告警编号", "告警类型", "告警等级", "触发设备", "作业地点", "提醒值班人", "触发时间", "告警状态"]
const createFields = ["区域编号", "区域名称", "作业地点", "围栏范围", "授权角色", "值班人"]

const store = useSessionStore()
const rows = ref<Row[]>([])
const boundaryAlarms = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const showCreate = ref(false)
const createForm = reactive<Record<string, string>>({})

const stats = computed(() => [
  { label: '授权区域', value: total.value },
  { label: '越界告警', value: boundaryAlarms.value.length },
  { label: '涉及值班人', value: new Set(boundaryAlarms.value.map((row) => String(row['提醒值班人'] ?? ''))).size },
])

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function createZone() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}?role=${encodeURIComponent(store.role)}`, {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm } }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      errorMessage.value = payload.message ?? '安全区域圈定被拒绝'
      return
    }
    showCreate.value = false
    Object.keys(createForm).forEach((key) => delete createForm[key])
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '安全区域圈定失败'
  }
}

async function adjustBoundary(row: Row) {
  errorMessage.value = ''
  const boundary = window.prompt(`调整 ${row['区域编号']} 的电子围栏边界`, String(row['围栏范围'] ?? ''))
  if (boundary === null) {
    return
  }
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions?role=${encodeURIComponent(store.role)}`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: '调整围栏', 围栏范围: boundary } }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      errorMessage.value = payload.message ?? '电子围栏调整被拒绝'
      return
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '电子围栏调整失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const role = encodeURIComponent(store.role)
  try {
    const [zoneResp, alarmResp] = await Promise.all([
      request(`${ENDPOINT}?role=${role}`),
      request(`${ENDPOINT}/alarms?role=${role}`),
    ])
    if (!zoneResp.ok || !alarmResp.ok) {
      throw new Error('安全区域数据读取失败')
    }
    const zonePayload = await zoneResp.json()
    const alarmPayload = await alarmResp.json()
    rows.value = zonePayload.items ?? []
    total.value = zonePayload.total ?? rows.value.length
    boundaryAlarms.value = alarmPayload.items ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '安全区域数据读取失败'
  }
}

watch(() => store.role, reload)
onMounted(reload)
</script>
