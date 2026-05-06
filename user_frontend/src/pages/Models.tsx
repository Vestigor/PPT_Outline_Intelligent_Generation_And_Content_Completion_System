import { useState, useEffect, useCallback, useMemo, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  MessageSquare, Database, Cpu, LogOut, Plus, Trash2, Star,
  KeyRound, ChevronDown, ChevronRight, ChevronUp, Edit2, UserX, Search, Mail,
  Eye, EyeOff,
} from 'lucide-react'
import {
  listUserLLMConfigs, createUserLLMConfig, updateUserLLMConfig,
  deleteUserLLMConfig, setDefaultLLMConfig,
  listAvailableProviders,
  getUserRagConfig, createUserRagConfig, updateUserRagConfig, deleteUserRagConfig,
  getUserSearchConfig, createUserSearchConfig, updateUserSearchConfig, deleteUserSearchConfig,
  logout, getToken, changePassword, deleteAccount, sendEmailCode, updateEmail,
  type UserLLMConfig, type AvailableProvider, type UserRagConfig, type UserSearchConfig,
} from '../api'
import { useToast } from '../hooks/useToast'
import { Modal, Confirm } from '../components/Modal'
import { CascadingPicker, type CPGroup } from '../components/CascadingPicker'

type TabKey = 'llm' | 'rag' | 'search'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'llm',    label: 'LLM 模型' },
  { key: 'rag',    label: '向量检索（RAG）' },
  { key: 'search', label: '联网搜索' },
]

