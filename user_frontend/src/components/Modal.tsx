import { type ReactNode } from 'react'
import { X, AlertTriangle } from 'lucide-react'

export function Modal({ title, onClose, footer, children, wide, maxWidth }: {
  title: string; onClose: () => void; footer?: ReactNode; children: ReactNode; wide?: boolean; maxWidth?: number | string
}) {
  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className={`modal-box${wide ? ' wide' : ''}`} style={maxWidth != null ? { maxWidth } : undefined}>
        <div className="modal-header">
          <span className="modal-title">{title}</span>
          <button className="btn-icon" onClick={onClose}><X /></button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  )
}

export function Confirm({ title, message, danger, loading, onConfirm, onCancel }: {
  title: string; message: string; danger?: boolean; loading?: boolean
  onConfirm: () => void; onCancel: () => void
}) {
  return (
    <Modal title={title} onClose={onCancel} footer={
      <>
        <button className="btn btn-ghost" onClick={onCancel} disabled={loading}>取消</button>
        <button
          className={`btn ${danger ? 'btn-danger' : 'btn-primary'}`}
          onClick={onConfirm}
          disabled={loading}
        >
          {loading ? '处理中…' : '确认'}
        </button>
      </>
    }>
      <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
        {danger && <AlertTriangle style={{ width: 20, height: 20, color: 'var(--error)', flexShrink: 0, marginTop: 1 }} />}
        <p style={{ fontSize: 13.5, color: 'var(--text-2)', lineHeight: 1.6 }}>{message}</p>
      </div>
    </Modal>
  )
}
