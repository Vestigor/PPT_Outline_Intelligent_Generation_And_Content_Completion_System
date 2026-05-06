import { useState } from 'react'
import { useNavigate, Link, useLocation } from 'react-router-dom'
import { Presentation, Eye, EyeOff } from 'lucide-react'
import { login } from '../api'

export function Login() {
  const navigate  = useNavigate()
  const location  = useLocation()
  const registered = (location.state as any)?.registered === true

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
      localStorage.setItem('token',         res.access_token)
      localStorage.setItem('refresh_token', res.refresh_token)
      localStorage.setItem('username',      res.username)
      navigate('/', { replace: true })
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
            <div className="login-title">PPT 智能生成</div>
            <div className="login-sub">AI 驱动的内容创作工具</div>
          </div>
        </div>

        {registered && (
          <div className="login-success">注册成功，请登录</div>
        )}
        {error && <div className="login-error">{error}</div>}

        <form onSubmit={submit}>
          <div className="form-group">
            <label className="form-label">用户名</label>
            <input
              className="form-input"
              name="username"
              autoComplete="username"
              placeholder="请输入用户名"
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoFocus required
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
                {showPwd ? <EyeOff style={{ width: 16, height: 16 }} /> : <Eye style={{ width: 16, height: 16 }} />}
              </button>
            </div>
            <div style={{ textAlign: 'right', marginTop: 4 }}>
              <Link to="/forgot-password" style={{ fontSize: 12, color: 'var(--accent)' }}>忘记密码？</Link>
            </div>
          </div>
          <button
            className="btn btn-primary w-full"
            style={{ marginTop: 8, justifyContent: 'center', padding: '10px 16px' }}
            type="submit" disabled={loading}
          >
            {loading ? '登录中…' : '登录'}
          </button>
        </form>

        <p style={{ textAlign: 'center', marginTop: 20, color: 'var(--text-3)', fontSize: 12.5 }}>
          还没有账户？{' '}
          <Link to="/register" style={{ color: 'var(--accent)', fontWeight: 600 }}>注册</Link>
        </p>
      </div>
    </div>
  )
}
