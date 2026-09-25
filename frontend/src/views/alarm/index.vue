<template>
  <section class="page" data-module="alarm">
    <header class="page-head">
      <div>
        <h2>告警中心管理</h2>
        <p class="page-desc">
          仅展示当前角色授权区域内的普通告警；越界告警不显示在此列表，统一到
          <RouterLink to="/safety" class="link">安全区域管控 · 越界告警看板</RouterLink>处理。
          当前角色：{{ session.identity?.角色名称 }} · {{ session.identity?.授权范围 }}
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="exportRows">导出普通告警清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">越界告警</span>
        <strong class="stat-value error-text">{{ boundaryPending }}</strong>
      </article>
    </div>

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
            <template v-if="canAct">
              <button
                v-for="action in actions"
                :key="action"
                class="link"
                type="button"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
            </template>
            <span v-else class="inline-tip">当前角色仅可查看</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">授权区域内暂无普通告警数据</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条普通告警记录（越界告警不在此列表）</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchJson, request, responseError } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/alarm'
const columns = ["告警编号", "告警类型", "告警等级", "触发设备", "触发时间", "确认人员", "处置说明", "告警状态"]
const actions = ["确认告警", "处置告警", "忽略告警"]
const stats = ref([{"label": "今日普通告警", "value": 0}, {"label": "待确认告警", "value": 0}, {"label": "高等级告警", "value": 0}])

const session = useSessionStore()
const canAct = computed(() => session.can('alarm_action'))

const rows = ref<Row[]>([])
const total = ref(0)
const boundaryPending = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = ["告警编号", "触发设备"]

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = (await response.json()) as { ok: boolean; message: string }
    if (!response.ok) {
      throw new Error(await responseError(response, '告警动作未生效'))
    }
    if (!payload.ok) {
      throw new Error(payload.message || '告警动作未生效')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '告警中心操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const [listResp, overview] = await Promise.all([
      request(`${ENDPOINT}?${query}`),
      fetchJson<{ boundary_pending: number }>('/api/overview'),
    ])
    if (!listResp.ok) {
      throw new Error(await responseError(listResp, '告警事件列表读取失败'))
    }
    const payload = await listResp.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    stats.value[0].value = total.value
    stats.value[1].value = rows.value.filter((row) => row.告警状态 === '待确认').length
    stats.value[2].value = rows.value.filter((row) => String(row.告警等级).includes('一级')).length
    boundaryPending.value = overview.boundary_pending ?? 0
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '告警中心列表读取失败'
  }
}

onMounted(reload)
</script>
