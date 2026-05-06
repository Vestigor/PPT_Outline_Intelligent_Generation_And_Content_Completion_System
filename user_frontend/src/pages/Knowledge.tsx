import { useState, useEffect, useRef, useCallback, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  MessageSquare, Database, LogOut, Upload, Trash2, RefreshCw,
  FileText, AlertCircle, CheckCircle, Clock, Loader2, Cpu, KeyRound, UserX,
  ChevronDown, ChevronRight, ChevronUp, Edit2, Check, X, Mail, Eye, EyeOff,
} from 'lucide-react'
import {
  listKnowledge, uploadKnowledge, deleteKnowledge, retryKnowledge, updateFileCategory,
  logout, getToken, changePassword, deleteAccount, sendEmailCode, updateEmail,
  type KnowledgeFile, type DocStatus,
} from '../api'
import { useToast } from '../hooks/useToast'
import { Modal, Confirm } from '../components/Modal'

const STATUS_LABEL: Record<DocStatus, string> = {
  pending: '等待处理', processing: '处理中', ready: '已就绪', failed: '失败',
}
const STATUS_ICON: Record<DocStatus, typeof Clock> = {
  pending: Clock, processing: Loader2, ready: CheckCircle, failed: AlertCircle,
}
const STATUS_COLOR: Record<DocStatus, string> = {
  pending: 'var(--text-3)', processing: 'var(--accent)', ready: 'var(--success)', failed: 'var(--error)',
}
const STATUS_CLS: Record<DocStatus, string> = {
  pending: 'badge-neutral', processing: 'badge-info', ready: 'badge-success', failed: 'badge-error',
}

let _filesCache: KnowledgeFile[] = []

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function groupByCategory(files: KnowledgeFile[]): Map<string, KnowledgeFile[]> {
  const map = new Map<string, KnowledgeFile[]>()
  for (const f of files) {
    const key = f.category || 'default'
    const arr = map.get(key) ?? []
    arr.push(f)
    map.set(key, arr)
  }
  return map
}

// ── Upload Modal ──────────────────────────────────────────────────────────
function UploadModal({ onClose, onUploaded }: {
  onClose: () => void; onUploaded: (file: KnowledgeFile) => void
}) {
  const { toast } = useToast()
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const [category,    setCategory]    = useState('')
  const [uploading,   setUploading]   = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!pendingFile) return
    setUploading(true)
    try {
      const kf = await uploadKnowledge(pendingFile, category.trim() || 'default')
      toast(`「${kf.file_name}」上传成功，正在处理…`, 'success')
      onUploaded(kf)
      onClose()
    } catch (err: any) {
      if (err.message !== '_auth_redirect') toast(err.message, 'error')
    } finally {
      setUploading(false)
    }
  }

  return (
    <Modal title="上传文件到知识库" onClose={onClose} footer={
      <>
        <button className="btn btn-ghost" onClick={onClose} disabled={uploading}>取消</button>
        <button className="btn btn-primary" onClick={handleSubmit as any}
          disabled={uploading || !pendingFile}>
          {uploading ? '上传中…' : '确认上传'}
        </button>
      </>
    }>
      <div className="form-group">
        <label className="form-label">选择文件</label>
        {pendingFile ? (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '10px 14px', background: 'var(--accent-bg)', borderRadius: 8,
            border: '1px solid rgba(184,135,74,.25)', cursor: 'pointer',
          }} onClick={() => fileRef.current?.click()}>
            <FileText style={{ width: 18, height: 18, color: 'var(--accent)', flexShrink: 0 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {pendingFile.name}
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--text-3)', marginTop: 1 }}>{formatBytes(pendingFile.size)}</div>
            </div>
            <span style={{ fontSize: 11, color: 'var(--accent)', whiteSpace: 'nowrap' }}>点击更换</span>
          </div>
        ) : (
          <div style={{
            border: '2px dashed var(--border)', borderRadius: 8, padding: '24px 16px',
            textAlign: 'center', cursor: 'pointer', transition: 'all 150ms',
          }}
            onClick={() => fileRef.current?.click()}
            onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--accent)'; (e.currentTarget as HTMLDivElement).style.background = 'var(--accent-bg)' }}
            onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.borderColor = ''; (e.currentTarget as HTMLDivElement).style.background = '' }}
          >
            <Upload style={{ width: 22, height: 22, color: 'var(--text-3)', margin: '0 auto 8px' }} />
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-2)', marginBottom: 3 }}>点击选择文件</div>
            <div style={{ fontSize: 12, color: 'var(--text-3)' }}>支持 PDF、Word、TXT、Markdown 等格式</div>
          </div>
        )}
        <input ref={fileRef} type="file" style={{ display: 'none' }}
          accept=".pdf,.doc,.docx,.txt,.md,.ppt,.pptx"
          onChange={e => { setPendingFile(e.target.files?.[0] ?? null); e.target.value = '' }} />
      </div>
      <div className="form-group" style={{ marginBottom: 0 }}>
        <label className="form-label">文件分类</label>
        <input className="form-input"
          placeholder="自定义分类名称，如：研究报告、会议记录（留空则归入 default）"
          value={category}
          onChange={e => setCategory(e.target.value)}
          autoFocus={!!pendingFile}
        />
        <div className="form-hint">用于在知识库中分类管理文件，便于检索时过滤</div>
      </div>
    </Modal>
  )
}

