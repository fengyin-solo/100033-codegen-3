<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标；许可与告警按当前角色授权区域统计，越界告警单独成卡。</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn primary" to="/safety">进入安全区域管控</RouterLink>
      </div>
    </header>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value" :class="{ 'error-text': card.label === '待提醒越界告警' && card.value > 0 }">
          {{ card.value }}
        </strong>
      </article>
    </div>
    <p v-if="scope" class="page-desc">当前角色：{{ scope.角色 }} · {{ scope.授权范围 }}</p>
    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ row.name }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
  scope?: { 角色: string; 授权范围: string }
  boundary_pending?: number
}

const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])
const scope = ref<Overview['scope']>()

onMounted(async () => {
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
    scope.value = payload.scope
    // 越界告警单独成卡，不并入普通告警异常量
    if (payload.boundary_pending !== undefined) {
      cards.value = [
        ...cards.value,
        { label: '待提醒越界告警', value: payload.boundary_pending },
      ]
    }
  } catch {
    cards.value = [{"label": "业务模块", "value": 0}, {"label": "今日新增", "value": 0}]
  }
})
</script>
