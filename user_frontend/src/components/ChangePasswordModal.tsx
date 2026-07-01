import { useState, type FormEvent } from 'react'
import { AlertCircle, Check, Eye, EyeOff } from 'lucide-react'
import { changePassword, clearAuthAndRedirect } from '../api'
import { useToast } from '../hooks/useToast'
import { Modal } from './Modal'

const rules = (pwd: string) => [
  { label: '长度为 8-16 个字符', ok: pwd.length >= 8 && pwd.length <= 16 },
  { label: '不能包含空格', ok: pwd.length > 0 && !pwd.includes(' ') },
  { label: '需包含大、小写字母和数字', ok: /[A-Z]/.test(pwd) && /[a-z]/.test(pwd) && /\d/.test(pwd) },
]

function Strength({ pwd, focused }: { pwd: string; focused: boolean }) {
  const checks = rules(pwd)
  const strength = checks.filter(r => r.ok).length
  const colors = ['', '#EF4444', '#F59E0B', '#22C55E']
  const labels = ['', '低', '中', '高']
  if (!pwd) return null
  return <div style={{ marginTop: 6 }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
      <span style={{ fontSize: 12, color: 'var(--text-3)' }}>密码强度：</span>
      <span style={{ fontSize: 12, fontWeight: 600, color: colors[strength] }}>{labels[strength]}</span>
    </div>
    <div style={{ display: 'flex', gap: 3, height: 4, marginBottom: 6 }}>
      {[1, 2, 3].map(i => <div key={i} style={{ flex: 1, borderRadius: 2, background: strength >= i ? colors[strength] : 'var(--border)', transition: 'background .2s' }} />)}
    </div>
    {focused && <div>
      <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 4 }}>密码要求：</div>
      {checks.map(r => <div key={r.label} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
        {r.ok ? <Check style={{ width: 13, height: 13, color: '#22C55E', flexShrink: 0 }} /> : <AlertCircle style={{ width: 13, height: 13, color: '#EF4444', flexShrink: 0 }} />}
        <span style={{ fontSize: 12, color: r.ok ? 'var(--text-2)' : '#EF4444' }}>{r.label}</span>
      </div>)}
    </div>}
    {!focused && !checks.every(r => r.ok) && <div style={{ fontSize: 12, color: '#EF4444', display: 'flex', alignItems: 'center', gap: 4 }}>
      <AlertCircle style={{ width: 13, height: 13 }} />密码不符合规范
    </div>}
  </div>
}

export function ChangePasswordModal({ onClose }: { onClose: () => void }) {
  const { toast } = useToast()
  const [oldPwd, setOldPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showOld, setShowOld] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [focused, setFocused] = useState(false)
  const [loading, setLoading] = useState(false)
  const allPass = rules(newPwd).every(r => r.ok)
  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!allPass) { toast('新密码不符合规范', 'error'); return }
    if (newPwd === oldPwd) { toast('新密码不能与旧密码相同', 'error'); return }
    if (newPwd !== confirm) { toast('两次密码不一致', 'error'); return }
    setLoading(true)
    try { await changePassword(oldPwd, newPwd); clearAuthAndRedirect() }
    catch (err: any) { toast(err.message, 'error') }
    finally { setLoading(false) }
  }
  const eyeStyle = { position: 'absolute' as const, right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: 0 }
  return <Modal title="修改密码" onClose={onClose} footer={<>
    <button className="btn btn-ghost" onClick={onClose} disabled={loading}>取消</button>
    <button className="btn btn-primary" onClick={submit as any} disabled={loading || !oldPwd || !allPass || !confirm || newPwd !== confirm}>{loading ? '修改中…' : '确认修改'}</button>
  </>}><form onSubmit={submit}>
    <div className="form-group"><label className="form-label">当前密码</label><div style={{ position: 'relative' }}>
      <input className="form-input" type={showOld ? 'text' : 'password'} autoComplete="current-password" placeholder="输入当前密码" value={oldPwd} onChange={e => setOldPwd(e.target.value)} style={{ paddingRight: 40 }} autoFocus />
      <button type="button" onClick={() => setShowOld(p => !p)} style={eyeStyle}>{showOld ? <EyeOff style={{ width: 15, height: 15 }} /> : <Eye style={{ width: 15, height: 15 }} />}</button>
    </div></div>
    <div className="form-group"><label className="form-label">新密码</label><div style={{ position: 'relative' }}>
      <input className="form-input" type={showNew ? 'text' : 'password'} autoComplete="new-password" placeholder="8-16 位，含大小写字母和数字" value={newPwd} onChange={e => setNewPwd(e.target.value)} onFocus={() => setFocused(true)} onBlur={() => setFocused(false)} style={{ paddingRight: 40 }} />
      <button type="button" onClick={() => setShowNew(p => !p)} style={eyeStyle}>{showNew ? <EyeOff style={{ width: 15, height: 15 }} /> : <Eye style={{ width: 15, height: 15 }} />}</button>
    </div><Strength pwd={newPwd} focused={focused} /></div>
    <div className="form-group" style={{ marginBottom: 0 }}><label className="form-label">确认新密码</label>
      <input className="form-input" type="password" autoComplete="new-password" placeholder="再次输入新密码" value={confirm} onChange={e => setConfirm(e.target.value)} />
      {confirm && newPwd !== confirm && <div style={{ fontSize: 12, color: '#EF4444', marginTop: 4 }}>两次密码不一致</div>}
    </div>
  </form></Modal>
}
