import { useState, type ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Users, Cpu, LogOut, Presentation, KeyRound,
  Check, AlertCircle, Eye, EyeOff, ChevronUp, Mail,
} from 'lucide-react'
import { Modal, Confirm } from './Modal'
import { useToast } from '../hooks/useToast'
import { changePassword, sendEmailCode, updateEmail } from '../api'

interface Props {
  children: ReactNode
  title: string
  subtitle?: string
  actions?: ReactNode
}

// ── Password strength helpers ─────────────────────────────────────────────
interface PwdRule { label: string; ok: boolean }

function getPwdRules(pwd: string): PwdRule[] {
  return [
    { label: '长度为 8-16 个字符',      ok: pwd.length >= 8 && pwd.length <= 16 },
    { label: '不能包含空格',             ok: pwd.length > 0 && !pwd.includes(' ') },
    { label: '需包含大、小写字母和数字', ok: /[A-Z]/.test(pwd) && /[a-z]/.test(pwd) && /\d/.test(pwd) },
  ]
}
function pwdStrength(pwd: string) { return getPwdRules(pwd).filter(r => r.ok).length }

function PwdStrengthWidget({ pwd, focused }: { pwd: string; focused: boolean }) {
  const rules    = getPwdRules(pwd)
  const strength = pwdStrength(pwd)
  const colors   = ['', '#EF4444', '#F59E0B', '#22C55E']
  const labels   = ['', '低', '中', '高']
  if (!pwd) return null
  return (
    <div style={{ marginTop: 6 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <span style={{ fontSize: 12, color: 'var(--text-3)' }}>密码强度：</span>
        <span style={{ fontSize: 12, fontWeight: 600, color: colors[strength] }}>{labels[strength]}</span>
      </div>
      <div style={{ display: 'flex', gap: 3, height: 4, marginBottom: 6 }}>
        {[1, 2, 3].map(i => (
          <div key={i} style={{ flex: 1, borderRadius: 2, background: strength >= i ? colors[strength] : 'var(--border)', transition: 'background .2s' }} />
        ))}
      </div>
      {focused && (
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 4 }}>密码要求：</div>
          {rules.map(r => (
            <div key={r.label} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
              {r.ok
                ? <Check       style={{ width: 13, height: 13, color: '#22C55E', flexShrink: 0 }} />
                : <AlertCircle style={{ width: 13, height: 13, color: '#EF4444', flexShrink: 0 }} />}
              <span style={{ fontSize: 12, color: r.ok ? 'var(--text-2)' : '#EF4444' }}>{r.label}</span>
            </div>
          ))}
        </div>
      )}
      {!focused && !rules.every(r => r.ok) && (
        <div style={{ fontSize: 12, color: '#EF4444', display: 'flex', alignItems: 'center', gap: 4 }}>
          <AlertCircle style={{ width: 13, height: 13 }} />密码不符合规范
        </div>
      )}
    </div>
  )
}

// ── Change Password Modal ─────────────────────────────────────────────────
function ChangePasswordModal({ onClose }: { onClose: () => void }) {
  const { toast }   = useToast()
  const [oldPwd,     setOldPwd]     = useState('')
  const [newPwd,     setNewPwd]     = useState('')
  const [confirm,    setConfirm]    = useState('')
  const [showOld,    setShowOld]    = useState(false)
  const [showNew,    setShowNew]    = useState(false)
  const [newFocused, setNewFocused] = useState(false)
  const [loading,    setLoading]    = useState(false)

  const allPass = getPwdRules(newPwd).every(r => r.ok)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!allPass)           { toast('新密码不符合规范', 'error'); return }
    if (newPwd !== confirm) { toast('两次密码不一致', 'error'); return }
    setLoading(true)
    try {
      await changePassword(oldPwd, newPwd)
      toast('密码修改成功', 'success')
      onClose()
    } catch (err: any) {
      toast(err.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title="修改密码" onClose={onClose} footer={
      <>
        <button className="btn btn-ghost" onClick={onClose} disabled={loading}>取消</button>
        <button className="btn btn-primary" onClick={handleSubmit as any}
          disabled={loading || !oldPwd || !allPass || !confirm || newPwd !== confirm}>
          {loading ? '修改中…' : '确认修改'}
        </button>
      </>
    }>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label">当前密码</label>
          <div style={{ position: 'relative' }}>
            <input className="form-input" type={showOld ? 'text' : 'password'}
              autoComplete="current-password" placeholder="输入当前密码"
              value={oldPwd} onChange={e => setOldPwd(e.target.value)}
              style={{ paddingRight: 40 }} autoFocus />
            <button type="button" onClick={() => setShowOld(p => !p)}
              style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: 0 }}>
              {showOld ? <EyeOff style={{ width: 15, height: 15 }} /> : <Eye style={{ width: 15, height: 15 }} />}
            </button>
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">新密码</label>
          <div style={{ position: 'relative' }}>
            <input className="form-input" type={showNew ? 'text' : 'password'}
              autoComplete="new-password" placeholder="8-16 位，含大小写字母和数字"
              value={newPwd} onChange={e => setNewPwd(e.target.value)}
              onFocus={() => setNewFocused(true)} onBlur={() => setNewFocused(false)}
              style={{ paddingRight: 40 }} />
            <button type="button" onClick={() => setShowNew(p => !p)}
              style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: 0 }}>
              {showNew ? <EyeOff style={{ width: 15, height: 15 }} /> : <Eye style={{ width: 15, height: 15 }} />}
            </button>
          </div>
          <PwdStrengthWidget pwd={newPwd} focused={newFocused} />
        </div>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">确认新密码</label>
          <input className="form-input" type="password"
            autoComplete="new-password" placeholder="再次输入新密码"
            value={confirm} onChange={e => setConfirm(e.target.value)} />
          {confirm && newPwd !== confirm && (
            <div style={{ fontSize: 12, color: '#EF4444', marginTop: 4 }}>两次密码不一致</div>
          )}
        </div>
      </form>
    </Modal>
  )
}

