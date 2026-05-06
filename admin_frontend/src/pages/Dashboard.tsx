import { useEffect, useState } from 'react'
import { Users, Cpu, FileText, Activity } from 'lucide-react'
import { Layout } from '../components/Layout'
import { listUsers, listProviders } from '../api'

interface Stats {
  users: number
  providers: number
  activeModels: number
}

export function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([listUsers(1, 1), listProviders()])
      .then(([usersPage, providers]) => {
        const activeModels = providers.reduce(
          (sum, p) => sum + p.models.filter(m => m.effective_is_active).length,
          0,
        )
        setStats({ users: usersPage.total, providers: providers.length, activeModels })
      })
      .catch((e: any) => { if (e.message !== '_auth_redirect') setStats({ users: 0, providers: 0, activeModels: 0 }) })
      .finally(() => setLoading(false))
  }, [])

  const now = new Date()
  const greeting =
    now.getHours() < 12 ? '早上好' : now.getHours() < 18 ? '下午好' : '晚上好'

  return (
    <Layout
      title="仪表盘"
      subtitle={`${greeting}，${localStorage.getItem('admin_username') ?? 'Admin'}`}
    >
      {/* Stat cards */}
      <div className="stats-grid">
        <StatCard
          icon={<Users />}
          iconClass="stat-icon-gold"
          label="注册用户"
          value={loading ? '—' : String(stats?.users ?? 0)}
          sub="系统累计注册用户数"
        />
        <StatCard
          icon={<Cpu />}
          iconClass="stat-icon-green"
          label="模型提供商"
          value={loading ? '—' : String(stats?.providers ?? 0)}
          sub="已配置的 LLM 服务商"
        />
        <StatCard
          icon={<Activity />}
          iconClass="stat-icon-blue"
          label="可用模型"
          value={loading ? '—' : String(stats?.activeModels ?? 0)}
          sub="当前有效启用的模型"
        />
        <StatCard
          icon={<FileText />}
          iconClass="stat-icon-warm"
          label="系统版本"
          value="v0.1"
          sub="PPT 智能生成系统"
        />
      </div>

      {/* Quick actions */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">快速导航</span>
        </div>
        <div className="card-body">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 16 }}>
            <QuickLink href="/users"     icon={<Users />}    label="管理用户"     desc="查看、创建、禁用用户账号" />
            <QuickLink href="/providers" icon={<Cpu />}      label="模型提供商"   desc="配置 LLM 服务商与可用模型" />
          </div>
        </div>
      </div>

      {/* System info */}
      <div className="card mt-6">
        <div className="card-header">
          <span className="card-title">系统信息</span>
        </div>
        <div className="card-body">
          <table>
            <tbody>
              {[
                ['应用名称',   'PPT 智能生成系统'],
                ['API 文档',   '/api/docs'],
                ['健康检查',   '/health'],
                ['认证方式',   'JWT Bearer Token'],
                ['任务队列',   'Redis Streams'],
                ['向量数据库', 'pgvector (PostgreSQL)'],
              ].map(([k, v]) => (
                <tr key={k}>
                  <td style={{ width: 180, color: 'var(--text-3)', fontWeight: 500 }}>{k}</td>
                  <td className="td-mono">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Layout>
  )
}

function StatCard({ icon, iconClass, label, value, sub }: {
  icon: React.ReactNode; iconClass: string; label: string; value: string; sub: string
}) {
  return (
    <div className="stat-card">
      <div className={`stat-card-icon ${iconClass}`}>{icon}</div>
      <div className="stat-card-label">{label}</div>
      <div className="stat-card-value">{value}</div>
      <div className="stat-card-sub">{sub}</div>
    </div>
  )
}

function QuickLink({ href, icon, label, desc }: {
  href: string; icon: React.ReactNode; label: string; desc: string
}) {
  return (
    <a href={href} style={{
      display: 'flex', alignItems: 'flex-start', gap: 12,
      padding: '14px 16px', borderRadius: 8, border: '1px solid var(--border)',
      transition: 'background 150ms, border-color 150ms',
    }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLElement).style.background = 'var(--accent-bg)'
        ;(e.currentTarget as HTMLElement).style.borderColor = 'var(--accent-muted)'
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLElement).style.background = ''
        ;(e.currentTarget as HTMLElement).style.borderColor = 'var(--border)'
      }}
    >
      <div style={{ color: 'var(--accent)', marginTop: 2 }}>{icon}</div>
      <div>
        <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 2 }}>{label}</div>
        <div style={{ fontSize: 12, color: 'var(--text-3)' }}>{desc}</div>
      </div>
    </a>
  )
}
