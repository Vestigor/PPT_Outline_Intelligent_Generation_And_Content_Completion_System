import { useEffect, useState, useCallback } from 'react'
import { Plus, RefreshCw, Trash2, Pencil, ChevronDown, ChevronRight } from 'lucide-react'
import { Layout } from '../components/Layout'
import { Modal, Confirm } from '../components/Modal'
import { useToast } from '../hooks/useToast'
import {
  listProviders, createProvider, updateProvider, deleteProvider,
  createModel, updateModel, deleteModel,
  type LLMProvider, type LLMModel,
} from '../api'

export function Providers() {
  const { toast } = useToast()
  const [providers, setProviders] = useState<LLMProvider[]>([])
  const [loading,   setLoading]   = useState(true)

  const [editProvider,   setEditProvider]   = useState<LLMProvider | null>(null)
  const [showCreate,     setShowCreate]     = useState(false)
  const [confirmDelete,  setConfirmDelete]  = useState<LLMProvider | null>(null)
  const [actionLoading,  setActionLoading]  = useState(false)

  const [editModel,      setEditModel]      = useState<{ provider: LLMProvider; model: LLMModel } | null>(null)
  const [addModel,       setAddModel]       = useState<LLMProvider | null>(null)
  const [confirmDelModel,setConfirmDelModel]= useState<{ provider: LLMProvider; model: LLMModel } | null>(null)

  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listProviders()
      setProviders(data)
    } catch (e: any) {
      toast(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])  // eslint-disable-line

  useEffect(() => { load() }, [load])

  function toggle(id: number) {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  // Provider CRUD
  async function handleCreateProvider(name: string, base_url: string, description: string, is_active: boolean) {
    setActionLoading(true)
    try {
      await createProvider(name, base_url, description || null, is_active)
      toast('提供商创建成功', 'success')
      setShowCreate(false)
      load()
    } catch (e: any) { if (e.message !== '_auth_redirect') toast(e.message, 'error') }
    finally { setActionLoading(false) }
  }

  async function handleUpdateProvider(id: number, data: Parameters<typeof updateProvider>[1]) {
    setActionLoading(true)
    try {
      await updateProvider(id, data)
      toast('提供商已更新', 'success')
      setEditProvider(null)
      load()
    } catch (e: any) { if (e.message !== '_auth_redirect') toast(e.message, 'error') }
    finally { setActionLoading(false) }
  }

  async function handleDeleteProvider() {
    if (!confirmDelete) return
    setActionLoading(true)
    try {
      await deleteProvider(confirmDelete.id)
      toast('提供商已删除', 'success')
      setConfirmDelete(null)
      load()
    } catch (e: any) { if (e.message !== '_auth_redirect') toast(e.message, 'error') }
    finally { setActionLoading(false) }
  }

  // Model CRUD
  async function handleCreateModel(provider: LLMProvider, model_name: string, description: string, is_active: boolean) {
    setActionLoading(true)
    try {
      await createModel(provider.id, model_name, description || null, is_active)
      toast('模型添加成功', 'success')
      setAddModel(null)
      load()
    } catch (e: any) { if (e.message !== '_auth_redirect') toast(e.message, 'error') }
    finally { setActionLoading(false) }
  }

  async function handleUpdateModel(provider: LLMProvider, model: LLMModel, data: Parameters<typeof updateModel>[2]) {
    setActionLoading(true)
    try {
      await updateModel(provider.id, model.id, data)
      toast('模型已更新', 'success')
      setEditModel(null)
      load()
    } catch (e: any) { if (e.message !== '_auth_redirect') toast(e.message, 'error') }
    finally { setActionLoading(false) }
  }

  async function handleDeleteModel() {
    if (!confirmDelModel) return
    setActionLoading(true)
    try {
      await deleteModel(confirmDelModel.provider.id, confirmDelModel.model.id)
      toast('模型已删除', 'success')
      setConfirmDelModel(null)
      load()
    } catch (e: any) { if (e.message !== '_auth_redirect') toast(e.message, 'error') }
    finally { setActionLoading(false) }
  }

  return (
    <Layout
      title="模型提供商"
      subtitle={`共 ${providers.length} 个提供商`}
      actions={
        <>
          <button className="btn-icon" onClick={load} title="刷新"><RefreshCw /></button>
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
            <Plus />添加提供商
          </button>
        </>
      }
    >
      {loading && (
        <div style={{ textAlign: 'center', color: 'var(--text-3)', padding: 48 }}>加载中…</div>
      )}

      {!loading && providers.length === 0 && (
        <div className="card">
          <div className="empty-state">
            <Plus />
            <p>暂无提供商，点击右上角添加</p>
          </div>
        </div>
      )}

      {!loading && providers.map(p => {
        const open = expanded.has(p.id)
        return (
          <div key={p.id} className="provider-card">
            <div className="provider-header" onClick={() => toggle(p.id)}>
              <div className="flex items-center gap-3">
                {open ? <ChevronDown style={{ width: 16, color: 'var(--text-3)' }} /> : <ChevronRight style={{ width: 16, color: 'var(--text-3)' }} />}
                <div>
                  <div className="flex items-center gap-2">
                    <span className="provider-name">{p.name}</span>
                    <span className={`badge ${p.is_active ? 'badge-success' : 'badge-error'}`}>
                      {p.is_active ? '启用' : '禁用'}
                    </span>
                  </div>
                  <div className="provider-url">{p.base_url}</div>
                </div>
              </div>
              <div className="td-actions" onClick={e => e.stopPropagation()}>
                <button className="btn btn-sm btn-ghost" onClick={() => setAddModel(p)}>
                  <Plus style={{ width: 13, height: 13 }} />添加模型
                </button>
                <button className="btn-icon" onClick={() => setEditProvider(p)} title="编辑"><Pencil /></button>
                <button className="btn-icon" onClick={() => setConfirmDelete(p)} title="删除" style={{ color: 'var(--error)' }}><Trash2 /></button>
              </div>
            </div>

            {open && (
              <div>
                {p.models.length === 0 ? (
                  <div style={{ padding: '24px 20px', color: 'var(--text-3)', fontSize: 13, textAlign: 'center' }}>
                    暂无模型，点击「添加模型」
                  </div>
                ) : (
                  <table>
                    <thead>
                      <tr>
                        <th>模型名称</th>
                        <th>描述</th>
                        <th>自身状态</th>
                        <th>有效状态</th>
                        <th>操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {p.models.map(m => (
                        <tr key={m.id}>
                          <td className="font-mono" style={{ fontSize: 13 }}>{m.model_name}</td>
                          <td style={{ color: 'var(--text-2)', fontSize: 13 }}>{m.description ?? '—'}</td>
                          <td>
                            <span className={`badge ${m.is_active ? 'badge-success' : 'badge-neutral'}`}>
                              {m.is_active ? '启用' : '禁用'}
                            </span>
                          </td>
                          <td>
                            <span className={`badge ${m.effective_is_active ? 'badge-success' : 'badge-error'}`}>
                              {m.effective_is_active ? '可用' : '不可用'}
                            </span>
                          </td>
                          <td>
                            <div className="td-actions">
                              <button className="btn-icon" onClick={() => setEditModel({ provider: p, model: m })} title="编辑"><Pencil /></button>
                              <button className="btn-icon" onClick={() => setConfirmDelModel({ provider: p, model: m })} title="删除" style={{ color: 'var(--error)' }}><Trash2 /></button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </div>
        )
      })}

      {/* Provider modals */}
      {showCreate && (
        <ProviderModal
          loading={actionLoading}
          onClose={() => setShowCreate(false)}
          onSubmit={handleCreateProvider}
        />
      )}
      {editProvider && (
        <ProviderModal
          initial={editProvider}
          loading={actionLoading}
          onClose={() => setEditProvider(null)}
          onSubmit={(name, base_url, description, is_active) =>
            handleUpdateProvider(editProvider.id, { name, base_url, description, is_active })
          }
        />
      )}
      {confirmDelete && (
        <Confirm
          title="删除提供商"
          message={`确认删除提供商「${confirmDelete.name}」及其所有模型？已绑定该提供商的用户配置将失效。`}
          danger
          loading={actionLoading}
          onConfirm={handleDeleteProvider}
          onCancel={() => setConfirmDelete(null)}
        />
      )}

      {/* Model modals */}
      {addModel && (
        <ModelModal
          provider={addModel}
          loading={actionLoading}
          onClose={() => setAddModel(null)}
          onSubmit={(model_name, description, is_active) =>
            handleCreateModel(addModel, model_name, description, is_active)
          }
        />
      )}
      {editModel && (
        <ModelModal
          provider={editModel.provider}
          initial={editModel.model}
          loading={actionLoading}
          onClose={() => setEditModel(null)}
          onSubmit={(model_name, description, is_active) =>
            handleUpdateModel(editModel.provider, editModel.model, { model_name, description, is_active })
          }
        />
      )}
      {confirmDelModel && (
        <Confirm
          title="删除模型"
          message={`确认删除模型「${confirmDelModel.model.model_name}」？已使用此模型的用户配置将被标记为不可用。`}
          danger
          loading={actionLoading}
          onConfirm={handleDeleteModel}
          onCancel={() => setConfirmDelModel(null)}
        />
      )}
    </Layout>
  )
}

function ProviderModal({ initial, loading, onClose, onSubmit }: {
  initial?: LLMProvider
  loading: boolean
  onClose: () => void
  onSubmit: (name: string, base_url: string, description: string, is_active: boolean) => void
}) {
  const [name,        setName]        = useState(initial?.name        ?? '')
  const [base_url,    setBaseUrl]     = useState(initial?.base_url    ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [is_active,   setIsActive]    = useState(initial?.is_active   ?? true)

  return (
    <Modal
      title={initial ? `编辑提供商 · ${initial.name}` : '添加提供商'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={loading}>取消</button>
          <button
            className="btn btn-primary"
            disabled={loading || !name || !base_url}
            onClick={() => onSubmit(name, base_url, description, is_active)}
          >
            {loading ? '保存中…' : initial ? '保存更改' : '创建提供商'}
          </button>
        </>
      }
    >
      <div className="form-group">
        <label className="form-label">提供商名称</label>
        <input className="form-input" placeholder="例如：OpenAI" value={name} onChange={e => setName(e.target.value)} autoFocus />
      </div>
      <div className="form-group">
        <label className="form-label">API Base URL</label>
        <input className="form-input font-mono" placeholder="https://api.openai.com/v1" value={base_url} onChange={e => setBaseUrl(e.target.value)} />
        <div className="form-hint">OpenAI 兼容接口地址，末尾不需要斜杠</div>
      </div>
      <div className="form-group">
        <label className="form-label">描述（选填）</label>
        <input className="form-input" placeholder="简短描述此提供商" value={description} onChange={e => setDescription(e.target.value)} />
      </div>
      <div className="form-group" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <label className="form-label" style={{ marginBottom: 0 }}>启用此提供商</label>
        <label className="toggle">
          <input type="checkbox" checked={is_active} onChange={e => setIsActive(e.target.checked)} />
          <span className="toggle-track" />
        </label>
      </div>
    </Modal>
  )
}

function ModelModal({ provider, initial, loading, onClose, onSubmit }: {
  provider: LLMProvider
  initial?: LLMModel
  loading: boolean
  onClose: () => void
  onSubmit: (model_name: string, description: string, is_active: boolean) => void
}) {
  const [model_name,  setModelName]   = useState(initial?.model_name  ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [is_active,   setIsActive]    = useState(initial?.is_active   ?? true)

  return (
    <Modal
      title={initial ? `编辑模型 · ${initial.model_name}` : `为「${provider.name}」添加模型`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={loading}>取消</button>
          <button
            className="btn btn-primary"
            disabled={loading || !model_name}
            onClick={() => onSubmit(model_name, description, is_active)}
          >
            {loading ? '保存中…' : initial ? '保存更改' : '添加模型'}
          </button>
        </>
      }
    >
      <div className="form-group">
        <label className="form-label">模型标识符</label>
        <input
          className="form-input font-mono"
          placeholder="例如：gpt-4o-mini"
          value={model_name}
          onChange={e => setModelName(e.target.value)}
          autoFocus
        />
        <div className="form-hint">与 API 调用时传入的 model 参数一致</div>
      </div>
      <div className="form-group">
        <label className="form-label">描述（选填）</label>
        <input className="form-input" placeholder="模型简介" value={description} onChange={e => setDescription(e.target.value)} />
      </div>
      <div className="form-group" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <label className="form-label" style={{ marginBottom: 0 }}>启用此模型</label>
        <label className="toggle">
          <input type="checkbox" checked={is_active} onChange={e => setIsActive(e.target.checked)} />
          <span className="toggle-track" />
        </label>
      </div>
    </Modal>
  )
}
