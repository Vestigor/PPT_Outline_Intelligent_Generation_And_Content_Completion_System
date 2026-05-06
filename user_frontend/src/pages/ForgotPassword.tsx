import { useState, useRef } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Presentation, Eye, EyeOff, CheckCircle2, XCircle } from 'lucide-react'
import { sendEmailCode, forgotPassword } from '../api'

interface PwdRule { label: string; ok: boolean }

function getPwdRules(pwd: string): PwdRule[] {
  return [
    { label: '长度为 8-16 个字符',      ok: pwd.length >= 8 && pwd.length <= 16 },
    { label: '不能包含空格',             ok: pwd.length > 0 && !pwd.includes(' ') },
    { label: '需包含大、小写字母和数字', ok: /[A-Z]/.test(pwd) && /[a-z]/.test(pwd) && /\d/.test(pwd) },
  ]
}

function pwdStrength(pwd: string): number {
  return getPwdRules(pwd).filter(r => r.ok).length
}

function PasswordStrengthBar({ strength }: { strength: number }) {
  const labels = ['', '低', '中', '高']
  const colors = ['', '#EF4444', '#F59E0B', '#22C55E']
  return (
    <div style={{ marginTop: 6 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <span style={{ fontSize: 12, color: 'var(--text-3)' }}>密码强度：</span>
        {strength > 0 && (
          <span style={{ fontSize: 12, fontWeight: 600, color: colors[strength] }}>{labels[strength]}</span>
        )}
      </div>
      <div style={{ display: 'flex', gap: 3, height: 4 }}>
        {[1, 2, 3].map(i => (
          <div key={i} style={{
            flex: 1, borderRadius: 2,
            background: strength >= i ? colors[strength] : 'var(--border)',
            transition: 'background .2s',
          }} />
        ))}
      </div>
    </div>
  )
}

export function ForgotPassword() {
  const navigate = useNavigate()

  const [email,       setEmail]       = useState('')
  const [code,        setCode]        = useState('')
  const [newPwd,      setNewPwd]      = useState('')
  const [showPwd,     setShowPwd]     = useState(false)
  const [pwdFocused,  setPwdFocused]  = useState(false)
  const [error,       setError]       = useState('')
  const [loading,     setLoading]     = useState(false)
  const [codeSending, setCodeSending] = useState(false)
  const [countdown,   setCountdown]   = useState(0)

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const rules    = getPwdRules(newPwd)
  const allPass  = rules.every(r => r.ok)
  const strength = pwdStrength(newPwd)

  async function handleSendCode() {
    const emailTrimmed = email.trim()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailTrimmed)) {
      setError('请输入有效的邮箱地址')
      return
    }
    setError('')
    setCodeSending(true)
    try {
      await sendEmailCode(emailTrimmed, 'reset_password')
      setCountdown(60)
      timerRef.current = setInterval(() => {
        setCountdown(c => {
          if (c <= 1) { clearInterval(timerRef.current!); return 0 }
          return c - 1
        })
      }, 1000)
    } catch (err: any) {
      setError(err.message ?? '发送失败，请重试')
    } finally {
      setCodeSending(false)
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!allPass) { setError('密码不符合规范'); return }
    setError('')
    setLoading(true)
    try {
      await forgotPassword(email.trim(), code.trim(), newPwd)
      navigate('/login', { state: { registered: false, pwdReset: true } })
    } catch (err: any) {
      setError(err.message ?? '重置失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card" style={{ maxWidth: 420 }}>
        <div className="login-logo">
          <div className="login-logo-mark"><Presentation /></div>
          <div>
            <div className="login-title">重置密码</div>
            <div className="login-sub">PPT 智能生成系统</div>
          </div>
        </div>

        {error && <div className="login-error">{error}</div>}

        <form onSubmit={submit}>
          {/* Email */}
          <div className="form-group">
            <label className="form-label">注册邮箱</label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                className="form-input"
                type="email"
                name="email"
                autoComplete="email"
                placeholder="请输入注册时使用的邮箱"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                style={{ flex: 1 }}
                autoFocus
              />
              <button
                type="button"
                className="btn btn-ghost"
                style={{ flexShrink: 0, padding: '0 12px', fontSize: 13 }}
                disabled={codeSending || countdown > 0}
                onClick={handleSendCode}
              >
                {codeSending ? '发送中…' : countdown > 0 ? `${countdown}s` : '获取验证码'}
              </button>
            </div>
          </div>

          {/* Code */}
          <div className="form-group">
            <label className="form-label">验证码</label>
            <input
              className="form-input"
              name="reset-code"
              autoComplete="one-time-code"
              placeholder="6 位验证码"
              maxLength={6}
              value={code}
              onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              required
            />
          </div>

          {/* New password */}
          <div className="form-group">
            <label className="form-label">新密码</label>
            <div style={{ position: 'relative' }}>
              <input
                className="form-input"
                type={showPwd ? 'text' : 'password'}
                name="new-password"
                autoComplete="new-password"
                placeholder="8-16 位，含大小写字母和数字"
                value={newPwd}
                onChange={e => setNewPwd(e.target.value)}
                onFocus={() => setPwdFocused(true)}
                onBlur={() => setPwdFocused(false)}
                style={{ paddingRight: 40 }}
                required
              />
              <button
                type="button"
                onClick={() => setShowPwd(p => !p)}
                style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: 0 }}
              >
                {showPwd ? <EyeOff style={{ width: 16, height: 16 }} /> : <Eye style={{ width: 16, height: 16 }} />}
              </button>
            </div>
            {newPwd && <PasswordStrengthBar strength={strength} />}
            {pwdFocused && newPwd && (
              <div style={{ marginTop: 8 }}>
                <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 4 }}>密码要求：</div>
                {rules.map(r => (
                  <div key={r.label} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                    {r.ok
                      ? <CheckCircle2 style={{ width: 14, height: 14, color: '#22C55E', flexShrink: 0 }} />
                      : <XCircle     style={{ width: 14, height: 14, color: '#EF4444', flexShrink: 0 }} />}
                    <span style={{ fontSize: 12, color: r.ok ? 'var(--text-2)' : '#EF4444' }}>{r.label}</span>
                  </div>
                ))}
              </div>
            )}
            {!pwdFocused && newPwd && !allPass && (
              <div style={{ fontSize: 12, color: '#EF4444', marginTop: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                <XCircle style={{ width: 13, height: 13 }} />密码不符合规范
              </div>
            )}
            {!pwdFocused && newPwd && allPass && (
              <div style={{ fontSize: 12, color: '#22C55E', marginTop: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                <CheckCircle2 style={{ width: 13, height: 13 }} />密码通过
              </div>
            )}
          </div>

          <button
            className="btn btn-primary w-full"
            style={{ marginTop: 8, justifyContent: 'center', padding: '10px 16px' }}
            type="submit" disabled={loading || !allPass}
          >
            {loading ? '重置中…' : '重置密码'}
          </button>
        </form>

        <p style={{ textAlign: 'center', marginTop: 20, color: 'var(--text-3)', fontSize: 12.5 }}>
          想起密码了？{' '}
          <Link to="/login" style={{ color: 'var(--accent)', fontWeight: 600 }}>返回登录</Link>
        </p>
      </div>
    </div>
  )
}
