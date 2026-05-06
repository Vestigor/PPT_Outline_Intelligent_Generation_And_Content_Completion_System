import React, { useState, useRef } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Presentation, Eye, EyeOff, CheckCircle2, XCircle } from 'lucide-react'
import { register, sendEmailCode } from '../api'

// ── Password strength helpers ─────────────────────────────────────────────
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
          <span style={{ fontSize: 12, fontWeight: 600, color: colors[strength] }}>
            {labels[strength]}
          </span>
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

function PwdRuleList({ rules, focused }: { rules: PwdRule[]; focused: boolean }) {
  if (!focused) return null
  return (
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
  )
}

// ── Email code countdown ──────────────────────────────────────────────────

export function Register() {
  const navigate  = useNavigate()

  const [username,     setUsername]     = useState('')
  const [email,        setEmail]        = useState('')
  const [code,         setCode]         = useState('')
  const [password,     setPassword]     = useState('')
  const [confirm,      setConfirm]      = useState('')
  const [showPwd,      setShowPwd]      = useState(false)
  const [showConfirm,  setShowConfirm]  = useState(false)
  const [pwdFocused,   setPwdFocused]   = useState(false)
  const [error,        setError]        = useState('')
  const [loading,      setLoading]      = useState(false)
  const [codeSending,  setCodeSending]  = useState(false)
  const [countdown,    setCountdown]    = useState(0)

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const rules    = getPwdRules(password)
  const strength = pwdStrength(password)
  const allPass  = rules.every(r => r.ok)

  async function handleSendCode() {
    const emailTrimmed = email.trim()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailTrimmed)) {
      setError('请输入有效的邮箱地址')
      return
    }
    setError('')
    setCodeSending(true)
    try {
      await sendEmailCode(emailTrimmed, 'register')
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
    if (!allPass)              { setError('密码不符合规范'); return }
    if (password !== confirm)  { setError('两次密码不一致'); return }
    if (!code.trim())          { setError('请输入验证码'); return }
    setError('')
    setLoading(true)
    try {
      await register(username.trim(), password, email.trim(), code.trim())
      navigate('/login', { state: { registered: true } })
    } catch (err: any) {
      setError(err.message ?? '注册失败，请重试')
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
            <div className="login-title">创建账户</div>
            <div className="login-sub">PPT 智能生成系统</div>
          </div>
        </div>

        {error && <div className="login-error">{error}</div>}

        <form onSubmit={submit}>
          {/* Username */}
          <div className="form-group">
            <label className="form-label">用户名</label>
            <input
              className="form-input"
              name="username"
              autoComplete="username"
              placeholder="3-64 位字母、数字或下划线"
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoFocus required
            />
          </div>

          {/* Email + send code */}
          <div className="form-group">
            <label className="form-label">邮箱地址</label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                className="form-input"
                type="email"
                name="email"
                autoComplete="email"
                placeholder="请输入邮箱"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                style={{ flex: 1 }}
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

          {/* Verification code */}
          <div className="form-group">
            <label className="form-label">邮箱验证码</label>
            <input
              className="form-input"
              name="email-code"
              autoComplete="one-time-code"
              placeholder="6 位验证码"
              maxLength={6}
              value={code}
              onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              required
            />
          </div>

          {/* Password */}
          <div className="form-group">
            <label className="form-label">密码</label>
            <div style={{ position: 'relative' }}>
              <input
                className="form-input"
                type={showPwd ? 'text' : 'password'}
                name="new-password"
                autoComplete="new-password"
                placeholder="8-16 位，含大小写字母和数字"
                value={password}
                onChange={e => setPassword(e.target.value)}
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
            {password && <PasswordStrengthBar strength={strength} />}
            <PwdRuleList rules={rules} focused={pwdFocused} />
            {!pwdFocused && password && !allPass && (
              <div style={{ fontSize: 12, color: '#EF4444', marginTop: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                <XCircle style={{ width: 13, height: 13 }} />密码不符合规范
              </div>
            )}
            {!pwdFocused && password && allPass && (
              <div style={{ fontSize: 12, color: '#22C55E', marginTop: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                <CheckCircle2 style={{ width: 13, height: 13 }} />密码通过
              </div>
            )}
          </div>

          {/* Confirm password */}
          <div className="form-group">
            <label className="form-label">确认密码</label>
            <div style={{ position: 'relative' }}>
              <input
                className="form-input"
                type={showConfirm ? 'text' : 'password'}
                name="confirm-password"
                autoComplete="new-password"
                placeholder="再次输入密码"
                value={confirm}
                onChange={e => setConfirm(e.target.value)}
                style={{ paddingRight: 40 }}
                required
              />
              <button
                type="button"
                onClick={() => setShowConfirm(p => !p)}
                style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: 0 }}
              >
                {showConfirm ? <EyeOff style={{ width: 16, height: 16 }} /> : <Eye style={{ width: 16, height: 16 }} />}
              </button>
            </div>
            {confirm && password !== confirm && (
              <div style={{ fontSize: 12, color: '#EF4444', marginTop: 4 }}>两次密码不一致</div>
            )}
          </div>

          <button
            className="btn btn-primary w-full"
            style={{ marginTop: 8, justifyContent: 'center', padding: '10px 16px' }}
            type="submit" disabled={loading}
          >
            {loading ? '注册中…' : '注册账户'}
          </button>
        </form>

        <p style={{ textAlign: 'center', marginTop: 20, color: 'var(--text-3)', fontSize: 12.5 }}>
          已有账户？{' '}
          <Link to="/login" style={{ color: 'var(--accent)', fontWeight: 600 }}>登录</Link>
        </p>
      </div>
    </div>
  )
}