// ── Bind Email Modal ──────────────────────────────────────────────────────
function BindEmailModal({ onClose }: { onClose: () => void }) {
  const { toast }      = useToast()
  const [step,         setStep]      = useState<1 | 2>(1)
  const [pwd,          setPwd]       = useState('')
  const [showPwd,      setShowPwd]   = useState(false)
  const [email,        setEmail]     = useState('')
  const [code,         setCode]      = useState('')
  const [sending,      setSending]   = useState(false)
  const [countdown,    setCountdown] = useState(0)
  const [loading,      setLoading]   = useState(false)

  async function handleSendCode() {
    if (!email) { toast('请输入新邮箱地址', 'error'); return }
    setSending(true)
    try {
      await sendEmailCode(email, 'bind_email')
      toast('验证码已发送，请查收', 'success')
      setCountdown(60)
      const timer = setInterval(() => {
        setCountdown(c => { if (c <= 1) { clearInterval(timer); return 0 } return c - 1 })
      }, 1000)
    } catch (err: any) {
      toast(err.message, 'error')
    } finally {
      setSending(false)
    }
  }

  async function handleSubmit() {
    if (!email || !code) { toast('请填写邮箱和验证码', 'error'); return }
    setLoading(true)
    try {
      await updateEmail(email, code, pwd)
      toast('邮箱绑定成功', 'success')
      onClose()
    } catch (err: any) {
      toast(err.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  if (step === 1) return (
    <Modal title="绑定 / 修改邮箱" onClose={onClose} footer={
      <>
        <button className="btn btn-ghost" onClick={onClose}>取消</button>
        <button className="btn btn-primary" disabled={!pwd} onClick={() => setStep(2)}>
          下一步
        </button>
      </>
    }>
      <div className="form-group" style={{ marginBottom: 0 }}>
        <label className="form-label">当前密码（用于验证身份）</label>
        <div style={{ position: 'relative' }}>
          <input className="form-input" type={showPwd ? 'text' : 'password'}
            autoComplete="current-password" placeholder="输入当前登录密码"
            value={pwd} onChange={e => setPwd(e.target.value)}
            style={{ paddingRight: 40 }} autoFocus />
          <button type="button" onClick={() => setShowPwd(p => !p)}
            style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: 0 }}>
            {showPwd ? <EyeOff style={{ width: 15, height: 15 }} /> : <Eye style={{ width: 15, height: 15 }} />}
          </button>
        </div>
      </div>
    </Modal>
  )

  return (
    <Modal title="绑定 / 修改邮箱" onClose={onClose} footer={
      <>
        <button className="btn btn-ghost" onClick={() => setStep(1)} disabled={loading}>上一步</button>
        <button className="btn btn-primary" disabled={loading || !email || !code} onClick={handleSubmit}>
          {loading ? '提交中…' : '确认绑定'}
        </button>
      </>
    }>
      <div className="form-group">
        <label className="form-label">新邮箱地址</label>
        <div style={{ display: 'flex', gap: 8 }}>
          <input className="form-input" type="email" autoComplete="email"
            placeholder="输入新邮箱" value={email}
            onChange={e => setEmail(e.target.value)} autoFocus style={{ flex: 1 }} />
          <button className="btn btn-ghost" type="button"
            disabled={sending || countdown > 0 || !email}
            onClick={handleSendCode}
            style={{ flexShrink: 0, whiteSpace: 'nowrap' }}>
            {sending ? '发送中…' : countdown > 0 ? `${countdown}s` : '发送验证码'}
          </button>
        </div>
      </div>
      <div className="form-group" style={{ marginBottom: 0 }}>
        <label className="form-label">验证码</label>
        <input className="form-input" type="text" placeholder="输入邮件中的 6 位验证码"
          value={code} onChange={e => setCode(e.target.value)} maxLength={6} />
      </div>
    </Modal>
  )
}

// ── Sidebar nav (shared) ──────────────────────────────────────────────────
function SidebarNav() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [showChangePwd,     setShowChangePwd]     = useState(false)
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false)
  const [showDeleteAccount, setShowDeleteAccount] = useState(false)
  const [showBindEmail,     setShowBindEmail]     = useState(false)
  const username = localStorage.getItem('username') ?? ''

  async function doLogout() {
    try { await logout(getToken()) } catch {}
    localStorage.removeItem('token'); localStorage.removeItem('username')
    navigate('/login', { replace: true })
  }

  async function doDeleteAccount() {
    try {
      await deleteAccount()
      localStorage.removeItem('token'); localStorage.removeItem('username')
      navigate('/login', { replace: true })
    } catch (err: any) { toast(err.message, 'error') }
  }

  return (
    <>
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="sidebar-logo-mark"><MessageSquare /></div>
          <div>
            <div className="sidebar-logo-text">PPT 智能生成</div>
            <div className="sidebar-logo-sub">AI 创作助手</div>
          </div>
        </div>

        <nav style={{ flex: 1, padding: '8px 6px' }}>
          <button className="sidebar-nav-item" onClick={() => navigate('/')}>
            <MessageSquare />我的会话
          </button>
          <button className="sidebar-nav-item" onClick={() => navigate('/knowledge')}>
            <Database />知识库
          </button>
          <button className="sidebar-nav-item active">
            <Cpu />模型配置
          </button>
        </nav>

        <div className="sidebar-user-area">
          <div className="sidebar-user-mini">
            <div className="sidebar-user-avatar">{username[0]?.toUpperCase() ?? 'U'}</div>
            <div className="sidebar-user-name">{username}</div>
            <ChevronUp style={{ width: 12, height: 12 }} className="sidebar-user-caret" />
          </div>
          <div className="sidebar-user-popup">
            <div className="sidebar-user-popup-head">
              <div className="sidebar-user-popup-avatar">{username[0]?.toUpperCase() ?? 'U'}</div>
              <div>
                <div className="sidebar-user-popup-name">{username}</div>
                <div className="sidebar-user-popup-role">普通用户</div>
              </div>
            </div>
            <button className="sidebar-user-popup-item" onClick={() => setShowChangePwd(true)}>
              <KeyRound />修改密码
            </button>
            <button className="sidebar-user-popup-item" onClick={() => setShowBindEmail(true)}>
              <Mail />绑定/修改邮箱
            </button>
            <button className="sidebar-user-popup-item danger" onClick={() => setShowLogoutConfirm(true)}>
              <LogOut />退出登录
            </button>
            <button className="sidebar-user-popup-item danger" onClick={() => setShowDeleteAccount(true)}>
              <UserX />注销账户
            </button>
          </div>
        </div>
      </aside>

      {showBindEmail && <BindEmailModal onClose={() => setShowBindEmail(false)} />}
      {showChangePwd && <ChangePwdModal onClose={() => setShowChangePwd(false)} toast={toast} />}
      {showLogoutConfirm && (
        <Confirm title="退出登录" message="确认退出登录？退出后需重新登录才能使用。"
          loading={false} onConfirm={doLogout} onCancel={() => setShowLogoutConfirm(false)} />
      )}
      {showDeleteAccount && (
        <Confirm title="注销账户" message="确认注销账户？此操作不可撤销，账户及所有相关数据将被永久删除。"
          danger loading={false} onConfirm={doDeleteAccount} onCancel={() => setShowDeleteAccount(false)} />
      )}
    </>
  )
}

