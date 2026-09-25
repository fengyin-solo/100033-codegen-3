/** 统一请求封装：拼后端地址、带上当前登录角色、抛网络错误、给页脚留一句可读的说明。 */
const API_BASE = import.meta.env.VITE_API_BASE ?? ''

const ROLE_STORAGE_KEY = 'ops-role'

export function currentRole(): string {
  return localStorage.getItem(ROLE_STORAGE_KEY) ?? 'duty_admin'
}

export function setCurrentRole(role: string) {
  localStorage.setItem(ROLE_STORAGE_KEY, role)
  window.dispatchEvent(new CustomEvent('role-changed', { detail: role }))
}

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  const headers = new Headers(init?.headers)
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  // 后端按 X-Operator-Role 判定授权区域，老接口也兼容这个头
  headers.set('X-Operator-Role', currentRole())
  return fetch(url, { ...init, headers }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : '请求未送达'
    throw new Error(`接口请求失败：${detail}`)
  })
}

/** 从失败响应里取后端给出的拒绝原因（detail 或 message）。 */
export async function responseError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string; message?: string }
    return payload.detail || payload.message || fallback
  } catch {
    return fallback
  }
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) {
    throw new Error(await responseError(response, `接口返回 ${response.status}，数据未更新`))
  }
  return (await response.json()) as T
}