// ── Bind / Update Email Modal (two-step) ─────────────────────────────────
function BindEmailModal({ onClose }: { onClose: () => void }) {
  const { toast }        = useToast()
  const [step,           setStep]      = useState<1 | 2>(1)
  const [pwd,            setPwd]       = useState('')
  const [showPwd,        setShowPwd]   = useState(false)
  const [email,          setEmail]     = useState('')
  const [code,           setCode]      = useState('')
  const [sending,        setSending]   = useState(false)
  const [countdown,      setCountdown] = useState(0)
  const [loading,        setLoading]   = useState(false)

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
        {/* Hidden username satisfies browser autofill pair — prevents filling the sidebar search input */}
        <input type="text" autoComplete="username" style={{ display: 'none' }} readOnly tabIndex={-1} />
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
            onChange={e => setEmail(e.target.value)} style={{ flex: 1 }} autoFocus />
          <button type="button" className="btn btn-ghost"
            style={{ flexShrink: 0, padding: '0 12px', fontSize: 12 }}
            disabled={sending || countdown > 0 || !email}
            onClick={handleSendCode}>
            {countdown > 0 ? `${countdown}s` : sending ? '发送中…' : '发送验证码'}
          </button>
        </div>
      </div>
      <div className="form-group" style={{ marginBottom: 0 }}>
        <label className="form-label">验证码</label>
        <input className="form-input" type="text" autoComplete="one-time-code"
          placeholder="输入 6 位验证码" maxLength={6}
          value={code} onChange={e => setCode(e.target.value)} />
      </div>
    </Modal>
  )
}

// ── Layout ────────────────────────────────────────────────────────────────
export function Layout({ children, title, subtitle, actions }: Props) {
  const navigate = useNavigate()
  const username = localStorage.getItem('admin_username') ?? 'Admin'
  const role     = localStorage.getItem('admin_role') ?? 'admin'

  const [showChangePwd,     setShowChangePwd]     = useState(false)
  const [showBindEmail,     setShowBindEmail]     = useState(false)
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false)

  function doLogout() {
    localStorage.removeItem('admin_token')
    localStorage.removeItem('admin_refresh_token')
    localStorage.removeItem('admin_username')
    localStorage.removeItem('admin_role')
    navigate('/login')
  }

  const ROLE_LABEL: Record<string, string> = {
    super_admin: '超级管理员',
    admin:       '管理员',
  }

  return (
    <>
      <div className="app-shell">
        <aside className="sidebar">
          <div className="sidebar-brand">
            <div className="sidebar-brand-mark"><Presentation /></div>
            <div>
              <div className="sidebar-brand-name">PPT 管理台</div>
              <div className="sidebar-brand-sub">Admin Console</div>
            </div>
          </div>

          <nav className="sidebar-nav">
            <div className="nav-section-label">概览</div>
            <NavLink to="/" end className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
              <LayoutDashboard />仪表盘
            </NavLink>

            <div className="nav-section-label">管理</div>
            <NavLink to="/users" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
              <Users />用户管理
            </NavLink>
            <NavLink to="/providers" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
              <Cpu />模型提供商
            </NavLink>
          </nav>

          {/* User hover area — mirrors user-frontend design */}
          <div className="sidebar-user-area">
            <div className="sidebar-user-mini">
              <div className="sidebar-avatar">{username.slice(0, 1).toUpperCase()}</div>
              <div className="sidebar-user-mini-info">
                <div className="sidebar-user-name truncate">{username}</div>
                <div className="sidebar-user-role">{ROLE_LABEL[role] ?? '管理员'}</div>
              </div>
              <ChevronUp style={{ width: 12, height: 12, opacity: .5, flexShrink: 0 }} className="sidebar-user-caret" />
            </div>

            <div className="sidebar-user-popup">
              <div className="sidebar-user-popup-head">
                <div className="sidebar-user-popup-avatar">{username.slice(0, 1).toUpperCase()}</div>
                <div>
                  <div className="sidebar-user-popup-name">{username}</div>
                  <div className="sidebar-user-popup-role">{ROLE_LABEL[role] ?? '管理员'}</div>
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
            </div>
          </div>
        </aside>

        <div className="main-content">
          <header className="page-header">
            <div>
              <div className="page-title">{title}</div>
              {subtitle && <div className="page-subtitle">{subtitle}</div>}
            </div>
            {actions && <div className="header-actions">{actions}</div>}
          </header>
          <main className="page-body">{children}</main>
        </div>
      </div>

      {showChangePwd  && <ChangePasswordModal onClose={() => setShowChangePwd(false)} />}
      {showBindEmail  && <BindEmailModal      onClose={() => setShowBindEmail(false)} />}

      {showLogoutConfirm && (
        <Confirm
          title="退出登录"
          message="确认退出管理台？退出后需重新登录。"
          loading={false}
          onConfirm={doLogout}
          onCancel={() => setShowLogoutConfirm(false)}
        />
      )}
    </>
  )
}
