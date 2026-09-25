<template>
  <section class="page" data-module="permit">
    <header class="page-head">
      <div>
        <h2>作业许可管理</h2>
        <p class="page-desc">
          只展示当前角色授权区域内的作业许可；同一片区域同时生效的许可只放行优先级最高的一条，其余只读。
          当前角色：{{ session.identity?.角色名称 }} · {{ session.identity?.授权范围 }}
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="exportRows">导出作业许可清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
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
          <td v-for="column in columns" :key="column">
            <template v-if="column === '放行状态'">
              <span v-if="row[column] === '放行'" class="tag tag-pass">放行</span>
              <span v-else-if="row[column] === '只读'" class="tag tag-readonly" :title="String(row.只读原因 ?? '')">只读</span>
              <span v-else>—</span>
            </template>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td class="row-actions">
            <template v-if="canAct && !row.只读">
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
            <span v-else-if="row.只读" class="inline-tip">只读：{{ row.只读原因 ?? '区域内已有更高优先级许可' }}</span>
            <span v-else class="inline-tip">当前角色仅可查看</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">授权区域内暂无作业许可数据</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条作业许可记录（已按许可编号去重）</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request, responseError } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, string | number | boolean | null>

const ENDPOINT = '/api/permit'
const columns = ["许可编号", "作业类型", "作业地点", "工作负责人", "许可时间", "有效期至", "优先级", "放行状态", "许可状态"]
const actions = ["提交申请", "签发许可", "驳回申请"]
const stats = [{"label": "授权区域内许可", "value": 0}, {"label": "放行中许可", "value": 0}, {"label": "只读排队许可", "value": 0}]

const session = useSessionStore()
const canAct = computed(() => session.can('permit_action'))

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = ["许可编号", "作业地点"]

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
      // 403：越权提交，后端 detail 里写明了拒绝原因
      throw new Error(await responseError(response, '作业许可动作未生效'))
    }
    if (!payload.ok) {
      throw new Error(payload.message || '作业许可动作未生效')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '作业许可操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error(await responseError(response, '作业许可单列表读取失败'))
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    stats[0].value = total.value
    stats[1].value = rows.value.filter((row) => row.放行状态 === '放行').length
    stats[2].value = rows.value.filter((row) => row.放行状态 === '只读').length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '作业许可列表读取失败'
  }
}

onMounted(reload)
</script>