// ── Change Password Modal ─────────────────────────────────────────────────
function ChangePasswordModal({ onClose }: { onClose: () => void }) {
  const { toast } = useToast()
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

// ── Main Knowledge component ──────────────────────────────────────────────
export function Knowledge() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [files,        setFiles]        = useState<KnowledgeFile[]>(_filesCache)
  const [loading,      setLoading]      = useState(_filesCache.length === 0)
  const [showUpload,   setShowUpload]   = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<KnowledgeFile | null>(null)
  const [deleting,     setDeleting]     = useState(false)
  const [showChangePwd,     setShowChangePwd]     = useState(false)
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false)
  const [showDeleteAccount, setShowDeleteAccount] = useState(false)
  const [showBindEmail,     setShowBindEmail]     = useState(false)
  const [expanded,          setExpanded]          = useState<Set<string>>(new Set())
  const [editingFileId,     setEditingFileId]     = useState<number | null>(null)
  const [editCategoryValue, setEditCategoryValue] = useState('')

  const load = useCallback(async () => {
    try {
      const data = await listKnowledge()
      _filesCache = data
      setFiles(data)
    } catch { toast('加载失败', 'error') }
    finally { setLoading(false) }
  }, [toast])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (files.some(f => f.status === 'pending' || f.status === 'processing')) {
      const t = setTimeout(load, 3000)
      return () => clearTimeout(t)
    }
  }, [files, load])

  async function doDelete() {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await deleteKnowledge(deleteTarget.id)
      setFiles(prev => prev.filter(f => f.id !== deleteTarget.id))
      toast('已删除', 'success')
      setDeleteTarget(null)
    } catch (err: any) { toast(err.message, 'error') }
    finally { setDeleting(false) }
  }

  function toggleExpand(cat: string) {
    setExpanded(prev => {
      const s = new Set(prev)
      if (s.has(cat)) s.delete(cat); else s.add(cat)
      return s
    })
  }

  function startEditCategory(file: KnowledgeFile) {
    setEditingFileId(file.id)
    setEditCategoryValue(file.category || 'default')
  }

  async function doEditCategory(file: KnowledgeFile) {
    const newCat = editCategoryValue.trim() || 'default'
    if (newCat === (file.category || 'default')) { setEditingFileId(null); return }
    try {
      const updated = await updateFileCategory(file.id, newCat)
      setFiles(prev => {
        const next = prev.map(f => f.id === updated.id ? updated : f)
        _filesCache = next
        return next
      })
      setExpanded(prev => new Set([...prev, newCat]))
      setEditingFileId(null)
      toast('分类已更新', 'success')
    } catch (err: any) {
      if (err.message !== '_auth_redirect') toast(err.message, 'error')
    }
  }

  async function doRetry(file: KnowledgeFile) {
    try {
      const updated = await retryKnowledge(file.id)
      setFiles(prev => prev.map(f => f.id === updated.id ? updated : f))
      toast('已重新提交处理', 'info')
    } catch (err: any) { toast(err.message, 'error') }
  }

  async function doLogout() {
    try { await logout(getToken()) } catch {}
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    navigate('/login', { replace: true })
  }

  async function doDeleteAccount() {
    try {
      await deleteAccount()
      localStorage.removeItem('token'); localStorage.removeItem('username')
      navigate('/login', { replace: true })
    } catch (err: any) { toast(err.message, 'error') }
  }

  const grouped = groupByCategory(files)
  const username = localStorage.getItem('username') ?? ''

  return (
    <div style={{ display: 'flex', height: '100vh', background: 'var(--bg)' }}>
      {/* Sidebar */}
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
          <button className="sidebar-nav-item active">
            <Database />知识库
          </button>
          <button className="sidebar-nav-item" onClick={() => navigate('/models')}>
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

      {/* Main */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Page header */}
        <div style={{
          padding: '0 32px', height: 52, borderBottom: '1px solid var(--border)',
          background: 'var(--surface)', display: 'flex', alignItems: 'center',
          justifyContent: 'space-between', flexShrink: 0,
        }}>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-1)' }}>知识库管理</div>
            <div style={{ fontSize: 11.5, color: 'var(--text-3)', marginTop: 1 }}>
              上传文档，启用 RAG 时 AI 将从中检索相关内容
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-ghost" onClick={load} style={{ padding: '6px 12px' }}>
              <RefreshCw style={{ width: 13, height: 13 }} />刷新
            </button>
            <button className="btn btn-primary" onClick={() => setShowUpload(true)}>
              <Upload style={{ width: 14, height: 14 }} />上传文件
            </button>
          </div>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflow: 'auto', padding: '24px 32px' }}>
          {loading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: 64 }}>
              <Loader2 style={{ width: 24, height: 24, animation: 'spin 1s linear infinite', color: 'var(--accent)' }} />
            </div>
          ) : files.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '72px 0', color: 'var(--text-3)' }}>
              <Database style={{ width: 36, height: 36, margin: '0 auto 14px', opacity: .35 }} />
              <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-2)', marginBottom: 6 }}>知识库为空</div>
              <div style={{ fontSize: 13, marginBottom: 20 }}>上传文档后，AI 可在生成 PPT 时检索其中内容</div>
              <button className="btn btn-primary" onClick={() => setShowUpload(true)}>
                <Upload style={{ width: 14, height: 14 }} />上传第一个文件
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {Array.from(grouped.entries()).map(([category, catFiles]) => {
                const isExpanded = expanded.has(category)
                return (
                  <div key={category} style={{ border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
                    {/* Category header */}
                    <div
                      onClick={() => toggleExpand(category)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 12,
                        padding: '12px 16px', cursor: 'pointer',
                        userSelect: 'none', background: 'var(--surface-2)',
                        borderBottom: isExpanded ? '1px solid var(--border)' : 'none',
                        transition: 'background 120ms',
                      }}
                    >
                      {isExpanded
                        ? <ChevronDown  style={{ width: 15, height: 15, color: 'var(--text-2)', flexShrink: 0 }} />
                        : <ChevronRight style={{ width: 15, height: 15, color: 'var(--text-2)', flexShrink: 0 }} />}
                      <span style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-1)', flex: 1, textTransform: 'uppercase', letterSpacing: '.04em' }}>
                        {category}
                      </span>
                      <span style={{ fontSize: 12, color: 'var(--text-3)' }}>
                        {catFiles.length} 个文件
                      </span>
                    </div>

                    {/* File table */}
                    {isExpanded && (
                      <div className="table-wrap" style={{ borderRadius: 0, border: 'none' }}>
                        <table>
                          <thead>
                            <tr>
                              <th>文件名</th>
                              <th>大小</th>
                              <th>状态</th>
                              <th>上传时间</th>
                              <th style={{ width: 100 }}>操作</th>
                            </tr>
                          </thead>
                          <tbody>
                            {catFiles.map(file => {
                              const Icon = STATUS_ICON[file.status]
                              const color = STATUS_COLOR[file.status]
                              return (
                                <tr key={file.id}>
                                  <td>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                      <div style={{
                                        width: 32, height: 32, borderRadius: 7, background: 'var(--accent-bg)',
                                        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                                      }}>
                                        <FileText style={{ width: 15, height: 15, color: 'var(--accent)' }} />
                                      </div>
                                      <div style={{ minWidth: 0 }}>
                                        <div style={{
                                          fontSize: 13, fontWeight: 500, color: 'var(--text-1)',
                                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 280,
                                        }}>{file.file_name}</div>
                                        {file.error_message && (
                                          <div style={{ fontSize: 11.5, color: 'var(--error)', marginTop: 1 }}>{file.error_message}</div>
                                        )}
                                      </div>
                                    </div>
                                  </td>
                                  <td className="td-mono" style={{ color: 'var(--text-3)', whiteSpace: 'nowrap' }}>
                                    {formatBytes(file.size_bytes)}
                                  </td>
                                  <td>
                                    <span className={`badge ${STATUS_CLS[file.status]}`} style={{ display: 'inline-flex', gap: 4 }}>
                                      <Icon style={{
                                        width: 11, height: 11, color,
                                        ...(file.status === 'processing' ? { animation: 'spin 1s linear infinite' } : {})
                                      }} />
                                      {STATUS_LABEL[file.status]}
                                    </span>
                                  </td>
                                  <td className="td-mono" style={{ color: 'var(--text-3)', fontSize: 12 }}>
                                    {formatDate(file.created_at)}
                                  </td>
                                  <td>
                                    <div className="td-actions">
                                      {editingFileId === file.id ? (
                                        <>
                                          <input
                                            className="form-input"
                                            style={{ padding: '2px 8px', fontSize: 12, height: 26, width: 110 }}
                                            value={editCategoryValue}
                                            onChange={e => setEditCategoryValue(e.target.value)}
                                            onKeyDown={e => {
                                              if (e.key === 'Enter') doEditCategory(file)
                                              if (e.key === 'Escape') setEditingFileId(null)
                                            }}
                                            autoFocus
                                          />
                                          <button className="btn-icon" style={{ color: 'var(--success)' }}
                                            onClick={() => doEditCategory(file)}>
                                            <Check style={{ width: 13, height: 13 }} />
                                          </button>
                                          <button className="btn-icon" onClick={() => setEditingFileId(null)}>
                                            <X style={{ width: 13, height: 13 }} />
                                          </button>
                                        </>
                                      ) : (
                                        <>
                                          {file.status === 'failed' && (
                                            <button className="btn btn-sm btn-ghost" onClick={() => doRetry(file)}>
                                              <RefreshCw style={{ width: 12, height: 12 }} />重试
                                            </button>
                                          )}
                                          <button className="btn-icon" title="修改分类"
                                            onClick={() => startEditCategory(file)}>
                                            <Edit2 style={{ width: 13, height: 13 }} />
                                          </button>
                                          <button className="btn-icon" style={{ color: 'var(--error)' }}
                                            onClick={() => setDeleteTarget(file)}>
                                            <Trash2 style={{ width: 14, height: 14 }} />
                                          </button>
                                        </>
                                      )}
                                    </div>
                                  </td>
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </main>

      {/* Modals */}
      {showUpload && (
        <UploadModal
          onClose={() => setShowUpload(false)}
          onUploaded={kf => setFiles(prev => [kf, ...prev])}
        />
      )}

      {deleteTarget && (
        <Confirm
          title="删除文件"
          message={`确定要删除「${deleteTarget.file_name}」吗？关联此文件的会话将无法再从中检索内容。`}
          danger loading={deleting}
          onConfirm={doDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}

      {showBindEmail && <BindEmailModal onClose={() => setShowBindEmail(false)} />}
      {showChangePwd && <ChangePasswordModal onClose={() => setShowChangePwd(false)} />}

      {showLogoutConfirm && (
        <Confirm
          title="退出登录"
          message="确认退出登录？退出后需重新登录才能使用。"
          loading={false}
          onConfirm={doLogout}
          onCancel={() => setShowLogoutConfirm(false)}
        />
      )}

      {showDeleteAccount && (
        <Confirm
          title="注销账户"
          message="确认注销账户？此操作不可撤销，账户及所有相关数据将被永久删除。"
          danger loading={false}
          onConfirm={doDeleteAccount}
          onCancel={() => setShowDeleteAccount(false)}
        />
      )}
    </div>
  )
}
