const BASE = '/api'

// Codes that indicate the token is hard-invalid (not recoverable by refresh)
const TOKEN_HARD_FAIL_CODES = new Set([2008, 2009, 2011])
// Code that means the access token expired (recoverable)
const TOKEN_EXPIRED_CODE = 2010

let _redirecting = false

function handleAuthError() {
  if (_redirecting) return
  _redirecting = true
  localStorage.removeItem('token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('username')
  setTimeout(() => { window.location.href = '/login'; _redirecting = false }, 0)
}

export function getToken()        { return localStorage.getItem('token') ?? '' }
export function getRefreshToken() { return localStorage.getItem('refresh_token') ?? '' }

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

  // Hard-invalid token → logout immediately
  if (TOKEN_HARD_FAIL_CODES.has(json.code)) { handleAuthError(); throw new Error('_auth_redirect') }

  // Expired token → attempt silent refresh once
  if (json.code === TOKEN_EXPIRED_CODE && !_isRetry) {
    try {
      const tokens = await _refreshTokenRaw()
      localStorage.setItem('token', tokens.access_token)
      localStorage.setItem('refresh_token', tokens.refresh_token)
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

async function upload<T>(path: string, form: FormData, _isRetry = false): Promise<T> {
  const t = getToken()
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: t ? { Authorization: `Bearer ${t}` } : {},
    body: form,
  })
  const json = await res.json()
  if (TOKEN_HARD_FAIL_CODES.has(json.code)) { handleAuthError(); throw new Error('_auth_redirect') }
  if (json.code === TOKEN_EXPIRED_CODE && !_isRetry) {
    try {
      const tokens = await _refreshTokenRaw()
      localStorage.setItem('token', tokens.access_token)
      localStorage.setItem('refresh_token', tokens.refresh_token)
      return await upload<T>(path, form, true)
    } catch {
      handleAuthError()
      throw new Error('_auth_redirect')
    }
  }
  if (json.code !== 200 && json.code !== 201) throw new Error(json.message ?? '上传失败')
  return json.data as T
}

const get    = <T>(p: string)               => request<T>('GET',    p)
const post   = <T>(p: string, b?: unknown)  => request<T>('POST',   p, b)
const put    = <T>(p: string, b?: unknown)  => request<T>('PUT',    p, b)
const patch  = <T>(p: string, b?: unknown)  => request<T>('PATCH',  p, b)
const del    = <T>(p: string)               => request<T>('DELETE', p)

// ── Auth ──────────────────────────────────────────────────────────────────
export interface TokenResponse { username: string; access_token: string; refresh_token: string }
export interface UserInfo {
  id: number; username: string; email: string | null; is_email_verified: boolean
  role: string; is_active: boolean; created_at: string; updated_at: string
}

export const sendEmailCode = (email: string, purpose: 'register' | 'reset_password' | 'bind_email') =>
  post<null>('/users/send-email-code', { email, purpose })

export const login    = (username: string, password: string) =>
  post<TokenResponse>('/users/login', { username, password })

export const logout   = (_token: string) => post<null>('/users/logout')
export const getMe    = () => get<UserInfo>('/users/me')

export const register = (username: string, password: string, email: string, code: string) =>
  post<null>('/users/register', { username, password, email, code })

export const forgotPassword = (email: string, code: string, new_password: string) =>
  post<null>('/users/forgot-password', { email, code, new_password })

export const changePassword = (old_password: string, new_password: string) =>
  put<null>('/users/me/password', { old_password, new_password })

export const updateEmail = (new_email: string, code: string, password: string) =>
  put<null>('/users/me/email', { new_email, code, password })

export const deleteAccount = () => del<null>('/users')

// ── Sessions ──────────────────────────────────────────────────────────────
export type SessionStage =
  | 'requirement_collection' | 'outline_generation' | 'outline_confirming'
  | 'content_generation' | 'content_confirming' | 'completed'
export type SessionType = 'guided' | 'report_driven'

export interface SessionSummary {
  id: number; title: string; session_type: SessionType; stage: SessionStage
  requirements_complete: boolean; rag_enabled: boolean; deep_search_enabled: boolean
  message_count: number; created_at: string; updated_at: string
}
export interface SessionDetail {
  id: number; user_id: number; title: string; session_type: SessionType
  stage: SessionStage; requirements: Record<string, unknown>
  requirements_complete: boolean; rag_enabled: boolean; deep_search_enabled: boolean
  message_count: number; current_user_llm_config_id: number | null
  created_at: string; updated_at: string
}
export interface SessionList { items: SessionSummary[]; total: number; page: number; page_size: number }
export interface StartSessionResp {
  session_id: number; message_id: number; seq_no: number
  task_id: number | null; reply: string | null; streaming: boolean
}
export interface SendMessageResp {
  session_id: number; message_id: number; seq_no: number
  task_id: number | null; reply: string | null; streaming: boolean
}

export const listSessions = (page = 1, page_size = 30) =>
  get<SessionList>(`/sessions?page=${page}&page_size=${page_size}`)
export const getSession = (id: number) => get<SessionDetail>(`/sessions/${id}`)
export const deleteSession = (id: number) => del<null>(`/sessions/${id}`)
export const updateSessionSettings = (id: number, data: {
  llm_config_id?: number | null; rag_enabled?: boolean; deep_search_enabled?: boolean
}) => patch<SessionDetail>(`/sessions/${id}/settings`, data)

export async function startSession(opts: {
  content: string; title?: string; llm_config_id?: number | null
  report_file?: File | null; rag_enabled?: boolean; deep_search_enabled?: boolean
}): Promise<StartSessionResp> {
  const form = new FormData()
  form.append('content', opts.content)
  if (opts.title) form.append('title', opts.title)
  if (opts.llm_config_id != null) form.append('llm_config_id', String(opts.llm_config_id))
  if (opts.report_file) form.append('report_file', opts.report_file)
  form.append('rag_enabled', String(opts.rag_enabled ?? false))
  form.append('deep_search_enabled', String(opts.deep_search_enabled ?? false))
  return upload<StartSessionResp>('/sessions/start', form)
}
export const sendMessage = (session_id: number, content: string) =>
  post<SendMessageResp>(`/sessions/${session_id}/messages`, { content })

// ── Messages ──────────────────────────────────────────────────────────────
export type MessageRole = 'user' | 'assistant' | 'system'
export interface Message {
  id: number; session_id: number; role: MessageRole; seq_no: number
  content: string | null; outline_json: Record<string, unknown> | null
  slide_json: Record<string, unknown> | null; created_at: string
}
export const listMessages = (session_id: number) =>
  get<Message[]>(`/sessions/${session_id}/messages`)

// ── Outline ───────────────────────────────────────────────────────────────
export interface Outline {
  id: number; session_id: number; version: number; outline_json: Record<string, unknown>
  confirmed_at: string | null; created_at: string
}
export const getOutline = (session_id: number) => get<Outline>(`/sessions/${session_id}/outline`)
export const updateOutline = (session_id: number, outline_json: Record<string, unknown>) =>
  put<Outline>(`/sessions/${session_id}/outline`, { outline_json })
export const confirmOutline = (session_id: number) =>
  post<SendMessageResp>(`/sessions/${session_id}/outline/confirm`)

// ── Slides ────────────────────────────────────────────────────────────────
export interface Slide {
  id: number; session_id: number; version: number; content: Record<string, unknown>
  confirmed_at: string | null; created_at: string
}
export const getSlides = (session_id: number) => get<Slide>(`/sessions/${session_id}/slides`)

// ── Tasks ─────────────────────────────────────────────────────────────────
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
export interface TaskStatusResp { id: number; status: TaskStatus; progress: number | null; error: string | null }
export const getTaskStatus = (task_id: number) =>
  get<TaskStatusResp>(`/tasks/${task_id}/status`)
export interface ActiveTaskResp { id: number; status: TaskStatus; type: string }
export const getActiveTask = (session_id: number) =>
  get<ActiveTaskResp | null>(`/tasks/sessions/${session_id}/active`)

// ── Knowledge ─────────────────────────────────────────────────────────────
export type DocStatus = 'pending' | 'processing' | 'ready' | 'failed'
export interface KnowledgeFile {
  id: number; category: string; file_name: string; file_type: string
  size_bytes: number; status: DocStatus; error_message: string | null
  created_at: string; updated_at: string
}
export interface KnowledgeRef {
  id: number; session_id: number; knowledge_file_id: number
  knowledge_file: KnowledgeFile; created_at: string
}

export const listKnowledge = () => get<KnowledgeFile[]>('/knowledge')
export const getKnowledge  = (id: number) => get<KnowledgeFile>(`/knowledge/${id}`)
export const deleteKnowledge = (id: number) => del<null>(`/knowledge/${id}`)
export const retryKnowledge      = (id: number) => post<KnowledgeFile>(`/knowledge/${id}/retry`)
export const updateFileCategory  = (id: number, category: string) =>
  patch<KnowledgeFile>(`/knowledge/${id}/category`, { category })
export async function uploadKnowledge(file: File, category = 'default'): Promise<KnowledgeFile> {
  const form = new FormData()
  form.append('file', file)
  form.append('category', category)
  return upload<KnowledgeFile>('/knowledge', form)
}

export const listSessionRefs = (session_id: number) =>
  get<KnowledgeRef[]>(`/knowledge/sessions/${session_id}/refs`)
export const addSessionRefs  = (session_id: number, knowledge_file_ids: number[]) =>
  post<{ added_count: number; message: string }>(`/knowledge/sessions/${session_id}/refs`, { knowledge_file_ids })
export const removeSessionRef = (session_id: number, knowledge_file_id: number) =>
  del<null>(`/knowledge/sessions/${session_id}/refs/${knowledge_file_id}`)

// ── Model configs ─────────────────────────────────────────────────────────
export interface UserLLMConfig {
  id: number; provider_model_id: number; provider_name: string; model_name: string
  alias: string | null; is_default: boolean; is_active: boolean
  created_at: string; updated_at: string
}
export interface AvailableModel { id: number; model_name: string; description: string | null }
export interface AvailableProvider {
  id: number; name: string; description: string | null
  models: AvailableModel[]
}
export interface UserRagConfig { id: number; base_url: string; model: string; created_at: string; updated_at: string }
export interface UserSearchConfig { id: number; provider: string; created_at: string; updated_at: string }
export interface UserDefaults {
  default_llm_config: UserLLMConfig | null
  search_config: UserSearchConfig | null
  rag_enabled: boolean; deep_search_enabled: boolean
}

export const getUserDefaults = () => get<UserDefaults>('/model/defaults')
export const listAvailableProviders = () => get<AvailableProvider[]>('/model/providers')

export const listUserLLMConfigs = () => get<UserLLMConfig[]>('/model/configs/llm')
export const createUserLLMConfig = (provider_model_id: number, api_key: string, alias: string | null, is_default: boolean) =>
  post<UserLLMConfig>('/model/configs/llm', { provider_model_id, api_key, alias, is_default })
export const updateUserLLMConfig = (config_id: number, data: { api_key?: string; alias?: string | null; is_default?: boolean }) =>
  put<UserLLMConfig>(`/model/configs/llm/${config_id}`, data)
export const deleteUserLLMConfig = (config_id: number) => del<null>(`/model/configs/llm/${config_id}`)
export const setDefaultLLMConfig = (config_id: number) => put<null>(`/model/configs/llm/${config_id}/default`)

export const getUserRagConfig = () => get<UserRagConfig | null>('/model/configs/rag')
export const createUserRagConfig = (api_key: string) => post<UserRagConfig>('/model/configs/rag', { api_key })
export const updateUserRagConfig = (api_key: string) => put<UserRagConfig>('/model/configs/rag', { api_key })
export const deleteUserRagConfig = () => del<null>('/model/configs/rag')

export const getUserSearchConfig = () => get<UserSearchConfig | null>('/model/configs/search')
export const createUserSearchConfig = (api_key: string) => post<UserSearchConfig>('/model/configs/search', { api_key })
export const updateUserSearchConfig = (api_key: string) => put<UserSearchConfig>('/model/configs/search', { api_key })
export const deleteUserSearchConfig = () => del<null>('/model/configs/search')
