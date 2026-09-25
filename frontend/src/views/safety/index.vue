<template>
  <section class="page" data-module="safety">
    <header class="page-head">
      <div>
        <h2>安全区域管控</h2>
        <p class="page-desc">
          按作业地点圈定电子围栏并给角色分配授权区域；许可列表与告警看板只展示授权区域内数据，
          同区生效许可按优先级只放行一条，越界告警单独标出并提醒值班人。
        </p>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value" :class="{ 'error-text': card.label.includes('越界') && card.value > 0 }">
          {{ card.value }}
        </strong>
      </article>
    </div>

    <!-- 电子围栏 -->
    <section class="panel">
      <h3>电子围栏（按作业地点圈定）</h3>
      <p class="sub">
        边界坐标按 [[x,y],...] 维护，形成封闭多边形；当前角色：{{ identity?.角色名称 }}，
        {{ canEditZone ? '可划定/调整边界' : '只能查看，无权改动边界' }}
      </p>
      <table class="data-table">
        <thead>
          <tr>
            <th>区域编码</th><th>区域名称</th><th>作业地点</th><th>授权角色</th>
            <th>生效许可</th><th>待提醒越界</th><th>围栏状态</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="zone in zones" :key="zone.id">
            <td>{{ zone.区域编码 }}</td>
            <td>{{ zone.区域名称 }}</td>
            <td>{{ zone.作业地点 }}</td>
            <td>
              <span v-for="role in zone.授权角色" :key="role.角色编码" class="tag tag-muted" style="margin-right:4px">
                {{ role.角色名称 }}
              </span>
              <span v-if="!zone.授权角色.length">—</span>
            </td>
            <td>{{ zone.生效许可数 }}</td>
            <td>
              <span :class="zone.待提醒越界数 > 0 ? 'tag tag-boundary' : ''">
                {{ zone.待提醒越界数 }}
              </span>
            </td>
            <td>{{ zone.围栏状态 }}</td>
            <td class="row-actions">
              <button v-if="canEditZone" class="link" type="button" @click="editZone(zone)">调整边界</button>
              <span v-else class="inline-tip">只读</span>
            </td>
          </tr>
        </tbody>
      </table>

      <form v-if="canEditZone" class="form-grid" style="margin-top:12px" @submit.prevent="saveZone">
        <label><span>区域编码</span><input v-model="zoneForm.区域编码" placeholder="如 ZONE-D" /></label>
        <label><span>区域名称</span><input v-model="zoneForm.区域名称" /></label>
        <label><span>作业地点</span><input v-model="zoneForm.作业地点" /></label>
        <label>
          <span>围栏状态</span>
          <select v-model="zoneForm.围栏状态"><option>启用</option><option>停用</option></select>
        </label>
        <label style="flex:1;min-width:260px">
          <span>边界坐标 [[x,y],...]</span>
          <input v-model="zoneForm.边界坐标" style="width:100%" placeholder="[[0,0],[0,100],[80,100],[80,0]]" />
        </label>
        <label style="min-width:200px"><span>备注</span><input v-model="zoneForm.备注" /></label>
        <button class="btn primary" type="submit">{{ zoneForm.id ? '保存边界调整' : '划定围栏' }}</button>
        <button v-if="zoneForm.id" class="btn ghost" type="button" @click="resetZoneForm">取消编辑</button>
      </form>
    </section>

    <!-- 角色授权（仅值班管理员） -->
    <section v-if="canEditGrant" class="panel">
      <h3>角色授权区域分配</h3>
      <p class="sub">被授权角色只能查看本区域内的作业许可与告警看板；同一角色重复授权会被拒绝。</p>
      <form class="form-grid" @submit.prevent="saveGrant">
        <label>
          <span>角色</span>
          <select v-model="grantForm.角色编码">
            <option v-for="role in roleOptions.filter(r => r.角色编码 !== 'duty_admin')" :key="role.角色编码" :value="role.角色编码">
              {{ role.角色名称 }}
            </option>
          </select>
        </label>
        <label>
          <span>安全区域</span>
          <select v-model="grantForm.安全区域ID">
            <option v-for="zone in zones" :key="zone.id" :value="zone.id">{{ zone.区域名称 }}</option>
          </select>
        </label>
        <button class="btn primary" type="submit">分配授权</button>
      </form>
      <table class="data-table" style="margin-top:10px">
        <thead><tr><th>角色</th><th>授权区域</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="grant in grants" :key="grant.id">
            <td>{{ grant.角色名称 }}</td>
            <td>{{ grant.安全区域名称 }}</td>
            <td class="row-actions">
              <button class="link" type="button" @click="revokeGrant(grant.id)">收回授权</button>
            </td>
          </tr>
          <tr v-if="!grants.length"><td colspan="3" class="empty-state">暂无授权记录</td></tr>
        </tbody>
      </table>
    </section>

    <!-- 越界告警（独立看板） -->
    <section class="panel">
      <h3>越界告警看板 <span class="tag tag-boundary" style="margin-left:6px">单独标出 · 提醒值班人</span></h3>
      <p class="sub">越界告警不进入普通告警列表；此处按当前角色授权区域过滤。</p>

      <form class="form-grid" @submit.prevent="reportPosition">
        <label>
          <span>作业区域</span>
          <select v-model="reportForm.安全区域ID">
            <option v-for="zone in zones" :key="zone.id" :value="zone.id">{{ zone.区域名称 }}</option>
          </select>
        </label>
        <label><span>人员</span><input v-model="reportForm.越界人员" placeholder="外委检修-姓名" /></label>
        <label><span>定位坐标 x,y</span><input v-model="reportForm.coord" placeholder="150,50" /></label>
        <button class="btn" type="submit">上报定位</button>
      </form>

      <table class="data-table" style="margin-top:10px">
        <thead>
          <tr><th>越界编号</th><th>分类</th><th>安全区域</th><th>越界人员</th><th>定位坐标</th>
          <th>越界时间</th><th>状态</th><th>提醒对象</th><th>处置说明</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="alarm in boundaryAlarms" :key="alarm.id" :class="{ 'boundary-row': alarm.状态 === '待提醒' }">
            <td>{{ alarm.越界编号 }}</td>
            <td><span class="tag tag-boundary">越界告警</span></td>
            <td>{{ alarm.安全区域名称 }}</td>
            <td>{{ alarm.越界人员 }}</td>
            <td>{{ alarm.定位坐标 }}</td>
            <td>{{ alarm.越界时间 }}</td>
            <td>
              <span :class="alarm.状态 === '待提醒' ? 'tag tag-boundary' : alarm.状态 === '已提醒' ? 'tag tag-warn' : 'tag tag-pass'">
                {{ alarm.状态 }}
              </span>
            </td>
            <td>{{ alarm.提醒值班人 }}</td>
            <td>{{ alarm.处置说明 || '—' }}</td>
            <td class="row-actions">
              <template v-if="canAckBoundary">
                <input v-model="ackNotes[alarm.id]" placeholder="处置说明（可选）" style="min-width:140px" />
                <button class="link" type="button" @click="ackBoundary(alarm.id)">处置完成</button>
              </template>
              <span v-else class="inline-tip">只读</span>
            </td>
          </tr>
          <tr v-if="!boundaryAlarms.length">
            <td colspan="10" class="empty-state">授权区域内暂无越界告警</td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- 放行/只读许可一览 -->
    <section class="panel">
      <h3>同区域许可优先级放行</h3>
      <p class="sub">同一片安全区域内多条许可同时生效时，只放行优先级最高的一条，其余只读排队。</p>
      <table class="data-table">
        <thead><tr><th>许可编号</th><th>安全区域</th><th>优先级</th><th>放行状态</th><th>只读原因</th></tr></thead>
        <tbody>
          <tr v-for="permit in releasedPermits" :key="`r-${permit.id}`">
            <td>{{ permit.许可编号 }}</td><td>{{ permit.作业地点 }}</td><td>{{ permit.优先级 }}</td>
            <td><span class="tag tag-pass">放行</span></td><td>—</td>
          </tr>
          <tr v-for="permit in readonlyPermits" :key="`ro-${permit.id}`">
            <td>{{ permit.许可编号 }}</td><td>{{ permit.作业地点 }}</td><td>{{ permit.优先级 }}</td>
            <td><span class="tag tag-readonly">只读</span></td><td>{{ permit.只读原因 }}</td>
          </tr>
          <tr v-if="!releasedPermits.length && !readonlyPermits.length">
            <td colspan="5" class="empty-state">当前无同时生效的许可</td>
          </tr>
        </tbody>
      </table>
    </section>

    <footer class="page-foot">
      <span>授权范围与角色保持一致：{{ identity?.授权范围 }}</span>
      <span v-if="message" :class="messageOk ? '' : 'error-text'">{{ message }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request, responseError } from '@/api/client'
