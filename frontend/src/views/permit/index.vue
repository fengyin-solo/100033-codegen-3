<template>
  <section class="page" data-module="permit">
    <header class="page-head">
      <div>
        <h2>作业许可管理</h2>
        <p class="page-desc">维护作业许可单，围绕许可编号、作业类型、作业地点、工作负责人做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="showCreate = !showCreate">登记作业许可单</button>
        <button class="btn" type="button" @click="exportRows">导出作业许可清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <p class="scope-note">当前角色：{{ store.role }} · 仅显示授权区域内的作业许可；同区域多条许可同时生效时按优先级只放行一条，其余只读</p>

    <form v-if="showCreate" class="create-form" @submit.prevent="createEntry">
      <label v-for="field in createFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <select v-if="field === '优先级'" v-model="createForm[field]">
          <option v-for="level in priorities" :key="level" :value="level">{{ level }}</option>
        </select>
        <input v-else v-model="createForm[field]" :placeholder="`请输入${field}`" />
      </label>
      <button class="btn primary" type="submit">提交登记</button>
      <button class="btn ghost" type="button" @click="showCreate = false">取消</button>
    </form>

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
        <tr v-for="row in rows" :key="String(row.id)" :class="{ 'row-readonly': isReadonly(row) }">
          <td v-for="column in columns" :key="column">
            <span v-if="column === '放行状态' && isReadonly(row)" class="tag readonly-tag">只读</span>
            <template v-else>{{ row[column] || '—' }}</template>
          </td>
          <td class="row-actions">
            <template v-if="isReadonly(row)">
              <span class="readonly-hint">等待放行</span>
            </template>
            <template v-else>
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
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">授权区域内暂无作业许可数据，可先登记作业许可单</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条作业许可记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, string | number | boolean | null>

const ENDPOINT = '/api/permit'
const columns = ["许可编号", "作业类型", "作业地点", "区域编号", "优先级", "工作负责人", "许可时间", "有效期至", "许可状态", "放行状态"]
const actions = ["提交申请", "签发许可", "驳回申请"]
const priorities = ["高", "中", "低"]
const createFields = ["许可编号", "作业类型", "作业地点", "优先级", "工作负责人"]

const store = useSessionStore()
const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const showCreate = ref(false)
const createForm = reactive<Record<string, string>>({ 优先级: '中' })

const stats = computed(() => [
  { label: '授权区域许可', value: total.value },
  { label: '放行中', value: rows.value.filter((row) => row['放行状态'] === '放行中').length },
  { label: '只读等待', value: rows.value.filter((row) => isReadonly(row)).length },
])

function isReadonly(row: Row) {
  return Boolean(row['只读'])
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function createEntry() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}?role=${encodeURIComponent(store.role)}`, {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm } }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      errorMessage.value = payload.message ?? '作业许可单登记被拒绝'
      return
    }
    showCreate.value = false
    Object.keys(createForm).forEach((key) => {
      if (key !== '优先级') delete createForm[key]
    })
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '作业许可单登记失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions?role=${encodeURIComponent(store.role)}`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      errorMessage.value = payload.message ?? '作业许可动作未生效'
      return
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '作业许可操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>)
  query.set('role', store.role)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('作业许可单列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '作业许可列表读取失败'
  }
}

watch(() => store.role, reload)
onMounted(reload)
</script>