function ChangePwdModal({ onClose, toast }: { onClose: () => void; toast: (m: string, t?: any) => void }) {
  const [oldPwd, setOldPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (newPwd !== confirm) { toast('两次密码不一致', 'error'); return }
    if (newPwd.length < 6) { toast('新密码至少 6 位', 'error'); return }
    setLoading(true)
    try {
      await changePassword(oldPwd, newPwd)
      toast('密码修改成功', 'success')
      onClose()
    } catch (err: any) { toast(err.message, 'error') }
    finally { setLoading(false) }
  }

  return (
    <Modal title="修改密码" onClose={onClose} footer={
      <>
        <button className="btn btn-ghost" onClick={onClose} disabled={loading}>取消</button>
        <button className="btn btn-primary" onClick={handleSubmit as any}
          disabled={loading || !oldPwd || !newPwd || !confirm}>
          {loading ? '修改中…' : '确认修改'}
        </button>
      </>
    }>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label">当前密码</label>
          <input className="form-input" type="password" placeholder="输入当前密码" value={oldPwd} onChange={e => setOldPwd(e.target.value)} autoFocus />
        </div>
        <div className="form-group">
          <label className="form-label">新密码</label>
          <input className="form-input" type="password" placeholder="至少 6 位" value={newPwd} onChange={e => setNewPwd(e.target.value)} />
        </div>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">确认新密码</label>
          <input className="form-input" type="password" placeholder="再次输入新密码" value={confirm} onChange={e => setConfirm(e.target.value)} />
        </div>
      </form>
    </Modal>
  )
}