import { useSessionStore, type Identity } from '@/stores/session'

const store = useSessionStore()
const identity = computed(() => store.identity)
const canEditZone = computed(() => store.can('zone_edit'))
const canEditGrant = computed(() => store.can('grant_edit'))
const canAckBoundary = computed(() => store.can('alarm_action'))

type Zone = {
  id: number
  区域编码: string
  区域名称: string
  作业地点: string
  边界坐标: string
  围栏状态: string
  备注: string
  授权角色: { 角色编码: string; 角色名称: string }[]
  生效许可数: number
  待提醒越界数: number
}
type Grant = { id: number; 角色编码: string; 角色名称: string; 安全区域ID: number; 安全区域名称: string }
type BoundaryAlarm = {
  id: number
  越界编号: string
  安全区域名称: string
  越界人员: string
  定位坐标: string
  越界时间: string
  状态: string
  提醒值班人: string
  处置说明: string
}
type Permit = { id: number; 许可编号: string; 作业地点: string; 优先级: number; 只读原因?: string }

const cards = ref<{ label: string; value: number }[]>([])
const zones = ref<Zone[]>([])
const grants = ref<Grant[]>([])
const boundaryAlarms = ref<BoundaryAlarm[]>([])
const releasedPermits = ref<Permit[]>([])
const readonlyPermits = ref<Permit[]>([])
const roleOptions = ref<{ 角色编码: string; 角色名称: string }[]>([])
const ackNotes = reactive<Record<number, string>>({})
const message = ref('')
const messageOk = ref(true)

