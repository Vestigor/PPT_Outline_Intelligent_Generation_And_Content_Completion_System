const BASE = '/api'

const TOKEN_HARD_FAIL_CODES = new Set([2008, 2009, 2011])
const TOKEN_EXPIRED_CODE = 2010

let _redirecting = false

function handleAuthError() {
  if (_redirecting) return
  _redirecting = true
  localStorage.removeItem('admin_token')
  localStorage.removeItem('admin_refresh_token')
  localStorage.removeItem('admin_username')
  localStorage.removeItem('admin_role')
  setTimeout(() => { window.location.href = '/login'; _redirecting = false }, 0)
}

function getToken()        { return localStorage.getItem('admin_token') ?? '' }
function getRefreshToken() { return localStorage.getItem('admin_refresh_token') ?? '' }

async function _refreshTokenRaw(): Promise<{ access_token: string; refresh_token: string }> {
  const rt = getRefreshToken()
  if (!rt) throw new Error('no_refresh_token')
  const res = await fetch(`${BASE}/users/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: rt }),
  })
  const json = await res.json()
  if (json.code !== 200) throw new Error('refresh_failed')
  return json.data
}

async function request<T>(
  method: string, path: string, body?: unknown, _isRetry = false,
): Promise<T> {
  const t = getToken()
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(t ? { Authorization: `Bearer ${t}` } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  const json = await res.json()

  if (TOKEN_HARD_FAIL_CODES.has(json.code)) { handleAuthError(); throw new Error('_auth_redirect') }

  if (json.code === TOKEN_EXPIRED_CODE && !_isRetry) {
    try {
      const tokens = await _refreshTokenRaw()
      localStorage.setItem('admin_token', tokens.access_token)
      localStorage.setItem('admin_refresh_token', tokens.refresh_token)
      return await request<T>(method, path, body, true)
    } catch {
      handleAuthError()
      throw new Error('_auth_redirect')
    }
  }

  if (json.code === TOKEN_EXPIRED_CODE && _isRetry) {
    handleAuthError()
    throw new Error('_auth_redirect')
  }

  if (json.code !== 200 && json.code !== 201) throw new Error(json.message ?? '请求失败')
  return json.data as T
}

const get  = <T>(path: string)              => request<T>('GET',    path)
const post = <T>(path: string, b?: unknown) => request<T>('POST',   path, b)
const put  = <T>(path: string, b?: unknown) => request<T>('PUT',    path, b)
const del  = <T>(path: string)              => request<T>('DELETE', path)

// ── Auth ──────────────────────────────────────────────────────────────
export interface TokenResponse {
  username: string
  access_token: string
  refresh_token: string
}
export const login = (username: string, password: string) =>
  post<TokenResponse>('/users/login', { username, password })
export const sendEmailCode = (email: string, purpose: 'register' | 'reset_password' | 'bind_email') =>
  post<null>('/users/send-email-code', { email, purpose })
export const forgotPassword = (email: string, code: string, new_password: string) =>
  post<null>('/users/forgot-password', { email, code, new_password })
export const updateEmail = (new_email: string, code: string, password: string) =>
  put<null>('/users/me/email', { new_email, code, password })

// ── Users ─────────────────────────────────────────────────────────────
export interface UserResponse {
  id: number
  username: string
  email: string | null
  is_email_verified: boolean
  role: 'super_admin' | 'admin' | 'user'
  is_active: boolean
  created_at: string
  updated_at: string
}
export interface PageResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}
export const listUsers = (page = 1, page_size = 20, username?: string) => {
  const q = new URLSearchParams({ page: String(page), page_size: String(page_size) })
  if (username) q.set('username', username)
  return get<PageResult<UserResponse>>(`/users/admin/users?${q}`)
}
export const createUser = (username: string, password: string, role: string) =>
  post<null>('/users/admin/create_user', { username, password, role })
export const deleteUser = (id: number) => del<null>(`/users/admin/delete_user/${id}`)
export const toggleUserStatus = (id: number) => put<null>(`/users/admin/users/status/${id}`)
export const resetPassword = (user_id: number, new_password: string) =>
  post<null>('/users/admin/change_password', { user_id, new_password })
export const getMe = () => get<UserResponse>('/users/me')
export const changePassword = (old_password: string, new_password: string) =>
  put<null>('/users/me/password', { old_password, new_password })

// ── Providers ─────────────────────────────────────────────────────────
export interface LLMModel {
  id: number
  provider_id: number
  model_name: string
  description: string | null
  is_active: boolean
  effective_is_active: boolean
  created_at: string
  updated_at: string
}
export interface LLMProvider {
  id: number
  name: string
  base_url: string
  description: string | null
  is_active: boolean
  models: LLMModel[]
  created_at: string
  updated_at: string
}
export const listProviders = () => get<LLMProvider[]>('/model/admin/providers')
export const createProvider = (
  name: string, base_url: string,
  description: string | null, is_active: boolean,
) => post<LLMProvider>('/model/admin/providers', { name, base_url, description, is_active })
export const updateProvider = (
  id: number,
  data: Partial<{ name: string; base_url: string; description: string; is_active: boolean }>,
) => put<LLMProvider>(`/model/admin/providers/${id}`, data)
export const deleteProvider = (id: number) => del<null>(`/model/admin/providers/${id}`)

export const createModel = (
  provider_id: number, model_name: string,
  description: string | null, is_active: boolean,
) => post<LLMModel>(`/model/admin/providers/${provider_id}/models`, { model_name, description, is_active })
export const updateModel = (
  provider_id: number, model_id: number,
  data: Partial<{ model_name: string; description: string; is_active: boolean }>,
) => put<LLMModel>(`/model/admin/providers/${provider_id}/models/${model_id}`, data)
export const deleteModel = (provider_id: number, model_id: number) =>
  del<null>(`/model/admin/providers/${provider_id}/models/${model_id}`)
