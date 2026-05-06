import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Presentation, Eye, EyeOff, Check, AlertCircle } from 'lucide-react'
import { login, getMe, sendEmailCode, forgotPassword } from '../api'

// ── Password strength helpers ────────────────────────────────────────────
interface PwdRule { label: string; ok: boolean }
function getPwdRules(pwd: string): PwdRule[] {
  return [
    { label: '长度为 8-16 个字符',      ok: pwd.length >= 8 && pwd.length <= 16 },
    { label: '不能包含空格',             ok: pwd.length > 0 && !pwd.includes(' ') },
    { label: '需包含大、小写字母和数字', ok: /[A-Z]/.test(pwd) && /[a-z]/.test(pwd) && /\d/.test(pwd) },
  ]
}

// ── Forgot-password form (three fields: email / code / new password) ─────
function ForgotPasswordForm({ onBack }: { onBack: () => void }) {
  const [email,     setEmail]     = useState('')
  const [code,      setCode]      = useState('')
  const [newPwd,    setNewPwd]    = useState('')
  const [showPwd,   setShowPwd]   = useState(false)
  const [sending,   setSending]   = useState(false)
  const [countdown, setCountdown] = useState(0)
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState('')
  const [done,      setDone]      = useState(false)

  const rules   = getPwdRules(newPwd)
  const allPass = rules.every(r => r.ok)

  async function handleSendCode() {
    if (!email) { setError('请输入邮箱地址'); return }
    setError('')
    setSending(true)
    try {
      await sendEmailCode(email, 'reset_password')
      setCountdown(60)
      const timer = setInterval(() => {
        setCountdown(c => { if (c <= 1) { clearInterval(timer); return 0 } return c - 1 })
      }, 1000)
    } catch (err: any) {
      setError(err.message ?? '发送失败')
    } finally {
      setSending(false)
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!email || !code || !newPwd) { setError('请填写所有字段'); return }
    if (!allPass) { setError('新密码不符合规范'); return }
    setError('')
    setLoading(true)
    try {
      await forgotPassword(email, code, newPwd)
      setDone(true)
    } catch (err: any) {
      setError(err.message ?? '重置失败')
    } finally {
      setLoading(false)
    }
  }

  if (done) return (
    <div style={{ textAlign: 'center' }}>
      <Check style={{ width: 40, height: 40, color: '#22C55E', margin: '0 auto 12px' }} />
      <div style={{ fontWeight: 600, marginBottom: 8 }}>密码重置成功</div>
      <div style={{ fontSize: 13, color: 'var(--text-3)', marginBottom: 24 }}>请使用新密码登录</div>
      <button className="btn btn-primary w-full" style={{ justifyContent: 'center', padding: '10px 16px' }}
        onClick={onBack}>
        返回登录
      </button>
    </div>
  )

  return (
    <form onSubmit={handleSubmit} autoComplete="on">
      {error && <div className="login-error">{error}</div>}
      <div className="form-group">
        <label className="form-label">注册邮箱</label>
        <input className="form-input" type="email" autoComplete="email"
          placeholder="请输入账号绑定的邮箱" value={email}
          onChange={e => setEmail(e.target.value)} autoFocus required />
      </div>
      <div className="form-group">
        <label className="form-label">验证码</label>
        <div style={{ display: 'flex', gap: 8 }}>
          <input className="form-input" type="text" autoComplete="one-time-code"
            placeholder="输入 6 位验证码" maxLength={6}
            value={code} onChange={e => setCode(e.target.value)}
            style={{ flex: 1 }} required />
          <button type="button" className="btn btn-ghost"
            style={{ flexShrink: 0, padding: '0 12px', fontSize: 12 }}
            disabled={sending || countdown > 0 || !email}
            onClick={handleSendCode}>
            {countdown > 0 ? `${countdown}s` : sending ? '发送中…' : '发送验证码'}
          </button>
        </div>
      </div>
      <div className="form-group">
        <label className="form-label">新密码</label>
        <div style={{ position: 'relative' }}>
          <input className="form-input" type={showPwd ? 'text' : 'password'}
            autoComplete="new-password" placeholder="8-16 位，含大小写字母和数字"
            value={newPwd} onChange={e => setNewPwd(e.target.value)}
            style={{ paddingRight: 40 }} required />
          <button type="button" onClick={() => setShowPwd(p => !p)}
            style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: 0 }}>
            {showPwd ? <EyeOff style={{ width: 16, height: 16 }} /> : <Eye style={{ width: 16, height: 16 }} />}
          </button>
        </div>
        {newPwd && (
          <div style={{ marginTop: 6 }}>
            {rules.map(r => (
              <div key={r.label} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                {r.ok
                  ? <Check       style={{ width: 12, height: 12, color: '#22C55E', flexShrink: 0 }} />
                  : <AlertCircle style={{ width: 12, height: 12, color: '#EF4444', flexShrink: 0 }} />}
                <span style={{ fontSize: 12, color: r.ok ? 'var(--text-2)' : '#EF4444' }}>{r.label}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <button className="btn btn-primary w-full"
        style={{ marginTop: 8, justifyContent: 'center', padding: '10px 16px' }}
        type="submit" disabled={loading || !allPass}>
        {loading ? '重置中…' : '重置密码'}
      </button>
      <button type="button" onClick={onBack}
        style={{ display: 'block', width: '100%', marginTop: 10, background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: 'var(--text-3)', textAlign: 'center' }}>
        ← 返回登录
      </button>
    </form>
  )
}

// ── Login page ────────────────────────────────────────────────────────────
export function Login() {
  const navigate  = useNavigate()
  const [mode,     setMode]     = useState<'login' | 'forgot'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPwd,  setShowPwd]  = useState(false)
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await login(username, password)
      localStorage.setItem('admin_token',         res.access_token)
      localStorage.setItem('admin_refresh_token', res.refresh_token)
      localStorage.setItem('admin_username',       res.username)
      const me = await getMe()
      localStorage.setItem('admin_role', me.role)
      navigate('/')
    } catch (err: any) {
      setError(err.message ?? '登录失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">
          <div className="login-logo-mark"><Presentation /></div>
          <div>
            <div className="login-title">{mode === 'forgot' ? '找回密码' : '管理后台'}</div>
            <div className="login-sub">PPT 智能生成系统</div>
          </div>
        </div>

        {mode === 'forgot' ? (
          <ForgotPasswordForm onBack={() => { setMode('login'); setError('') }} />
        ) : (
          <>
            {error && <div className="login-error">{error}</div>}

            <form onSubmit={submit} autoComplete="on">
              <div className="form-group">
                <label className="form-label">用户名</label>
                <input
                  className="form-input"
                  name="username"
                  autoComplete="username"
                  placeholder="请输入管理员用户名"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  autoFocus
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">密码</label>
                <div style={{ position: 'relative' }}>
                  <input
                    className="form-input"
                    type={showPwd ? 'text' : 'password'}
                    name="password"
                    autoComplete="current-password"
                    placeholder="请输入密码"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    style={{ paddingRight: 40 }}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPwd(p => !p)}
                    style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: 0 }}
                  >
                    {showPwd
                      ? <EyeOff style={{ width: 16, height: 16 }} />
                      : <Eye    style={{ width: 16, height: 16 }} />}
                  </button>
                </div>
              </div>
              <button
                className="btn btn-primary w-full"
                style={{ marginTop: 8, justifyContent: 'center', padding: '10px 16px' }}
                type="submit"
                disabled={loading}
              >
                {loading ? '登录中…' : '登录'}
              </button>
            </form>

            <div style={{ textAlign: 'center', marginTop: 14 }}>
              <button
                type="button"
                onClick={() => { setMode('forgot'); setError('') }}
                style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, color: 'var(--accent)', textDecoration: 'underline' }}
              >
                忘记密码？
              </button>
            </div>

            <p className="text-sm" style={{ textAlign: 'center', marginTop: 12, color: 'var(--text-3)', fontSize: 12 }}>
              仅限管理员账号登录
            </p>
          </>
        )}
      </div>
    </div>
  )
}
