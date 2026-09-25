import { defineStore } from 'pinia'

export const useSessionStore = defineStore('session', {
  state: () => ({
    operator: '值班管理员',
    role: '值班管理员',
    roles: ['值班管理员', '值班人', '维护人员', '外委负责人'],
    shiftLabel: '白班 08:00-20:00',
    scope: '光伏电站智能运维平台',
  }),
  getters: {
    canOperate: (state) => state.operator.length > 0,
  },
  actions: {
    setShift(label: string) {
      this.shiftLabel = label
    },
    setRole(role: string) {
      this.role = role
    },
  },
})