// ── Add LLM Config Modal ──────────────────────────────────────────────────
function AddLLMModal({ providers, loading: saving, onClose, onSubmit }: {
  providers: AvailableProvider[]
  loading: boolean
  onClose: () => void
  onSubmit: (provider_model_id: number, api_key: string, alias: string, is_default: boolean) => void
}) {
  const [pickerAnchor,         setPi]   = useState<DOMRect | null>(null)
  const [selectedModelId,      setId]   = useState<number | null>(null)
  const [selectedModelName,    setMN]   = useState('')
  const [selectedProviderName, setPN]   = useState('')
  const [apiKey,    setApiKey]    = useState('')
  const [alias,     setAlias]     = useState('')
  const [isDefault, setIsDefault] = useState(false)

  const pickerGroups: CPGroup[] = providers.map(p => ({
    id: p.id,
    label: p.name,
    count: p.models.length,
    items: p.models.map(m => ({
      id: m.id,
      label: m.model_name,
      sublabel: m.description || undefined,
    })),
  }))

  function pickModel(id: number | null) {
    if (id === null) return
    for (const p of providers) {
      const m = p.models.find(m => m.id === id)
      if (m) { setId(m.id); setMN(m.model_name); setPN(p.name); return }
    }
  }

  return (
    <Modal title="添加 LLM 配置" onClose={onClose} footer={
      <>
        <button className="btn btn-ghost" onClick={onClose} disabled={saving}>取消</button>
        <button className="btn btn-primary"
          disabled={saving || !selectedModelId || !apiKey}
          onClick={() => onSubmit(selectedModelId!, apiKey, alias, isDefault)}>
          {saving ? '添加中…' : '添加配置'}
        </button>
      </>
    }>
      <div className="form-group">
        <label className="form-label">选择模型</label>
        <button type="button" className="form-input"
          style={{
            textAlign: 'left', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            color: selectedModelId ? 'var(--text-1)' : 'var(--text-3)',
            background: pickerAnchor ? 'var(--accent-bg)' : undefined,
            borderColor: pickerAnchor ? 'var(--accent)' : undefined,
          }}
          onClick={e => {
            const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
            setPi(p => p ? null : rect)
          }}
        >
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {selectedModelId ? `${selectedProviderName} · ${selectedModelName}` : '点击选择模型…'}
          </span>
          <ChevronRight style={{
            width: 14, height: 14, flexShrink: 0, color: 'var(--text-3)',
            transition: 'transform 150ms',
            transform: pickerAnchor ? 'rotate(90deg)' : undefined,
          }} />
        </button>
      </div>
      <div className="form-group">
        <label className="form-label">API Key</label>
        <input className="form-input" type="password" placeholder="输入该模型提供商的 API Key"
          value={apiKey} onChange={e => setApiKey(e.target.value)} />
      </div>
      <div className="form-group">
        <label className="form-label">别名（可选）</label>
        <input className="form-input" placeholder="为这个配置取个便于识别的名称"
          value={alias} onChange={e => setAlias(e.target.value)} />
      </div>
      <div className="form-group" style={{ marginBottom: 0 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', userSelect: 'none' }}>
          <input type="checkbox" checked={isDefault} onChange={e => setIsDefault(e.target.checked)}
            style={{ width: 14, height: 14, accentColor: 'var(--accent)' }} />
          <span style={{ fontSize: 13, color: 'var(--text-2)' }}>设为默认配置</span>
        </label>
      </div>

      {pickerAnchor && (
        <CascadingPicker
          anchorRect={pickerAnchor}
          groups={pickerGroups}
          selectedId={selectedModelId}
          direction="right"
          onSelect={pickModel}
          onClose={() => setPi(null)}
        />
      )}
    </Modal>
  )
}

// ── Edit LLM Config Modal ─────────────────────────────────────────────────
function EditLLMModal({ config, loading: saving, onClose, onSubmit }: {
  config: UserLLMConfig; loading: boolean
  onClose: () => void
  onSubmit: (api_key: string, alias: string) => void
}) {
  const [apiKey, setApiKey] = useState('')
  const [alias,  setAlias]  = useState(config.alias ?? '')

  return (
    <Modal title={`编辑配置 · ${config.model_name}`} onClose={onClose} footer={
      <>
        <button className="btn btn-ghost" onClick={onClose} disabled={saving}>取消</button>
        <button className="btn btn-primary" disabled={saving}
          onClick={() => onSubmit(apiKey, alias)}>
          {saving ? '保存中…' : '保存修改'}
        </button>
      </>
    }>
      <div className="form-group">
        <label className="form-label">新 API Key（留空则不更换）</label>
        <input className="form-input" type="password" placeholder="输入新 API Key（留空保持不变）"
          value={apiKey} onChange={e => setApiKey(e.target.value)} autoFocus />
      </div>
      <div className="form-group" style={{ marginBottom: 0 }}>
        <label className="form-label">别名</label>
        <input className="form-input" placeholder="配置别名"
          value={alias} onChange={e => setAlias(e.target.value)} />
      </div>
    </Modal>
  )
}

// ── Main Models component ─────────────────────────────────────────────────
export function Models() {
  const { toast } = useToast()
  const [activeTab, setActiveTab] = useState<TabKey>('llm')

  // LLM configs
  const [llmConfigs,        setLlmConfigs]        = useState<UserLLMConfig[]>([])
  const [providers,         setProviders]         = useState<AvailableProvider[]>([])
  const [llmLoading,        setLlmLoading]        = useState(true)
  const [providersLoading,  setProvidersLoading]  = useState(false)
  const [showAddLLM,        setShowAddLLM]        = useState(false)
  const [editLLM,           setEditLLM]           = useState<UserLLMConfig | null>(null)
  const [deleteLLM,         setDeleteLLM]         = useState<UserLLMConfig | null>(null)
  const [llmSaving,         setLlmSaving]         = useState(false)
  const [expandedProviders, setExpandedProviders] = useState<Set<string>>(new Set())

  // RAG config
  const [ragConfig,   setRagConfig]   = useState<UserRagConfig | null>(null)
  const [ragLoading,  setRagLoading]  = useState(false)
  const [ragKey,      setRagKey]      = useState('')
  const [ragSaving,   setRagSaving]   = useState(false)
  const [ragDeleteConfirm, setRagDeleteConfirm] = useState(false)
  const [ragFetched,  setRagFetched]  = useState(false)

  // Search config
  const [searchConfig, setSearchConfig] = useState<UserSearchConfig | null>(null)
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchKey,    setSearchKey]   = useState('')
  const [searchSaving, setSearchSaving] = useState(false)
  const [searchDeleteConfirm, setSearchDeleteConfirm] = useState(false)
  const [searchFetched, setSearchFetched] = useState(false)

  const groupedLLMConfigs = useMemo(() => {
    const map = new Map<string, UserLLMConfig[]>()
    for (const c of llmConfigs) {
      if (!map.has(c.provider_name)) map.set(c.provider_name, [])
      map.get(c.provider_name)!.push(c)
    }
    return map
  }, [llmConfigs])

  function toggleProvider(name: string) {
    setExpandedProviders(prev => {
      const s = new Set(prev)
      s.has(name) ? s.delete(name) : s.add(name)
      return s
    })
  }

  const loadLLM = useCallback(async () => {
    setLlmLoading(true)
    try {
      const configs = await listUserLLMConfigs()
      setLlmConfigs(configs)
      setExpandedProviders(new Set())
    } catch { /* ignore */ }
    finally { setLlmLoading(false) }
  }, [])

  const loadRag = useCallback(async () => {
    setRagLoading(true)
    try { setRagConfig(await getUserRagConfig()) } catch { /* ignore */ }
    finally { setRagLoading(false); setRagFetched(true) }
  }, [])

  const loadSearch = useCallback(async () => {
    setSearchLoading(true)
    try { setSearchConfig(await getUserSearchConfig()) } catch { /* ignore */ }
    finally { setSearchLoading(false); setSearchFetched(true) }
  }, [])

  useEffect(() => { loadLLM() }, [loadLLM])
  useEffect(() => { if (activeTab === 'rag' && !ragFetched) loadRag() }, [activeTab, ragFetched, loadRag])
  useEffect(() => { if (activeTab === 'search' && !searchFetched) loadSearch() }, [activeTab, searchFetched, loadSearch])

  async function handleOpenAddLLM() {
    setProvidersLoading(true)
    try { setProviders(await listAvailableProviders()) } catch { /* ignore */ }
    finally { setProvidersLoading(false) }
    setShowAddLLM(true)
  }

  async function handleAddLLM(provider_model_id: number, api_key: string, alias: string, is_default: boolean) {
    setLlmSaving(true)
    try {
      const forceDefault = llmConfigs.length === 0 ? true : is_default
      const cfg = await createUserLLMConfig(provider_model_id, api_key, alias || null, forceDefault)
      setLlmConfigs(prev => [...prev, cfg])
      setExpandedProviders(prev => new Set([...prev, cfg.provider_name]))
      toast('配置添加成功', 'success')
      setShowAddLLM(false)
    } catch (err: any) { toast(err.message, 'error') }
    finally { setLlmSaving(false) }
  }

  async function handleEditLLM(api_key: string, alias: string) {
    if (!editLLM) return
    setLlmSaving(true)
    try {
      const data: { api_key?: string; alias?: string | null } = {}
      if (api_key) data.api_key = api_key
      data.alias = alias || null
      const cfg = await updateUserLLMConfig(editLLM.id, data)
      setLlmConfigs(prev => prev.map(c => c.id === cfg.id ? cfg : c))
      toast('配置已更新', 'success')
      setEditLLM(null)
    } catch (err: any) { toast(err.message, 'error') }
    finally { setLlmSaving(false) }
  }

  async function handleDeleteLLM() {
    if (!deleteLLM) return
    setLlmSaving(true)
    try {
      await deleteUserLLMConfig(deleteLLM.id)
      setLlmConfigs(prev => prev.filter(c => c.id !== deleteLLM.id))
      toast('已删除', 'success')
      setDeleteLLM(null)
    } catch (err: any) { toast(err.message, 'error') }
    finally { setLlmSaving(false) }
  }

  async function handleSetDefault(id: number) {
    try {
      await setDefaultLLMConfig(id)
      setLlmConfigs(prev => prev.map(c => ({ ...c, is_default: c.id === id })))
      toast('已设为默认', 'success')
    } catch (err: any) { toast(err.message, 'error') }
  }

  async function handleRagSave(e: FormEvent) {
    e.preventDefault()
    if (!ragKey.trim()) return
    setRagSaving(true)
    try {
      const cfg = ragConfig
        ? await updateUserRagConfig(ragKey)
        : await createUserRagConfig(ragKey)
      setRagConfig(cfg)
      setRagKey('')
      toast('RAG 配置已保存', 'success')
    } catch (err: any) { toast(err.message, 'error') }
    finally { setRagSaving(false) }
  }

  async function handleRagDelete() {
    setRagSaving(true)
    try {
      await deleteUserRagConfig()
      setRagConfig(null)
      toast('已删除 RAG 配置', 'success')
      setRagDeleteConfirm(false)
    } catch (err: any) { toast(err.message, 'error') }
    finally { setRagSaving(false) }
  }

  async function handleSearchSave(e: FormEvent) {
    e.preventDefault()
    if (!searchKey.trim()) return
    setSearchSaving(true)
    try {
      const cfg = searchConfig
        ? await updateUserSearchConfig(searchKey)
        : await createUserSearchConfig(searchKey)
      setSearchConfig(cfg)
      setSearchKey('')
      toast('联网搜索配置已保存', 'success')
    } catch (err: any) { toast(err.message, 'error') }
    finally { setSearchSaving(false) }
  }

  async function handleSearchDelete() {
    setSearchSaving(true)
    try {
      await deleteUserSearchConfig()
      setSearchConfig(null)
      toast('已删除搜索配置', 'success')
      setSearchDeleteConfirm(false)
    } catch (err: any) { toast(err.message, 'error') }
    finally { setSearchSaving(false) }
  }

  return (
    <div style={{ display: 'flex', height: '100vh', background: 'var(--bg)' }}>
      <SidebarNav />

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Page header */}
        <div style={{
          padding: '0 32px', height: 52, borderBottom: '1px solid var(--border)',
          background: 'var(--surface)', display: 'flex', alignItems: 'center', flexShrink: 0,
        }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-1)' }}>模型配置</div>
        </div>

        {/* Tab bar */}
        <div style={{
          display: 'flex', gap: 0,
          borderBottom: '1px solid var(--border)',
          background: 'var(--surface)', flexShrink: 0,
          padding: '0 32px',
        }}>
          {TABS.map(t => (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              style={{
                padding: '11px 20px',
                fontSize: 13,
                fontWeight: activeTab === t.key ? 600 : 400,
                color: activeTab === t.key ? 'var(--accent-dark)' : 'var(--text-3)',
                background: 'none', border: 'none', cursor: 'pointer',
                borderBottom: `2px solid ${activeTab === t.key ? 'var(--accent)' : 'transparent'}`,
                marginBottom: -1,
                transition: 'color 150ms, border-color 150ms',
                fontFamily: 'inherit', whiteSpace: 'nowrap',
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div style={{ flex: 1, overflow: 'auto', padding: '28px 32px' }}>

          {/* ─ LLM Configs ─ */}
          {activeTab === 'llm' && (
            <div className="config-card">
              <div className="config-card-header">
                <div>
                  <div className="config-card-title">
                    <Cpu style={{ width: 15, height: 15, color: 'var(--accent)' }} />
                    LLM 模型配置
                  </div>
                  <div className="config-card-sub">配置对话模型（OpenAI、Anthropic 等），每个配置需要独立的 API Key</div>
                </div>
                <button className="btn btn-primary" style={{ flexShrink: 0 }} onClick={handleOpenAddLLM} disabled={providersLoading}>
                  <Plus style={{ width: 14, height: 14 }} />{providersLoading ? '加载中…' : '添加配置'}
                </button>
              </div>
              <div className="config-card-body">
                {llmLoading ? (
                  <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--text-3)', fontSize: 13 }}>加载中…</div>
                ) : llmConfigs.length === 0 ? (
                  <div style={{ padding: '40px 0', textAlign: 'center' }}>
                    <Cpu style={{ width: 32, height: 32, margin: '0 auto 12px', color: 'var(--text-3)', opacity: .35 }} />
                    <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-2)', marginBottom: 6 }}>还没有 LLM 配置</div>
                    <div style={{ fontSize: 12.5, color: 'var(--text-3)', marginBottom: 16 }}>添加一个模型配置后，即可在会话中选择使用</div>
                    <button className="btn btn-primary" onClick={handleOpenAddLLM} disabled={providersLoading}>
                      <Plus style={{ width: 13, height: 13 }} />{providersLoading ? '加载中…' : '添加第一个配置'}
                    </button>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {Array.from(groupedLLMConfigs.entries()).map(([providerName, configs]) => {
                      const isExpanded = expandedProviders.has(providerName)
                      return (
                        <div key={providerName} style={{ border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
                          {/* Provider header */}
                          <div
                            onClick={() => toggleProvider(providerName)}
                            style={{
                              display: 'flex', alignItems: 'center', gap: 10,
                              padding: '11px 16px', cursor: 'pointer', userSelect: 'none',
                              background: 'var(--surface-2)',
                              borderBottom: isExpanded ? '1px solid var(--border)' : 'none',
                              transition: 'background 120ms',
                            }}
                          >
                            {isExpanded
                              ? <ChevronDown style={{ width: 14, height: 14, color: 'var(--text-3)', flexShrink: 0 }} />
                              : <ChevronRight style={{ width: 14, height: 14, color: 'var(--text-3)', flexShrink: 0 }} />}
                            <span style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-1)', flex: 1 }}>{providerName}</span>
                            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>{configs.length} 个配置</span>
                          </div>
                          {/* Config items */}
                          {isExpanded && (
                            <div style={{ padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 6 }}>
                              {configs.map(c => (
                                <div key={c.id} className={`llm-config-item${!c.is_active ? ' disabled' : ''}`}>
                                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, flex: 1, minWidth: 0 }}>
                                    <div style={{
                                      width: 36, height: 36, borderRadius: 8, background: 'var(--accent-bg)',
                                      display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                                    }}>
                                      <Cpu style={{ width: 16, height: 16, color: 'var(--accent)' }} />
                                    </div>
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                                        <span style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-1)' }}>
                                          {c.alias || c.model_name}
                                        </span>
                                        {c.is_default && (
                                          <span className="badge badge-accent" style={{ fontSize: 10.5, padding: '1px 6px' }}>
                                            <Star style={{ width: 9, height: 9 }} />默认
                                          </span>
                                        )}
                                        {!c.is_active && (
                                          <span className="badge badge-error" style={{ fontSize: 10.5, padding: '1px 6px' }}>已停用</span>
                                        )}
                                      </div>
                                      <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 3 }}>
                                        {c.model_name}
                                        {c.alias && <span style={{ marginLeft: 4 }}>（别名：{c.alias}）</span>}
                                      </div>
                                    </div>
                                  </div>
                                  <div className="td-actions">
                                    {!c.is_default && c.is_active && (
                                      <button className="btn btn-sm btn-ghost" onClick={() => handleSetDefault(c.id)}>
                                        <Star style={{ width: 12, height: 12 }} />设为默认
                                      </button>
                                    )}
                                    <button className="btn-icon" title="编辑" onClick={() => setEditLLM(c)}>
                                      <Edit2 style={{ width: 14, height: 14 }} />
                                    </button>
                                    <button className="btn-icon" style={{ color: 'var(--error)' }} title="删除"
                                      onClick={() => setDeleteLLM(c)}>
                                      <Trash2 style={{ width: 14, height: 14 }} />
                                    </button>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ─ RAG Config ─ */}
          {activeTab === 'rag' && (
            <div className="config-card">
              <div className="config-card-header">
                <div>
                  <div className="config-card-title">
                    <Database style={{ width: 15, height: 15, color: 'var(--accent)' }} />
                    向量检索配置（RAG）
                  </div>
                  <div className="config-card-sub">
                    配置阿里云 DashScope Embedding API，用于将知识库文档向量化并进行语义检索
                  </div>
                </div>
                {ragConfig && (
                  <button className="btn btn-ghost" style={{ flexShrink: 0, color: 'var(--error)' }}
                    onClick={() => setRagDeleteConfirm(true)}>
                    <Trash2 style={{ width: 13, height: 13 }} />删除配置
                  </button>
                )}
              </div>
              <div className="config-card-body">
                {ragLoading ? (
                  <div style={{ padding: '16px 0', textAlign: 'center', color: 'var(--text-3)', fontSize: 13 }}>加载中…</div>
                ) : ragConfig ? (
                  <>
                    <div className="api-config-info">
                      <KeyRound style={{ width: 15, height: 15, color: 'var(--success)', flexShrink: 0 }} />
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)' }}>已配置</div>
                        <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 2 }}>
                          {ragConfig.model} · 更新于 {new Date(ragConfig.updated_at).toLocaleDateString('zh-CN')}
                        </div>
                      </div>
                      <span className="badge badge-success" style={{ marginLeft: 'auto' }}>生效中</span>
                    </div>
                    <form onSubmit={handleRagSave} style={{ marginTop: 16 }}>
                      <div className="form-group" style={{ marginBottom: 10 }}>
                        <label className="form-label">更换 API Key</label>
                        <input className="form-input" type="password" placeholder="输入新的 DashScope API Key"
                          value={ragKey} onChange={e => setRagKey(e.target.value)} />
                      </div>
                      <button className="btn btn-ghost" type="submit" disabled={ragSaving || !ragKey.trim()}>
                        {ragSaving ? '保存中…' : '更换 API Key'}
                      </button>
                    </form>
                  </>
                ) : (
                  <form onSubmit={handleRagSave}>
                    <div style={{ fontSize: 13, color: 'var(--text-3)', marginBottom: 16 }}>
                      未配置。配置后可在创建会话时启用知识库检索功能。
                    </div>
                    <div className="form-group" style={{ marginBottom: 10 }}>
                      <label className="form-label">阿里云 DashScope API Key</label>
                      <input className="form-input" type="password" placeholder="sk-xxxx…"
                        value={ragKey} onChange={e => setRagKey(e.target.value)} />
                      <div className="form-hint">用于 text-embedding-v4 模型，将在保存时验证有效性</div>
                    </div>
                    <button className="btn btn-primary" type="submit" disabled={ragSaving || !ragKey.trim()}>
                      {ragSaving ? '验证中…' : '保存配置'}
                    </button>
                  </form>
                )}
              </div>
            </div>
          )}

          {/* ─ Search Config ─ */}
          {activeTab === 'search' && (
            <div className="config-card">
              <div className="config-card-header">
                <div>
                  <div className="config-card-title">
                    <Search style={{ width: 15, height: 15, color: 'var(--accent)' }} />
                    联网搜索配置（DeepSearch）
                  </div>
                  <div className="config-card-sub">
                    配置 Tavily Search API，用于在生成时实时联网搜索补充信息
                  </div>
                </div>
                {searchConfig && (
                  <button className="btn btn-ghost" style={{ flexShrink: 0, color: 'var(--error)' }}
                    onClick={() => setSearchDeleteConfirm(true)}>
                    <Trash2 style={{ width: 13, height: 13 }} />删除配置
                  </button>
                )}
              </div>
              <div className="config-card-body">
                {searchLoading ? (
                  <div style={{ padding: '16px 0', textAlign: 'center', color: 'var(--text-3)', fontSize: 13 }}>加载中…</div>
                ) : searchConfig ? (
                  <>
                    <div className="api-config-info">
                      <KeyRound style={{ width: 15, height: 15, color: 'var(--success)', flexShrink: 0 }} />
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)' }}>已配置 · {searchConfig.provider}</div>
                        <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 2 }}>
                          更新于 {new Date(searchConfig.updated_at).toLocaleDateString('zh-CN')}
                        </div>
                      </div>
                      <span className="badge badge-success" style={{ marginLeft: 'auto' }}>生效中</span>
                    </div>
                    <form onSubmit={handleSearchSave} style={{ marginTop: 16 }}>
                      <div className="form-group" style={{ marginBottom: 10 }}>
                        <label className="form-label">更换 API Key</label>
                        <input className="form-input" type="password" placeholder="输入新的 Tavily API Key"
                          value={searchKey} onChange={e => setSearchKey(e.target.value)} />
                      </div>
                      <button className="btn btn-ghost" type="submit" disabled={searchSaving || !searchKey.trim()}>
                        {searchSaving ? '保存中…' : '更换 API Key'}
                      </button>
                    </form>
                  </>
                ) : (
                  <form onSubmit={handleSearchSave}>
                    <div style={{ fontSize: 13, color: 'var(--text-3)', marginBottom: 16 }}>
                      未配置。配置后可在创建会话时启用联网搜索，AI 将实时检索最新资料。
                    </div>
                    <div className="form-group" style={{ marginBottom: 10 }}>
                      <label className="form-label">Tavily API Key</label>
                      <input className="form-input" type="password" placeholder="tvly-xxxx…"
                        value={searchKey} onChange={e => setSearchKey(e.target.value)} />
                      <div className="form-hint">前往 tavily.com 免费注册获取 API Key，将在保存时验证有效性</div>
                    </div>
                    <button className="btn btn-primary" type="submit" disabled={searchSaving || !searchKey.trim()}>
                      {searchSaving ? '验证中…' : '保存配置'}
                    </button>
                  </form>
                )}
              </div>
            </div>
          )}

        </div>
      </main>

      {/* Modals */}
      {showAddLLM && (
        <AddLLMModal providers={providers} loading={llmSaving}
          onClose={() => setShowAddLLM(false)} onSubmit={handleAddLLM} />
      )}
      {editLLM && (
        <EditLLMModal config={editLLM} loading={llmSaving}
          onClose={() => setEditLLM(null)} onSubmit={handleEditLLM} />
      )}
      {deleteLLM && (
        <Confirm title="删除配置"
          message={`确认删除配置「${deleteLLM.alias || deleteLLM.model_name}」？使用该配置的会话将改为使用默认配置。`}
          danger loading={llmSaving}
          onConfirm={handleDeleteLLM} onCancel={() => setDeleteLLM(null)} />
      )}
      {ragDeleteConfirm && (
        <Confirm title="删除 RAG 配置" message="确认删除向量检索配置？删除后将无法使用知识库检索功能。"
          danger loading={ragSaving}
          onConfirm={handleRagDelete} onCancel={() => setRagDeleteConfirm(false)} />
      )}
      {searchDeleteConfirm && (
        <Confirm title="删除搜索配置" message="确认删除联网搜索配置？删除后将无法使用联网搜索功能。"
          danger loading={searchSaving}
          onConfirm={handleSearchDelete} onCancel={() => setSearchDeleteConfirm(false)} />
      )}
    </div>
  )
}