const emptyZoneForm = () => ({
  id: null as number | null,
  区域编码: '',
  区域名称: '',
  作业地点: '',
  边界坐标: '',
  围栏状态: '启用',
  备注: '',
})
const zoneForm = ref(emptyZoneForm())
const grantForm = reactive({ 角色编码: 'contractor_lead', 安全区域ID: 1 })
const reportForm = reactive({ 安全区域ID: 1, 越界人员: '', coord: '' })

function flash(text: string, ok = true) {
  message.value = text
  messageOk.value = ok
}

async function postJson(path: string, body: unknown, fallback: string) {
  const response = await request(path, { method: 'POST', body: JSON.stringify(body) })
  const payload = (await response.json()) as { ok: boolean; message: string }
  if (!response.ok || !payload.ok) {
    throw new Error(response.ok ? payload.message || fallback : await responseError(response, fallback))
  }
  return payload.message
}

async function loadDashboard() {
  const response = await request('/api/safety/dashboard')
  const payload = await response.json()
  cards.value = payload.cards
  zones.value = payload.zones
  releasedPermits.value = payload.released_permits
  readonlyPermits.value = payload.readonly_permits
  boundaryAlarms.value = payload.boundary_alarms
}

async function loadGrants() {
  if (!canEditGrant.value) return
  const response = await request('/api/safety/grants')
  grants.value = (await response.json()).items
}

async function loadRoles() {
  const response = await request('/api/safety/roles')
  roleOptions.value = (await response.json()).roles
}

function editZone(zone: Zone) {
  zoneForm.value = {
    id: zone.id,
    区域编码: zone.区域编码,
    区域名称: zone.区域名称,
    作业地点: zone.作业地点,
    边界坐标: zone.边界坐标,
    围栏状态: zone.围栏状态,
    备注: zone.备注,
  }
}

function resetZoneForm() {
  zoneForm.value = emptyZoneForm()
}

async function saveZone() {
  try {
    const text = await postJson('/api/safety/zones', { values: zoneForm.value }, '围栏保存失败')
    flash(text)
    resetZoneForm()
    await loadDashboard()
  } catch (error) {
    flash(error instanceof Error ? error.message : '围栏保存失败', false)
  }
}

async function saveGrant() {
  try {
    const text = await postJson('/api/safety/grants', { values: { ...grantForm } }, '授权失败')
    flash(text)
    await loadGrants()
  } catch (error) {
    flash(error instanceof Error ? error.message : '授权失败', false)
  }
}

async function revokeGrant(grantId: number) {
  const response = await request(`/api/safety/grants/${grantId}`, { method: 'DELETE' })
  const payload = await response.json()
  flash(response.ok && payload.ok ? payload.message : payload.detail || '收回授权失败', response.ok && payload.ok)
  if (response.ok && payload.ok) await loadGrants()
}

async function reportPosition() {
  const parts = reportForm.coord.split(',').map((v) => Number(v.trim()))
  if (parts.length !== 2 || parts.some(Number.isNaN)) {
    flash('定位坐标需要填写为 x,y 两个数字', false)
    return
  }
  try {
    const text = await postJson(
      '/api/safety/boundary-alarms/report',
      { values: { 安全区域ID: reportForm.安全区域ID, 越界人员: reportForm.越界人员, 定位坐标: parts } },
      '定位上报失败',
    )
    flash(text)
    reportForm.coord = ''
    await loadDashboard()
  } catch (error) {
    flash(error instanceof Error ? error.message : '定位上报失败', false)
  }
}

async function ackBoundary(alarmId: number) {
  try {
    const text = await postJson(
      `/api/safety/boundary-alarms/${alarmId}/ack`,
      { values: { note: ackNotes[alarmId] || '' } },
      '处置失败',
    )
    ackNotes[alarmId] = ''
    flash(text)
    await loadDashboard()
  } catch (error) {
    flash(error instanceof Error ? error.message : '处置失败', false)
  }
}

onMounted(async () => {
  await loadRoles()
  await loadDashboard()
  await loadGrants()
})
</script>

<style scoped>
.boundary-row { background: #fff5f4; }
</style>
