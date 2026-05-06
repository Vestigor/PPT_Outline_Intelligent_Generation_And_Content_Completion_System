import { useEffect, useState, useCallback, useRef } from 'react'
import { UserPlus, Search, RefreshCw, Trash2, KeyRound, Power, ShieldAlert } from 'lucide-react'
import { Layout } from '../components/Layout'
import { Modal, Confirm } from '../components/Modal'
import { useToast } from '../hooks/useToast'
import {
  listUsers, createUser, deleteUser, toggleUserStatus, resetPassword, getMe,
  type UserResponse, type PageResult,
} from '../api'

const PAGE_SIZE = 15

const ROLE_LABEL: Record<string, string> = {
  super_admin: '超级管理员',
  admin: '管理员',
  user: '普通用户',
}
const ROLE_BADGE: Record<string, string> = {
  super_admin: 'badge-super',
  admin: 'badge-warning',
  user: 'badge-neutral',
}

export function Users() {
  const { toast } = useToast()
  const [data,    setData]    = useState<PageResult<UserResponse> | null>(null)
  const [loading, setLoading] = useState(true)
  const [page,    setPage]    = useState(1)
  const [search,  setSearch]  = useState('')
  const [myRole,  setMyRole]  = useState<string>('admin')

  const [showCreate,      setShowCreate]      = useState(false)
  const [showResetPwd,    setShowResetPwd]    = useState<UserResponse | null>(null)
  const [confirmDelete,   setConfirmDelete]   = useState<UserResponse | null>(null)
  const [confirmToggle,   setConfirmToggle]   = useState<UserResponse | null>(null)
  const [actionLoading,   setActionLoading]   = useState(false)

  // 获取当前用户身份
  useEffect(() => {
    getMe().then(me => setMyRole(me.role)).catch(() => {})
  }, [])

  // Keep toast in a ref so load's identity only changes when page/search change,
  // preventing spurious reloads when modals open.
  const toastRef = useRef(toast)
  toastRef.current = toast

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await listUsers(page, PAGE_SIZE, search || undefined)
      setData(res)
    } catch (e: any) {
      if (e.message !== '_auth_redirect') toastRef.current(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }, [page, search])

  useEffect(() => { load() }, [load])

  // 判断当前用户是否可以操作目标用户
  function canManage(target: UserResponse) {
    if (target.role === 'super_admin') return false
    if (myRole === 'admin' && target.role === 'admin') return false
    return true
  }

  async function handleCreate(username: string, password: string, role: string) {
    setActionLoading(true)
    try {
      await createUser(username, password, role)
      toast('用户创建成功', 'success')
      setShowCreate(false)
      load()
    } catch (e: any) {
      if (e.message !== '_auth_redirect') toast(e.message, 'error')
    } finally {
      setActionLoading(false)
    }
  }

  async function handleDelete() {
    if (!confirmDelete) return
    setActionLoading(true)
    try {
      await deleteUser(confirmDelete.id)
      toast('用户已删除', 'success')
      setConfirmDelete(null)
      load()
    } catch (e: any) {
      if (e.message !== '_auth_redirect') toast(e.message, 'error')
    } finally {
      setActionLoading(false)
    }
  }

  async function handleToggle() {
    if (!confirmToggle) return
    setActionLoading(true)
    try {
      await toggleUserStatus(confirmToggle.id)
      toast(`用户已${confirmToggle.is_active ? '禁用' : '启用'}`, 'success')
      setConfirmToggle(null)
      load()
    } catch (e: any) {
      if (e.message !== '_auth_redirect') toast(e.message, 'error')
    } finally {
      setActionLoading(false)
    }
  }

  async function handleResetPwd(user: UserResponse, newPwd: string) {
    setActionLoading(true)
    try {
      await resetPassword(user.id, newPwd)
      toast('密码已重置', 'success')
      setShowResetPwd(null)
    } catch (e: any) {
      if (e.message !== '_auth_redirect') toast(e.message, 'error')
    } finally {
      setActionLoading(false)
    }
  }

  const total = data?.total ?? 0
  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <Layout
      title="用户管理"
      subtitle={`共 ${total} 名用户`}
      actions={
        <>
          <div className="search-bar">
            <Search />
            <input
              className="form-input"
              placeholder="搜索用户名…"
              autoComplete="off"
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1) }}
            />
          </div>
          <button className="btn-icon" onClick={load} title="刷新"><RefreshCw /></button>
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
            <UserPlus />新建用户
          </button>
        </>
      }
    >
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>用户名</th>
              <th>邮箱</th>
              <th>角色</th>
              <th>状态</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {loading && !data && (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-3)', padding: 40 }}>
                  加载中…
                </td>
              </tr>
            )}
            {!loading && data?.items.length === 0 && (
              <tr>
                <td colSpan={7}>
                  <div className="empty-state"><Search /><p>未找到用户</p></div>
                </td>
              </tr>
            )}
            {data?.items.map(u => (
              <tr key={u.id}>
                <td className="td-mono">{u.id}</td>
                <td style={{ fontWeight: 500 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    {u.role === 'super_admin' && (
                      <ShieldAlert style={{ width: 14, height: 14, color: 'var(--accent)' }} />
                    )}
                    {u.username}
                  </div>
                </td>
                <td className="td-mono" style={{ fontSize: 12 }}>
                  {u.email
                    ? <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        {u.email}
                        {u.is_email_verified && (
                          <span className="badge badge-success" style={{ fontSize: 10, padding: '1px 5px' }}>已验证</span>
                        )}
                      </span>
                    : <span style={{ color: 'var(--text-3)' }}>—</span>
                  }
                </td>
                <td>
                  <span className={`badge ${ROLE_BADGE[u.role] ?? 'badge-neutral'}`}>
                    {ROLE_LABEL[u.role] ?? u.role}
                  </span>
                </td>
                <td>
                  <span className={`badge ${u.is_active ? 'badge-success' : 'badge-error'}`}>
                    {u.is_active ? '正常' : '禁用'}
                  </span>
                </td>
                <td className="td-mono">{new Date(u.created_at).toLocaleString('zh-CN')}</td>
                <td>
                  <div className="td-actions">
                    {canManage(u) ? (
                      <>
                        <button className="btn btn-sm btn-ghost" onClick={() => setShowResetPwd(u)}>
                          <KeyRound style={{ width: 13, height: 13 }} />重置密码
                        </button>
                        <button
                          className={`btn btn-sm ${u.is_active ? 'btn-ghost' : 'btn-accent'}`}
                          onClick={() => setConfirmToggle(u)}
                        >
                          <Power style={{ width: 13, height: 13 }} />
                          {u.is_active ? '禁用' : '启用'}
                        </button>
                        <button
                          className="btn-icon"
                          onClick={() => setConfirmDelete(u)}
                          style={{ color: 'var(--error)' }}
                        >
                          <Trash2 />
                        </button>
                      </>
                    ) : (
                      <span style={{ fontSize: 12, color: 'var(--text-3)', padding: '0 4px' }}>
                        {u.role === 'super_admin' ? '受保护' : '无权限'}
                      </span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {totalPages > 1 && (
          <div className="pagination">
            <span className="pagination-info">第 {page} / {totalPages} 页，共 {total} 条</span>
            <div className="pagination-btns">
              <button className="btn btn-sm btn-ghost" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>上一页</button>
              <button className="btn btn-sm btn-ghost" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>下一页</button>
            </div>
          </div>
        )}
      </div>

      {showCreate && (
        <CreateUserModal
          myRole={myRole}
          loading={actionLoading}
          onClose={() => setShowCreate(false)}
          onSubmit={handleCreate}
        />
      )}
      {showResetPwd && (
        <ResetPasswordModal
          user={showResetPwd}
          loading={actionLoading}
          onClose={() => setShowResetPwd(null)}
          onSubmit={(pwd) => handleResetPwd(showResetPwd, pwd)}
        />
      )}
      {confirmDelete && (
        <Confirm
          title="删除用户"
          message={`确认删除用户「${confirmDelete.username}」？此操作不可撤销，该用户的所有会话和配置将一并删除。`}
          danger
          loading={actionLoading}
          onConfirm={handleDelete}
          onCancel={() => setConfirmDelete(null)}
        />
      )}
      {confirmToggle && (
        <Confirm
          title={confirmToggle.is_active ? '禁用用户' : '启用用户'}
          message={`确认${confirmToggle.is_active ? '禁用' : '启用'}用户「${confirmToggle.username}」？`}
          loading={actionLoading}
          onConfirm={handleToggle}
          onCancel={() => setConfirmToggle(null)}
        />
      )}
    </Layout>
  )
}

function CreateUserModal({ myRole, loading, onClose, onSubmit }: {
  myRole: string
  loading: boolean
  onClose: () => void
  onSubmit: (username: string, password: string, role: string) => void
}) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role,     setRole]     = useState('user')

  return (
    <Modal
      title="新建用户"
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={loading}>取消</button>
          <button
            className="btn btn-primary"
            disabled={loading || !username || !password}
            onClick={() => onSubmit(username, password, role)}
          >
            {loading ? '创建中…' : '创建用户'}
          </button>
        </>
      }
    >
      <div className="form-group">
        <label className="form-label">用户名</label>
        <input className="form-input" placeholder="输入用户名" value={username} onChange={e => setUsername(e.target.value)} autoFocus />
      </div>
      <div className="form-group">
        <label className="form-label">初始密码</label>
        <input className="form-input" type="password" placeholder="输入初始密码" value={password} onChange={e => setPassword(e.target.value)} />
      </div>
      <div className="form-group">
        <label className="form-label">角色</label>
        <select className="form-input form-select" value={role} onChange={e => setRole(e.target.value)}>
          <option value="user">普通用户</option>
          {myRole === 'super_admin' && <option value="admin">管理员</option>}
        </select>
      </div>
    </Modal>
  )
}

function ResetPasswordModal({ user, loading, onClose, onSubmit }: {
  user: UserResponse
  loading: boolean
  onClose: () => void
  onSubmit: (pwd: string) => void
}) {
  const [pwd, setPwd] = useState('')

  return (
    <Modal
      title={`重置密码 · ${user.username}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={loading}>取消</button>
          <button className="btn btn-primary" disabled={loading || !pwd} onClick={() => onSubmit(pwd)}>
            {loading ? '重置中…' : '确认重置'}
          </button>
        </>
      }
    >
      <div className="form-group">
        <label className="form-label">新密码</label>
        <input
          className="form-input"
          type="password"
          placeholder="输入新密码"
          autoComplete="new-password"
          value={pwd}
          onChange={e => setPwd(e.target.value)}
          autoFocus
        />
        <div className="form-hint">重置后，该用户下次登录须使用新密码。</div>
      </div>
    </Modal>
  )
}

