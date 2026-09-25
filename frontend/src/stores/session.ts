import { defineStore } from 'pinia'

import { currentRole, setCurrentRole } from '@/api/client'

type Permission =
  | 'zone_view_all'
  | 'zone_edit'
  | 'grant_edit'
  | 'permit_action'
  | 'alarm_action'

export type Identity = {
  角色编码: string
  角色名称: string
  授权范围: string
  permissions: Record<Permission, boolean>
}

export const useSessionStore = defineStore('session', {
  state: () => ({
    operator: '值班管理员',
    shiftLabel: '白班 08:00-20:00',
    scope: '全站安全区域',
    roleCode: currentRole(),
    identity: null as Identity | null,
  }),
  getters: {
    canOperate: (state) => state.operator.length > 0,
    can: (state) => (permission: Permission) => state.identity?.permissions[permission] ?? false,
  },
  actions: {
    setShift(label: string) {
      this.shiftLabel = label
    },
    setRole(roleCode: string) {
      setCurrentRole(roleCode)
      this.roleCode = roleCode
    },
    setIdentity(identity: Identity) {
      this.identity = identity
      this.operator = identity.角色名称
      this.scope = identity.授权范围
    },
  },
})
