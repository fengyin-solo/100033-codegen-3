<template>
  <section class="page" data-module="alarm">
    <header class="page-head">
      <div>
        <h2>告警中心管理</h2>
        <p class="page-desc">维护告警事件，围绕告警编号、告警类型、告警等级、触发设备做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记告警事件</button>
        <button class="btn" type="button" @click="exportRows">导出告警中心清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <p class="scope-note">当前角色：{{ store.role }} · 仅显示授权区域内的告警；越界告警不在此列表，请在安全区域看板查看</p>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
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
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">授权区域内暂无告警中心数据，可先登记告警事件</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条告警中心记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/alarm'
const columns = ["告警编号", "告警类型", "告警等级", "触发设备", "触发时间", "确认人员", "处置说明", "告警状态"]
const actions = ["确认告警", "处置告警", "忽略告警"]
const stats = [{"label": "今日告警", "value": 0}, {"label": "待确认告警", "value": 0}, {"label": "高等级告警", "value": 0}]

const store = useSessionStore()
const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '告警事件登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      errorMessage.value = payload.message ?? '告警中心动作未生效'
      return
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '告警中心操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>)
  query.set('role', store.role)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('告警事件列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '告警中心列表读取失败'
  }
}

watch(() => store.role, reload)
onMounted(reload)
</script>
