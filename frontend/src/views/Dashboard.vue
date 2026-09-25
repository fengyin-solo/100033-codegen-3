<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常。</p>
      </div>
    </header>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>

    <section class="scope-board">
      <h3 class="scope-title">当前角色授权范围</h3>
      <p class="page-desc">角色：{{ store.role }} · 授权范围与角色保持一致，切换角色后看板同步更新。</p>
      <div class="scope-zone-list">
        <span v-for="zone in scopeZones" :key="zone" class="tag scope-tag">{{ zone }}</span>
        <span v-if="!scopeZones.length" class="empty-state">当前角色没有授权区域</span>
      </div>
      <p v-if="boundaryCount" class="boundary-hint">
        授权区域内有 {{ boundaryCount }} 条越界告警待值班人处理，请前往安全区域看板。
      </p>
    </section>

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
import { onMounted, ref, watch } from 'vue'

import { fetchJson } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}

type ZoneDashboard = {
  zones: { 区域名称?: string }[]
  boundary_alarms: unknown[]
}

const store = useSessionStore()
const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])
const scopeZones = ref<string[]>([])
const boundaryCount = ref(0)

async function loadScope() {
  try {
    const payload = await fetchJson<ZoneDashboard>(`/api/zone/dashboard?role=${encodeURIComponent(store.role)}`)
    scopeZones.value = payload.zones.map((zone) => zone.区域名称 ?? '').filter(Boolean)
    boundaryCount.value = payload.boundary_alarms.length
  } catch {
    scopeZones.value = []
    boundaryCount.value = 0
  }
}

async function loadOverview() {
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
  } catch {
    cards.value = [{"label": "业务模块", "value": 0}, {"label": "今日新增", "value": 0}]
    moduleRows.value = [{"name": "光伏电站", "created": 0, "pending": 0, "abnormal": 0}, {"name": "光伏方阵", "created": 0, "pending": 0, "abnormal": 0}, {"name": "逆变器管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "汇流箱管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "组串监测", "created": 0, "pending": 0, "abnormal": 0}, {"name": "辐照监测", "created": 0, "pending": 0, "abnormal": 0}, {"name": "组件清洗", "created": 0, "pending": 0, "abnormal": 0}, {"name": "巡检任务", "created": 0, "pending": 0, "abnormal": 0}, {"name": "缺陷登记", "created": 0, "pending": 0, "abnormal": 0}, {"name": "消缺处理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "备件领用", "created": 0, "pending": 0, "abnormal": 0}, {"name": "发电量核算", "created": 0, "pending": 0, "abnormal": 0}, {"name": "限电记录", "created": 0, "pending": 0, "abnormal": 0}, {"name": "告警中心", "created": 0, "pending": 0, "abnormal": 0}, {"name": "作业许可", "created": 0, "pending": 0, "abnormal": 0}, {"name": "安全区域", "created": 0, "pending": 0, "abnormal": 0}, {"name": "运维承包商", "created": 0, "pending": 0, "abnormal": 0}, {"name": "培训考核", "created": 0, "pending": 0, "abnormal": 0}, {"name": "电量结算", "created": 0, "pending": 0, "abnormal": 0}]
  }
}

watch(() => store.role, loadScope)
onMounted(() => {
  void loadOverview()
  void loadScope()
})
</script>
