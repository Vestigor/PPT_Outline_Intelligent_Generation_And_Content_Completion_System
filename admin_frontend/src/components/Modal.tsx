import { type ReactNode } from 'react'
import { X } from 'lucide-react'

interface Props {
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  size?: 'md' | 'lg'
}

export function Modal({ title, onClose, children, footer, size = 'md' }: Props) {
  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${size === 'lg' ? 'modal-lg' : ''}`}>
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

interface ConfirmProps {
  title: string
  message: string
  onConfirm: () => void
  onCancel: () => void
  danger?: boolean
  loading?: boolean
}

export function Confirm({ title, message, onConfirm, onCancel, danger, loading }: ConfirmProps) {
  return (
    <Modal
      title={title}
      onClose={onCancel}
      footer={
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
      }
    >
      <p style={{ color: 'var(--text-2)', fontSize: 14 }}>{message}</p>
    </Modal>
  )
}
