import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Check, ChevronRight, Star } from 'lucide-react'

export interface CPItem {
  id: number | null
  label: string
  sublabel?: string
  isDefault?: boolean
}

export interface CPGroup {
  id: string | number
  label: string
  count?: number
  items: CPItem[]
}

interface Props {
  anchorRect: DOMRect
  groups: CPGroup[]
  defaultItem?: CPItem
  selectedId?: number | null
  /** 'bottom' (default): panel opens below anchor; 'right': panel opens to the right of anchor */
  direction?: 'bottom' | 'right'
  onSelect: (id: number | null) => void
  onClose: () => void
}

export function CascadingPicker({
  anchorRect, groups, defaultItem, selectedId,
  direction = 'bottom', onSelect, onClose,
}: Props) {
  const [activeGroupId, setActiveGroupId] = useState<string | number | null>(null)
  const [hoveredTop,    setHoveredTop]    = useState<number>(
    direction === 'right' ? anchorRect.top : anchorRect.bottom + 6
  )
  const [hoveredItemId, setHoveredItemId] = useState<number | null | undefined>(undefined)
  const l1Ref = useRef<HTMLDivElement>(null)
  const l2Ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handler(e: MouseEvent) {
      const t = e.target as Node
      if (l1Ref.current?.contains(t) || l2Ref.current?.contains(t)) return
      onClose()
    }
    const tid = window.setTimeout(() => document.addEventListener('mousedown', handler), 0)
    return () => { window.clearTimeout(tid); document.removeEventListener('mousedown', handler) }
  }, [onClose])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  const vw = window.innerWidth
  const vh = window.innerHeight
  const L1W = 190
  const L2W = 220
  const MAX_H = 300

  // L1 position
  let l1Top: number, l1Left: number
  if (direction === 'right') {
    const rawLeft = anchorRect.right + 6
    l1Left = rawLeft + L1W > vw ? anchorRect.left - L1W - 6 : rawLeft
    l1Top  = Math.min(anchorRect.top, vh - MAX_H - 8)
  } else {
    l1Top  = Math.min(anchorRect.bottom + 6, vh - MAX_H - 8)
    l1Left = Math.min(anchorRect.left, vw - L1W - 8)
  }

  // L2 position (always right of L1, clamped)
  const l2LeftRaw = l1Left + L1W + 4
  const l2Left    = l2LeftRaw + L2W > vw ? l1Left - L2W - 4 : l2LeftRaw
  const l2Top     = Math.max(l1Top, Math.min(hoveredTop, vh - MAX_H - 8))

  const activeGroup = groups.find(g => g.id === activeGroupId) ?? null

  const panel: React.CSSProperties = {
    position: 'fixed', zIndex: 9999,
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 10,
    boxShadow: '0 8px 32px rgba(0,0,0,.14)',
    padding: '4px 0', maxHeight: MAX_H, overflowY: 'auto',
  }

  function l1RowStyle(active: boolean): React.CSSProperties {
    return {
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '7px 12px', cursor: 'pointer', borderRadius: 6, margin: '1px 4px',
      background: active ? 'var(--surface-2)' : 'transparent',
      color: active ? 'var(--text-1)' : 'var(--text-2)',
      fontSize: 13, lineHeight: 1.4, userSelect: 'none',
      transition: 'background 100ms, color 100ms',
    }
  }

  function l2RowStyle(isSelected: boolean, isHovered: boolean): React.CSSProperties {
    if (isSelected) {
      return {
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '7px 12px', cursor: 'default', borderRadius: 6, margin: '1px 4px',
        background: 'var(--accent-bg)',
        color: 'var(--accent-dark)',
        fontSize: 13, lineHeight: 1.4, userSelect: 'none',
        fontWeight: 600,
      }
    }
    return {
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '7px 12px', cursor: 'pointer', borderRadius: 6, margin: '1px 4px',
      background: isHovered ? 'var(--surface-2)' : 'transparent',
      color: isHovered ? 'var(--text-1)' : 'var(--text-2)',
      fontSize: 13, lineHeight: 1.4, userSelect: 'none',
      transition: 'background 100ms, color 100ms',
    }
  }

  return createPortal(
    <>
      {/* Level 1 – provider groups */}
      <div ref={l1Ref} style={{ ...panel, top: l1Top, left: l1Left, minWidth: L1W }}>
        {defaultItem != null && (
          <div
            style={l1RowStyle(selectedId === null)}
            onClick={() => { onSelect(null); onClose() }}
            onMouseEnter={e => {
              setHoveredTop((e.currentTarget as HTMLElement).getBoundingClientRect().top)
              setActiveGroupId(null)
            }}
          >
            {selectedId === null
              ? <Check style={{ width: 13, height: 13, flexShrink: 0, color: 'var(--accent)' }} />
              : <span style={{ width: 13, flexShrink: 0 }} />}
            <div style={{ flex: 1, minWidth: 0, overflow: 'hidden' }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 4,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {defaultItem.label}
                <Star style={{ width: 10, height: 10, color: 'var(--accent)', flexShrink: 0 }} />
              </div>
              {defaultItem.sublabel && (
                <div style={{ fontSize: 11, color: 'var(--text-3)' }}>{defaultItem.sublabel}</div>
              )}
            </div>
          </div>
        )}
        {defaultItem != null && groups.length > 0 && (
          <div style={{ height: 1, background: 'var(--border)', margin: '3px 0' }} />
        )}
        {groups.map(g => (
          <div
            key={g.id}
            style={{ ...l1RowStyle(activeGroupId === g.id), justifyContent: 'space-between' }}
            onMouseEnter={e => {
              setHoveredTop((e.currentTarget as HTMLElement).getBoundingClientRect().top)
              setActiveGroupId(g.id)
            }}
          >
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {g.label}
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0 }}>
              {g.count != null && <span style={{ fontSize: 11, color: 'var(--text-3)' }}>{g.count}</span>}
              <ChevronRight style={{ width: 12, height: 12, color: 'var(--text-3)' }} />
            </div>
          </div>
        ))}
      </div>

      {/* Level 2 – items in active group */}
      {activeGroup && (
        <div ref={l2Ref} style={{ ...panel, top: l2Top, left: l2Left, minWidth: L2W }}>
          {activeGroup.items.length === 0 ? (
            <div style={{ padding: '10px 14px', fontSize: 12.5, color: 'var(--text-3)' }}>暂无选项</div>
          ) : activeGroup.items.map(it => {
            const isSelected = selectedId === it.id
            const isHovered  = !isSelected && hoveredItemId === it.id
            return (
              <div
                key={String(it.id)}
                style={l2RowStyle(isSelected, isHovered)}
                onMouseEnter={() => { if (!isSelected) setHoveredItemId(it.id) }}
                onMouseLeave={() => setHoveredItemId(undefined)}
                onClick={isSelected ? undefined : () => { onSelect(it.id); onClose() }}
              >
                {isSelected
                  ? <Check style={{ width: 13, height: 13, flexShrink: 0, color: 'var(--accent)' }} />
                  : <span style={{ width: 13, flexShrink: 0 }} />}
                <div style={{ flex: 1, minWidth: 0, overflow: 'hidden' }}>
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 4,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>
                    {it.label}
                    {it.isDefault && <Star style={{ width: 10, height: 10, color: 'var(--accent)', flexShrink: 0 }} />}
                  </div>
                  {it.sublabel && (
                    <div style={{ fontSize: 11, color: 'var(--text-3)' }}>{it.sublabel}</div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </>,
    document.body
  )
}
