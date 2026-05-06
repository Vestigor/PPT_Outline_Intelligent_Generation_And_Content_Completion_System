import {
  useState, useEffect, useRef, useCallback,
  type KeyboardEvent, type ChangeEvent, type ReactNode,
} from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Plus, MessageSquare, Database, Layers, BookOpen, Download, Send,
  Paperclip, Zap, X, Trash2, ChevronDown, ChevronUp,
  Cpu, Check, KeyRound, LogOut, UserX, AlertCircle, Upload, FileText,
  Globe, Pencil, PlusCircle, MinusCircle, Eye, EyeOff, Mail,
} from 'lucide-react'
import { useToast } from '../hooks/useToast'
import { Modal, Confirm } from '../components/Modal'
import { CascadingPicker, type CPGroup } from '../components/CascadingPicker'
import {
  listSessions, getSession, deleteSession, startSession, sendMessage, listMessages,
  listSessionRefs, addSessionRefs, removeSessionRef,
  listKnowledge, uploadKnowledge, updateSessionSettings, logout, getToken,
  listUserLLMConfigs, changePassword, deleteAccount, getActiveTask,
  updateOutline, confirmOutline, sendEmailCode, updateEmail,
  type SessionSummary, type Message, type SessionDetail,
  type KnowledgeFile, type KnowledgeRef, type UserLLMConfig,
} from '../api'

const STAGE_LABEL: Record<string, string> = {
  requirement_collection: '需求收集中',
  outline_generation:     '大纲生成中',
  outline_confirming:     '大纲确认',
  content_generation:     '内容生成中',
  content_confirming:     '内容确认',
  completed:              '已完成',
}

const ASYNC_STAGES = new Set(['outline_generation', 'content_generation'])

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

function timeSince(dt: string) {
  const diff = (Date.now() - new Date(dt).getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  return new Date(dt).toLocaleDateString('zh-CN')
}

// ── Outline renderer ──────────────────────────────────────────────────────
function safeStr(v: unknown): string {
  if (typeof v === 'string') return v
  if (v === null || v === undefined) return ''
  return JSON.stringify(v)
}

// ── Outline editor types + normalization ─────────────────────────────────
// New outline shape: chapter has summary; slide has slide_intent + must_cover + expected_takeaway.
// Legacy points[] is read on input as a fallback (each point becomes a must_cover entry).
interface EditableSlide   {
  title: string
  slide_intent: string
  must_cover: string[]
  expected_takeaway: string
}
interface EditableChapter { title: string; summary: string; slides: EditableSlide[] }
interface EditableOutline { topic: string; chapters: EditableChapter[] }

function normalizeToEditable(raw: Record<string, unknown>): EditableOutline {
  const chaptersRaw = (raw.chapters ?? raw.outline) as any[] | undefined
  if (Array.isArray(chaptersRaw) && chaptersRaw.length > 0 && Array.isArray((chaptersRaw[0] as any)?.slides)) {
    return {
      topic: safeStr(raw.topic ?? raw.title ?? ''),
      chapters: chaptersRaw.map((ch: any) => ({
        title: safeStr(ch.title ?? ch.chapter_title ?? ''),
        summary: safeStr(ch.summary ?? ''),
        slides: ((ch.slides as any[]) ?? []).map((s: any) => {
          const legacyPoints = ((s.points ?? s.key_points ?? []) as any[])
            .map(p => safeStr(p)).filter(Boolean)
          const must = Array.isArray(s.must_cover)
            ? (s.must_cover as any[]).map(p => safeStr(p)).filter(Boolean)
            : legacyPoints
          return {
            title: safeStr(s.title ?? s.slide_title ?? ''),
            slide_intent: safeStr(s.slide_intent ?? ''),
            must_cover: must,
            expected_takeaway: safeStr(s.expected_takeaway ?? ''),
          }
        }),
      })),
    }
  }
  return { topic: safeStr(raw.topic ?? raw.title ?? ''), chapters: [] }
}

function denormalizeOutline(e: EditableOutline): Record<string, unknown> {
  return {
    topic: e.topic,
    chapters: e.chapters.map(ch => ({
      title: ch.title,
      summary: ch.summary,
      slides: ch.slides.map(s => ({
        title: s.title,
        slide_intent: s.slide_intent,
        must_cover: s.must_cover.filter(p => p.trim()),
        expected_takeaway: s.expected_takeaway,
      })),
    })),
  }
}

// ── Outline editor modal ──────────────────────────────────────────────────
function OutlineEditor({
  initialOutline, sessionId, onClose, onConfirmed,
}: {
  initialOutline: Record<string, unknown>
  sessionId: number
  onClose: () => void
  onConfirmed: (taskId: number) => void
}) {
  const { toast } = useToast()
  const [edited, setEdited] = useState<EditableOutline>(() => normalizeToEditable(initialOutline))
  const [saving, setSaving] = useState(false)
  const [confirming, setConfirming] = useState(false)

  function setTopic(v: string) { setEdited(e => ({ ...e, topic: v })) }

  function emptySlide(): EditableSlide {
    return { title: '新幻灯片', slide_intent: '', must_cover: [''], expected_takeaway: '' }
  }
  function emptyChapter(): EditableChapter {
    return { title: '新章节', summary: '', slides: [emptySlide()] }
  }

  function setChapterTitle(ci: number, v: string) {
    setEdited(e => { const cs = [...e.chapters]; cs[ci] = { ...cs[ci], title: v }; return { ...e, chapters: cs } })
  }
  function setChapterSummary(ci: number, v: string) {
    setEdited(e => { const cs = [...e.chapters]; cs[ci] = { ...cs[ci], summary: v }; return { ...e, chapters: cs } })
  }
  function addChapter() {
    setEdited(e => ({ ...e, chapters: [...e.chapters, emptyChapter()] }))
  }
  function removeChapter(ci: number) {
    setEdited(e => ({ ...e, chapters: e.chapters.filter((_, i) => i !== ci) }))
  }

  function updateSlide(ci: number, si: number, patch: Partial<EditableSlide>) {
    setEdited(e => {
      const cs = [...e.chapters]; const ss = [...cs[ci].slides]
      ss[si] = { ...ss[si], ...patch }; cs[ci] = { ...cs[ci], slides: ss }
      return { ...e, chapters: cs }
    })
  }
  function setSlideTitle(ci: number, si: number, v: string)            { updateSlide(ci, si, { title: v }) }
  function setSlideIntent(ci: number, si: number, v: string)           { updateSlide(ci, si, { slide_intent: v }) }
  function setSlideTakeaway(ci: number, si: number, v: string)         { updateSlide(ci, si, { expected_takeaway: v }) }
  function addSlide(ci: number) {
    setEdited(e => {
      const cs = [...e.chapters]
      cs[ci] = { ...cs[ci], slides: [...cs[ci].slides, emptySlide()] }
      return { ...e, chapters: cs }
    })
  }
  function removeSlide(ci: number, si: number) {
    setEdited(e => {
      const cs = [...e.chapters]; cs[ci] = { ...cs[ci], slides: cs[ci].slides.filter((_, i) => i !== si) }
      return { ...e, chapters: cs }
    })
  }
  function setMustCover(ci: number, si: number, mi: number, v: string) {
    setEdited(e => {
      const cs = [...e.chapters]; const ss = [...cs[ci].slides]; const ms = [...ss[si].must_cover]
      ms[mi] = v; ss[si] = { ...ss[si], must_cover: ms }; cs[ci] = { ...cs[ci], slides: ss }
      return { ...e, chapters: cs }
    })
  }
  function addMustCover(ci: number, si: number) {
    setEdited(e => {
      const cs = [...e.chapters]; const ss = [...cs[ci].slides]
      ss[si] = { ...ss[si], must_cover: [...ss[si].must_cover, ''] }; cs[ci] = { ...cs[ci], slides: ss }
      return { ...e, chapters: cs }
    })
  }
  function removeMustCover(ci: number, si: number, mi: number) {
    setEdited(e => {
      const cs = [...e.chapters]; const ss = [...cs[ci].slides]
      ss[si] = { ...ss[si], must_cover: ss[si].must_cover.filter((_, i) => i !== mi) }
      cs[ci] = { ...cs[ci], slides: ss }; return { ...e, chapters: cs }
    })
  }

  async function handleSave() {
    setSaving(true)
    try {
      await updateOutline(sessionId, denormalizeOutline(edited))
      toast('大纲已保存', 'success')
    } catch (err: any) {
      toast(err.message, 'error')
    } finally { setSaving(false) }
  }

  async function handleConfirm() {
    setConfirming(true)
    try {
      await updateOutline(sessionId, denormalizeOutline(edited))
      const res = await confirmOutline(sessionId)
      onConfirmed(res.task_id!)
    } catch (err: any) {
      toast(err.message, 'error')
    } finally { setConfirming(false) }
  }

  const footer = (
    <>
      <button className="btn btn-ghost" onClick={onClose} disabled={saving || confirming}>取消</button>
      <button className="btn btn-secondary" onClick={handleSave} disabled={saving || confirming}>
        {saving ? '保存中…' : '保存草稿'}
      </button>
      <button className="btn btn-primary" onClick={handleConfirm} disabled={saving || confirming}>
        {confirming ? '处理中…' : '确认并生成 PPT'}
      </button>
    </>
  )

  return (
    <Modal title="编辑大纲" onClose={onClose} wide footer={footer}>
      <div className="outline-editor">
        {/* Topic */}
        <div className="oe-field">
          <label className="oe-label">演示主题</label>
          <input className="oe-input" value={edited.topic} onChange={e => setTopic(e.target.value)} placeholder="输入主题…" />
        </div>

        {/* Chapters */}
        {edited.chapters.map((ch, ci) => (
          <div key={ci} className="oe-chapter">
            <div className="oe-chapter-head">
              <span className="oe-chapter-num">第{ci + 1}章</span>
              <input
                className="oe-input oe-chapter-title"
                value={ch.title}
                onChange={e => setChapterTitle(ci, e.target.value)}
                placeholder="章节标题…"
              />
              <button className="btn-icon oe-remove-btn" onClick={() => removeChapter(ci)} title="删除章节">
                <MinusCircle style={{ width: 15, height: 15 }} />
              </button>
            </div>
            <div className="oe-points" style={{ marginTop: 6 }}>
              <input
                className="oe-input"
                value={ch.summary}
                onChange={e => setChapterSummary(ci, e.target.value)}
                placeholder="本章核心论点（1 句话）…"
              />
            </div>

            {/* Slides */}
            {ch.slides.map((s, si) => (
              <div key={si} className="oe-slide">
                <div className="oe-slide-head">
                  <span className="slide-num">{si + 1}</span>
                  <input
                    className="oe-input oe-slide-title"
                    value={s.title}
                    onChange={e => setSlideTitle(ci, si, e.target.value)}
                    placeholder="幻灯片标题…"
                  />
                  <button className="btn-icon oe-remove-btn" onClick={() => removeSlide(ci, si)} title="删除幻灯片">
                    <MinusCircle style={{ width: 13, height: 13 }} />
                  </button>
                </div>
                {/* slide_intent */}
                <div className="oe-points">
                  <input
                    className="oe-input"
                    value={s.slide_intent}
                    onChange={e => setSlideIntent(ci, si, e.target.value)}
                    placeholder="本页意图：要让观众理解什么（1 句话）…"
                  />
                </div>
                {/* must_cover */}
                <div className="oe-points">
                  <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 4, paddingLeft: 14 }}>
                    必须覆盖（关键概念/数据/人物/案例）
                  </div>
                  {s.must_cover.map((m, mi) => (
                    <div key={mi} className="oe-point-row">
                      <span className="oe-point-dot" />
                      <input
                        className="oe-input oe-point-input"
                        value={m}
                        onChange={e => setMustCover(ci, si, mi, e.target.value)}
                        placeholder="关键要素（短语，≤30字）…"
                      />
                      <button className="btn-icon oe-remove-btn" onClick={() => removeMustCover(ci, si, mi)} title="删除关键要素">
                        <X style={{ width: 11, height: 11 }} />
                      </button>
                    </div>
                  ))}
                  <button className="oe-add-point-btn" onClick={() => addMustCover(ci, si)}>
                    <PlusCircle style={{ width: 12, height: 12 }} />添加关键要素
                  </button>
                </div>
                {/* expected_takeaway */}
                <div className="oe-points">
                  <input
                    className="oe-input"
                    value={s.expected_takeaway}
                    onChange={e => setSlideTakeaway(ci, si, e.target.value)}
                    placeholder="核心 takeaway：观众听完应记住的 1 句话…"
                  />
                </div>
                {si < ch.slides.length - 1 && <div className="oe-slide-divider" />}
              </div>
            ))}
            <button className="oe-add-slide-btn" onClick={() => addSlide(ci)}>
              <PlusCircle style={{ width: 12, height: 12 }} />添加幻灯片
            </button>
          </div>
        ))}

        <button className="oe-add-chapter-btn" onClick={addChapter}>
          <PlusCircle style={{ width: 13, height: 13 }} />添加章节
        </button>
      </div>
    </Modal>
  )
}

function renderOutlineSlide(s: Record<string, unknown>, idx: number) {
  const intent = safeStr(s.slide_intent)
  const takeaway = safeStr(s.expected_takeaway)
  const mustCover = (s.must_cover as unknown[]) || []
  // Legacy fallback: old outlines stored points/key_points before the schema redesign.
  const legacyPoints = (s.points ?? s.key_points) as unknown[] | undefined
  const showLegacy = !intent && !takeaway && (!Array.isArray(mustCover) || mustCover.length === 0)

  return (
    <div key={idx} className="outline-slide">
      <div className="outline-slide-title">
        <span className="slide-num">{idx + 1}</span>
        {String(s.title ?? s.slide_title ?? `第${idx + 1}张`)}
      </div>
      {intent && (
        <div style={{ fontSize: 12, color: 'var(--text-2)', paddingLeft: 26, marginBottom: 4 }}>
          意图：{intent}
        </div>
      )}
      {Array.isArray(mustCover) && mustCover.length > 0 && (
        <div style={{ paddingLeft: 26, marginBottom: 4, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {mustCover.map((m, j) => (
            <span key={j} style={{
              fontSize: 11, padding: '2px 8px', borderRadius: 10,
              background: 'var(--bg-2)', color: 'var(--text-2)', border: '1px solid var(--border)',
            }}>
              {safeStr(m)}
            </span>
          ))}
        </div>
      )}
      {takeaway && (
        <div style={{ fontSize: 11.5, color: 'var(--text-3)', paddingLeft: 26, fontStyle: 'italic' }}>
          Takeaway：{takeaway}
        </div>
      )}
      {showLegacy && Array.isArray(legacyPoints) && legacyPoints.length > 0 && (
        <ul className="outline-slide-points">
          {legacyPoints.map((p, j) => <li key={j}>{safeStr(p)}</li>)}
        </ul>
      )}
    </div>
  )
}

function OutlineView({ outline }: { outline: Record<string, unknown> }) {
  const chapters = (outline.chapters ?? outline.outline) as Array<Record<string, unknown>> | undefined

  if (Array.isArray(chapters) && chapters.length > 0 && Array.isArray((chapters[0] as any)?.slides)) {
    return (
      <>
        {outline.topic && (
          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 12, color: 'var(--text-1)' }}>
            {String(outline.topic)}
          </div>
        )}
        {chapters.map((ch, ci) => {
          const chSlides = (ch.slides ?? []) as Array<Record<string, unknown>>
          const chTitle = String(ch.title ?? ch.chapter_title ?? `第${ci + 1}章`)
          const chSummary = safeStr(ch.summary)
          return (
            <div key={ci} style={{ marginBottom: 14 }}>
              <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--accent)', marginBottom: 6, paddingLeft: 4, borderLeft: '3px solid var(--accent)' }}>
                {chTitle}
              </div>
              {chSummary && (
                <div style={{ fontSize: 12, color: 'var(--text-2)', paddingLeft: 8, marginBottom: 6 }}>
                  {chSummary}
                </div>
              )}
              {Array.isArray(chSlides) && chSlides.map((s, si) => renderOutlineSlide(s, si))}
            </div>
          )
        })}
      </>
    )
  }

  // Fallback: flat slides (no chapters nesting)
  const slides = (outline.slides ?? []) as Array<Record<string, unknown>>
  if (!Array.isArray(slides) || slides.length === 0) {
    return <pre style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>{JSON.stringify(outline, null, 2)}</pre>
  }
  return (
    <>
      {(outline.title ?? outline.topic) && (
        <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 12, color: 'var(--text-1)' }}>
          {String(outline.title ?? outline.topic)}
        </div>
      )}
      {slides.map((s, i) => renderOutlineSlide(s, i))}
    </>
  )
}

// ── Slide viewer ──────────────────────────────────────────────────────────
const CITATION_STYLE_LABEL: Record<string, string> = {
  direct: '直接引用', paraphrase: '改写', summary: '概括', data: '数据引用',
}
const SOURCE_TYPE_LABEL: Record<string, string> = {
  report: '报告', rag: 'RAG', web: 'Web',
}

// Wrap [N] markers in the text so they're visually distinguishable.
function renderCitedText(raw: string): ReactNode {
  const parts: ReactNode[] = []
  const re = /\[(\d+)\]/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(raw)) !== null) {
    if (m.index > last) parts.push(raw.slice(last, m.index))
    parts.push(
      <sup key={`${m.index}-${m[1]}`} style={{
        color: 'var(--accent)', fontWeight: 600, padding: '0 1px', fontSize: '0.85em',
      }}>[{m[1]}]</sup>
    )
    last = m.index + m[0].length
  }
  if (last < raw.length) parts.push(raw.slice(last))
  return parts
}

function SlideReferences({ refs }: { refs: Array<Record<string, unknown>> }) {
  if (!Array.isArray(refs) || refs.length === 0) return null
  return (
    <div style={{ marginTop: 6, paddingLeft: 26, paddingTop: 6, borderTop: '1px dashed var(--border)' }}>
      <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 3 }}>参考文献</div>
      {refs.map((r, i) => {
        const n = r.ref_number != null ? String(r.ref_number) : String(i + 1)
        const sType = SOURCE_TYPE_LABEL[String(r.source_type ?? '')] ?? String(r.source_type ?? '')
        const cStyle = CITATION_STYLE_LABEL[String(r.citation_style ?? '')] ?? String(r.citation_style ?? '')
        return (
          <div key={i} style={{ fontSize: 11.5, color: 'var(--text-2)', lineHeight: 1.55 }}>
            <span style={{ color: 'var(--accent)', fontWeight: 600, marginRight: 4 }}>[{n}]</span>
            <span>{safeStr(r.source)}</span>
            {sType && <span style={{ color: 'var(--text-3)' }}> · {sType}</span>}
            {cStyle && <span style={{ color: 'var(--text-3)' }}> · {cStyle}</span>}
          </div>
        )
      })}
    </div>
  )
}

function SlideView({ content }: { content: Record<string, unknown> }) {
  const slides = (content.slides ?? []) as Array<Record<string, unknown>>
  if (!Array.isArray(slides) || slides.length === 0) {
    return <pre style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>{JSON.stringify(content, null, 2)}</pre>
  }
  return (
    <>
      {content.presentation_title && (
        <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 12, color: 'var(--text-1)' }}>
          {String(content.presentation_title)}
        </div>
      )}
      {slides.map((s, i) => {
        const blocks = (s.content_blocks ?? s.content ?? null) as Array<Record<string, unknown>> | null
        const refs = (s.references ?? null) as Array<Record<string, unknown>> | null
        return (
          <div key={i} className="outline-slide">
            <div className="outline-slide-title">
              <span className="slide-num">{s.slide_number != null ? String(s.slide_number) : i + 1}</span>
              {String(s.title ?? `第${i + 1}张`)}
            </div>
            {s.subtitle != null && (
              <div style={{ fontSize: 12, color: 'var(--text-3)', paddingLeft: 26, marginBottom: 4 }}>
                {String(s.subtitle)}
              </div>
            )}
            {Array.isArray(blocks) && blocks.map((block, bi) => {
              const items = block.items as unknown[] | null
              const text = block.text as string | null
              return (
                <div key={bi}>
                  {Array.isArray(items) && items.length > 0 && (
                    <ul className="outline-slide-points">
                      {items.map((it, j) => <li key={j}>{renderCitedText(safeStr(it))}</li>)}
                    </ul>
                  )}
                  {typeof text === 'string' && text && (
                    <div style={{ fontSize: 12, color: 'var(--text-2)', paddingLeft: 26, marginBottom: 4 }}>
                      {renderCitedText(text)}
                    </div>
                  )}
                </div>
              )
            })}
            {typeof s.speaker_notes === 'string' && s.speaker_notes && (
              <div style={{ fontSize: 11.5, color: 'var(--text-3)', marginTop: 4, paddingLeft: 26, fontStyle: 'italic' }}>
                备注：{renderCitedText(s.speaker_notes)}
              </div>
            )}
            {Array.isArray(refs) && refs.length > 0 && <SlideReferences refs={refs} />}
          </div>
        )
      })}
    </>
  )
}

// ── Message bubble ────────────────────────────────────────────────────────
function MessageBubble({ msg, stage, onExport }: {
  msg: Message; stage: string; onExport: () => void
}) {
  const [outlineOpen, setOutlineOpen] = useState(true)
  const [slideOpen,   setSlideOpen]   = useState(true)
  const isUser = msg.role === 'user'

  return (
    <div className={`msg-row ${isUser ? 'user-row' : ''}`}>
      <div className={`msg-avatar ${isUser ? 'user-avatar' : 'ai-avatar'}`}>
        {isUser ? (localStorage.getItem('username') ?? 'U')[0].toUpperCase() : 'AI'}
      </div>
      <div className="msg-content">
        {msg.content && (
          <div className={`msg-bubble ${isUser ? 'user-bubble' : 'ai-bubble'}`}>
            {msg.content}
          </div>
        )}

        {msg.outline_json && (
          <div className="structured-card" style={{ marginTop: msg.content ? 8 : 0 }}>
            <div className="structured-card-header">
              <span className="structured-card-title"><Layers /> 大纲方案</span>
              <button className="btn-icon" onClick={() => setOutlineOpen(o => !o)}>
                {outlineOpen ? <ChevronUp /> : <ChevronDown />}
              </button>
            </div>
            {outlineOpen && (
              <div className="structured-card-body">
                <OutlineView outline={msg.outline_json} />
              </div>
            )}
            {outlineOpen && stage === 'outline_confirming' && (
              <div className="structured-card-actions">
                <span style={{ fontSize: 12, color: 'var(--text-3)', flex: 1 }}>
                  请通过发送消息来确认或修改大纲
                </span>
              </div>
            )}
          </div>
        )}

        {msg.slide_json && (
          <div className="structured-card" style={{ marginTop: msg.content ? 8 : 0 }}>
            <div className="structured-card-header">
              <span className="structured-card-title"><BookOpen /> PPT 内容</span>
              <button className="btn-icon" onClick={() => setSlideOpen(o => !o)}>
                {slideOpen ? <ChevronUp /> : <ChevronDown />}
              </button>
            </div>
            {slideOpen && (
              <div className="structured-card-body">
                <SlideView content={msg.slide_json} />
              </div>
            )}
            {slideOpen && (
              <div className="structured-card-actions">
                <button className="btn btn-sm btn-primary" onClick={onExport}>
                  <Download />导出 PPT
                </button>
                {stage === 'content_confirming' && (
                  <span style={{ fontSize: 12, color: 'var(--text-3)' }}>或发送消息修改内容</span>
                )}
              </div>
            )}
          </div>
        )}

        <div className="msg-time">
          {new Date(msg.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
    </div>
  )
}

// ── Password strength helpers ─────────────────────────────────────────────
interface PwdRule { label: string; ok: boolean }

function getPwdRules(pwd: string): PwdRule[] {
  return [
    { label: '长度为 8-16 个字符',      ok: pwd.length >= 8 && pwd.length <= 16 },
    { label: '不能包含空格',             ok: pwd.length > 0 && !pwd.includes(' ') },
    { label: '需包含大、小写字母和数字', ok: /[A-Z]/.test(pwd) && /[a-z]/.test(pwd) && /\d/.test(pwd) },
  ]
}
function pwdStrength(pwd: string) { return getPwdRules(pwd).filter(r => r.ok).length }

function PwdStrengthWidget({ pwd, focused }: { pwd: string; focused: boolean }) {
  const rules    = getPwdRules(pwd)
  const strength = pwdStrength(pwd)
  const colors   = ['', '#EF4444', '#F59E0B', '#22C55E']
  const labels   = ['', '低', '中', '高']
  if (!pwd) return null
  return (
    <div style={{ marginTop: 6 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <span style={{ fontSize: 12, color: 'var(--text-3)' }}>密码强度：</span>
        <span style={{ fontSize: 12, fontWeight: 600, color: colors[strength] }}>{labels[strength]}</span>
      </div>
      <div style={{ display: 'flex', gap: 3, height: 4, marginBottom: 6 }}>
        {[1, 2, 3].map(i => (
          <div key={i} style={{ flex: 1, borderRadius: 2, background: strength >= i ? colors[strength] : 'var(--border)', transition: 'background .2s' }} />
        ))}
      </div>
      {focused && (
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 4 }}>密码要求：</div>
          {rules.map(r => (
            <div key={r.label} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
              {r.ok
                ? <Check style={{ width: 13, height: 13, color: '#22C55E', flexShrink: 0 }} />
                : <AlertCircle style={{ width: 13, height: 13, color: '#EF4444', flexShrink: 0 }} />}
              <span style={{ fontSize: 12, color: r.ok ? 'var(--text-2)' : '#EF4444' }}>{r.label}</span>
            </div>
          ))}
        </div>
      )}
      {!focused && !rules.every(r => r.ok) && (
        <div style={{ fontSize: 12, color: '#EF4444', display: 'flex', alignItems: 'center', gap: 4 }}>
          <AlertCircle style={{ width: 13, height: 13 }} />密码不符合规范
        </div>
      )}
    </div>
  )
}

// ── Change Password Modal ─────────────────────────────────────────────────
function ChangePasswordModal({ onClose }: { onClose: () => void }) {
  const { toast }   = useToast()
  const [oldPwd,     setOldPwd]     = useState('')
  const [newPwd,     setNewPwd]     = useState('')
  const [confirm,    setConfirm]    = useState('')
  const [showOld,    setShowOld]    = useState(false)
  const [showNew,    setShowNew]    = useState(false)
  const [newFocused, setNewFocused] = useState(false)
  const [loading,    setLoading]    = useState(false)

  const newRules = getPwdRules(newPwd)
  const allPass  = newRules.every(r => r.ok)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!allPass)             { toast('新密码不符合规范', 'error'); return }
    if (newPwd !== confirm)   { toast('两次密码不一致', 'error'); return }
    setLoading(true)
    try {
      await changePassword(oldPwd, newPwd)
      toast('密码修改成功', 'success')
      onClose()
    } catch (err: any) {
      toast(err.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title="修改密码" onClose={onClose} footer={
      <>
        <button className="btn btn-ghost" onClick={onClose} disabled={loading}>取消</button>
        <button className="btn btn-primary" onClick={handleSubmit as any}
          disabled={loading || !oldPwd || !allPass || !confirm || newPwd !== confirm}>
          {loading ? '修改中…' : '确认修改'}
        </button>
      </>
    }>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label">当前密码</label>
          <div style={{ position: 'relative' }}>
            <input className="form-input" type={showOld ? 'text' : 'password'}
              autoComplete="current-password" placeholder="输入当前密码"
              value={oldPwd} onChange={e => setOldPwd(e.target.value)}
              style={{ paddingRight: 40 }} autoFocus />
            <button type="button" onClick={() => setShowOld(p => !p)}
              style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: 0 }}>
              {showOld ? <EyeOff style={{ width: 15, height: 15 }} /> : <Eye style={{ width: 15, height: 15 }} />}
            </button>
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">新密码</label>
          <div style={{ position: 'relative' }}>
            <input className="form-input" type={showNew ? 'text' : 'password'}
              autoComplete="new-password" placeholder="8-16 位，含大小写字母和数字"
              value={newPwd} onChange={e => setNewPwd(e.target.value)}
              onFocus={() => setNewFocused(true)} onBlur={() => setNewFocused(false)}
              style={{ paddingRight: 40 }} />
            <button type="button" onClick={() => setShowNew(p => !p)}
              style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: 0 }}>
              {showNew ? <EyeOff style={{ width: 15, height: 15 }} /> : <Eye style={{ width: 15, height: 15 }} />}
            </button>
          </div>
          <PwdStrengthWidget pwd={newPwd} focused={newFocused} />
        </div>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">确认新密码</label>
          <input className="form-input" type="password"
            autoComplete="new-password" placeholder="再次输入新密码"
            value={confirm} onChange={e => setConfirm(e.target.value)} />
          {confirm && newPwd !== confirm && (
            <div style={{ fontSize: 12, color: '#EF4444', marginTop: 4 }}>两次密码不一致</div>
          )}
        </div>
      </form>
    </Modal>
  )
}

// ── Bind / Update Email Modal (two-step) ─────────────────────────────────
function BindEmailModal({ onClose }: { onClose: () => void }) {
  const { toast }         = useToast()
  const [step,            setStep]       = useState<1 | 2>(1)
  const [pwd,             setPwd]        = useState('')
  const [showPwd,         setShowPwd]    = useState(false)
  const [email,           setEmail]      = useState('')
  const [code,            setCode]       = useState('')
  const [sending,         setSending]    = useState(false)
  const [countdown,       setCountdown]  = useState(0)
  const [loading,         setLoading]    = useState(false)

  async function handleSendCode() {
    if (!email) { toast('请输入新邮箱地址', 'error'); return }
    setSending(true)
    try {
      await sendEmailCode(email, 'bind_email')
      toast('验证码已发送，请查收', 'success')
      setCountdown(60)
      const timer = setInterval(() => {
        setCountdown(c => { if (c <= 1) { clearInterval(timer); return 0 } return c - 1 })
      }, 1000)
    } catch (err: any) {
      toast(err.message, 'error')
    } finally {
      setSending(false)
    }
  }

  async function handleSubmit() {
    if (!email || !code) { toast('请填写邮箱和验证码', 'error'); return }
    setLoading(true)
    try {
      await updateEmail(email, code, pwd)
      toast('邮箱绑定成功', 'success')
      onClose()
    } catch (err: any) {
      toast(err.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  if (step === 1) return (
    <Modal title="绑定 / 修改邮箱" onClose={onClose} footer={
      <>
        <button className="btn btn-ghost" onClick={onClose}>取消</button>
        <button className="btn btn-primary" disabled={!pwd} onClick={() => setStep(2)}>
          下一步
        </button>
      </>
    }>
      <div className="form-group" style={{ marginBottom: 0 }}>
        <label className="form-label">当前密码（用于验证身份）</label>
        <div style={{ position: 'relative' }}>
          <input className="form-input" type={showPwd ? 'text' : 'password'}
            autoComplete="current-password" placeholder="输入当前登录密码"
            value={pwd} onChange={e => setPwd(e.target.value)}
            style={{ paddingRight: 40 }} autoFocus />
          <button type="button" onClick={() => setShowPwd(p => !p)}
            style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: 0 }}>
            {showPwd ? <EyeOff style={{ width: 15, height: 15 }} /> : <Eye style={{ width: 15, height: 15 }} />}
          </button>
        </div>
      </div>
    </Modal>
  )

  return (
    <Modal title="绑定 / 修改邮箱" onClose={onClose} footer={
      <>
        <button className="btn btn-ghost" onClick={() => setStep(1)} disabled={loading}>上一步</button>
        <button className="btn btn-primary" disabled={loading || !email || !code} onClick={handleSubmit}>
          {loading ? '提交中…' : '确认绑定'}
        </button>
      </>
    }>
      <div className="form-group">
        <label className="form-label">新邮箱地址</label>
        <div style={{ display: 'flex', gap: 8 }}>
          <input className="form-input" type="email" autoComplete="email"
            placeholder="输入新邮箱" value={email}
            onChange={e => setEmail(e.target.value)} style={{ flex: 1 }} autoFocus />
          <button type="button" className="btn btn-ghost"
            style={{ flexShrink: 0, padding: '0 12px', fontSize: 12 }}
            disabled={sending || countdown > 0 || !email}
            onClick={handleSendCode}>
            {countdown > 0 ? `${countdown}s` : sending ? '发送中…' : '发送验证码'}
          </button>
        </div>
      </div>
      <div className="form-group" style={{ marginBottom: 0 }}>
        <label className="form-label">验证码</label>
        <input className="form-input" type="text" autoComplete="one-time-code"
          placeholder="输入 6 位验证码" maxLength={6}
          value={code} onChange={e => setCode(e.target.value)} />
      </div>
    </Modal>
  )
}

// ── Doc Modal ─────────────────────────────────────────────────────────────
const DOC_STATUS: Record<string, { label: string; cls: string }> = {
  pending:    { label: '等待处理', cls: 'badge-neutral' },
  processing: { label: '处理中',   cls: 'badge-info' },
  ready:      { label: '就绪',     cls: 'badge-success' },
  failed:     { label: '失败',     cls: 'badge-error' },
}

function DocModal({
  sessionId, pendingDocs, onPendingChange, sessionRefs, onRefsChange, ragEnabled, onClose,
}: {
  sessionId: number | null
  pendingDocs: KnowledgeFile[]
  onPendingChange: (docs: KnowledgeFile[]) => void
  sessionRefs: KnowledgeRef[]
  onRefsChange: (refs: KnowledgeRef[]) => void
  ragEnabled: boolean
  onClose: () => void
}) {
  const { toast } = useToast()
  const [tab,            setTab]            = useState<'linked' | 'library'>('linked')
  const [library,        setLibrary]        = useState<KnowledgeFile[]>([])
  const [libLoading,     setLibLoading]     = useState(false)
  const [uploading,      setUploading]      = useState(false)
  const [uploadFile,     setUploadFile]     = useState<File | null>(null)
  const [uploadCategory, setUploadCategory] = useState('')
  const [showUploadForm, setShowUploadForm] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const linkedDocs: KnowledgeFile[] = sessionId
    ? sessionRefs.map(r => r.knowledge_file)
    : pendingDocs

  const linkedIds = new Set(linkedDocs.map(d => d.id))
  const notReadyCount = ragEnabled ? linkedDocs.filter(d => d.status !== 'ready').length : 0

  useEffect(() => {
    setLibLoading(true)
    listKnowledge().then(setLibrary).catch(() => {}).finally(() => setLibLoading(false))
  }, [])

  function onFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ''
    setUploadFile(file)
    setUploadCategory('')
    setShowUploadForm(true)
  }

  async function handleUpload() {
    if (!uploadFile) return
    setUploading(true)
    try {
      const doc = await uploadKnowledge(uploadFile, uploadCategory.trim() || 'default')
      toast(`「${doc.file_name}」上传成功，正在处理…`, 'success')
      setLibrary(prev => [doc, ...prev])
      setUploadFile(null); setUploadCategory(''); setShowUploadForm(false)
      if (sessionId) {
        await addSessionRefs(sessionId, [doc.id])
        onRefsChange(await listSessionRefs(sessionId))
      } else {
        onPendingChange([...pendingDocs, doc])
      }
    } catch (err: any) {
      if (err.message !== '_auth_redirect') toast(err.message, 'error')
    } finally {
      setUploading(false)
    }
  }

  async function handleAssociate(fileId: number) {
    try {
      if (sessionId) {
        await addSessionRefs(sessionId, [fileId])
        onRefsChange(await listSessionRefs(sessionId))
      } else {
        const file = library.find(f => f.id === fileId)
        if (file) onPendingChange([...pendingDocs, file])
      }
      toast('已关联', 'success')
    } catch (err: any) {
      if (err.message !== '_auth_redirect') toast(err.message, 'error')
    }
  }

  async function handleRemove(fileId: number, refId?: number) {
    try {
      if (sessionId && refId) {
        await removeSessionRef(sessionId, fileId)
        onRefsChange(sessionRefs.filter(r => r.id !== refId))
      } else {
        onPendingChange(pendingDocs.filter(d => d.id !== fileId))
      }
    } catch (err: any) {
      if (err.message !== '_auth_redirect') toast(err.message, 'error')
    }
  }

  const availableLib = library.filter(f => !linkedIds.has(f.id))

  return (
    <Modal title="关联知识文档" onClose={onClose} footer={
      <>
        <button className="btn btn-ghost btn-sm" onClick={() => fileRef.current?.click()} disabled={uploading}>
          <Upload style={{ width: 12, height: 12 }} />{uploading ? '上传中…' : '上传文件'}
        </button>
        <span style={{ flex: 1 }} />
        <button className="btn btn-ghost" onClick={onClose}>关闭</button>
      </>
    }>
      <div className="doc-modal-tabs">
        <button className={`doc-modal-tab${tab === 'linked' ? ' active' : ''}`}
          onClick={() => setTab('linked')}>
          已关联 ({linkedDocs.length})
        </button>
        <button className={`doc-modal-tab${tab === 'library' ? ' active' : ''}`}
          onClick={() => setTab('library')}>
          知识库
        </button>
      </div>

      {ragEnabled && notReadyCount > 0 && (
        <div className="doc-status-warn">
          <AlertCircle style={{ width: 15, height: 15, flexShrink: 0, marginTop: 1 }} />
          有 {notReadyCount} 个文件尚未处理完成，发送前请等待就绪或取消关联
        </div>
      )}

      {tab === 'linked' && (
        <>
          {linkedDocs.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--text-3)' }}>
              <Database style={{ width: 24, height: 24, margin: '0 auto 10px', opacity: .35 }} />
              <div style={{ fontSize: 13, marginBottom: 14 }}>还没有关联文档</div>
              <button className="btn btn-sm btn-ghost" onClick={() => setTab('library')}>
                从知识库选择
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {linkedDocs.map(doc => {
                const ref = sessionRefs.find(r => r.knowledge_file_id === doc.id)
                const st = DOC_STATUS[doc.status] ?? { label: doc.status, cls: 'badge-neutral' }
                return (
                  <div key={doc.id} className="file-item">
                    <div className="file-item-icon"><FileText /></div>
                    <div className="file-item-body">
                      <div className="file-item-name">{doc.file_name}</div>
                      <div className="file-item-meta">
                        {formatSize(doc.size_bytes)} ·{' '}
                        <span className={`badge ${st.cls}`} style={{ fontSize: 10, padding: '1px 5px' }}>{st.label}</span>
                      </div>
                    </div>
                    <div className="file-item-actions">
                      <button className="btn-icon" style={{ color: 'var(--error)' }}
                        onClick={() => handleRemove(doc.id, ref?.id)}>
                        <X style={{ width: 13, height: 13 }} />
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}

      {tab === 'library' && (
        <>
          {libLoading ? (
            <div style={{ textAlign: 'center', padding: '16px 0', color: 'var(--text-3)', fontSize: 13 }}>加载中…</div>
          ) : availableLib.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '16px 0', color: 'var(--text-3)', fontSize: 13 }}>
              {library.length === 0 ? '知识库为空，请先上传文件' : '所有文件均已关联'}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {availableLib.map(f => {
                const st = DOC_STATUS[f.status] ?? { label: f.status, cls: 'badge-neutral' }
                return (
                  <div key={f.id} className="file-item" style={{ opacity: f.status !== 'ready' ? 0.65 : 1 }}>
                    <div className="file-item-icon"><FileText /></div>
                    <div className="file-item-body">
                      <div className="file-item-name">{f.file_name}</div>
                      <div className="file-item-meta">
                        <span className={`badge ${st.cls}`} style={{ fontSize: 10, padding: '1px 5px' }}>{st.label}</span>
                      </div>
                    </div>
                    <div className="file-item-actions">
                      <button className="btn btn-sm btn-ghost" style={{ padding: '3px 8px', fontSize: 11 }}
                        onClick={() => handleAssociate(f.id)}>
                        关联
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}

      {showUploadForm && uploadFile && (
        <div style={{
          marginTop: 14, padding: 14, background: 'var(--bg-2)',
          borderRadius: 8, border: '1px solid var(--border)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <FileText style={{ width: 16, height: 16, color: 'var(--accent)', flexShrink: 0 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12.5, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {uploadFile.name}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-3)' }}>{formatSize(uploadFile.size)}</div>
            </div>
            <button className="btn-icon" style={{ width: 22, height: 22 }}
              onClick={() => { setUploadFile(null); setShowUploadForm(false) }}>
              <X style={{ width: 12, height: 12 }} />
            </button>
          </div>
          <div className="form-group" style={{ marginBottom: 10 }}>
            <label className="form-label">文件分类</label>
            <input className="form-input" placeholder="例如：研究报告（留空则为 default）"
              value={uploadCategory} onChange={e => setUploadCategory(e.target.value)} autoFocus />
          </div>
          <button className="btn btn-primary btn-sm" onClick={handleUpload} disabled={uploading}>
            {uploading ? '上传中…' : '确认上传并关联'}
          </button>
        </div>
      )}

      <input ref={fileRef} type="file" accept=".pdf,.docx,.md,.txt,.pptx,.doc"
        style={{ display: 'none' }} onChange={onFileChange} />
    </Modal>
  )
}

// Module-level sessions cache — survives page navigation within the SPA
let _sessionsCache: SessionSummary[] = []

// ── Main Chat component ───────────────────────────────────────────────────
export function Chat() {
  const navigate  = useNavigate()
  const { id }    = useParams<{ id?: string }>()
  const { toast } = useToast()

  const [sessions,     setSessions]     = useState<SessionSummary[]>(_sessionsCache)
  const [session,      setSession]      = useState<SessionDetail | null>(null)
  const [messages,     setMessages]     = useState<Message[]>([])
  const [streaming,    setStreaming]     = useState(false)
  const [streamText,   setStreamText]   = useState('')
  const [taskId,       setTaskId]       = useState<number | null>(null)
  const [progress,     setProgress]     = useState<number | null>(null)
  const [confirmDel,   setConfirmDel]   = useState<SessionSummary | null>(null)
  const [sessLoading,  setSessLoading]  = useState(_sessionsCache.length === 0)
  const [msgLoading,   setMsgLoading]   = useState(false)
  const [llmConfigs,   setLlmConfigs]   = useState<UserLLMConfig[]>([])

  // New session form
  const [input,          setInput]          = useState('')
  const [ragEnabled,     setRagEnabled]     = useState(false)
  const [deepSearch,     setDeepSearch]     = useState(false)
  const [reportFile,     setReportFile]     = useState<File | null>(null)
  const [sending,        setSending]        = useState(false)
  const [selectedConfig, setSelectedConfig] = useState<number | null>(null)

  // Doc management
  const [pendingDocs,   setPendingDocs]   = useState<KnowledgeFile[]>([])
  const [sessionRefs,   setSessionRefs]   = useState<KnowledgeRef[]>([])
  const [showDocModal,  setShowDocModal]  = useState(false)

  // Modals
  const [showChangePwd,      setShowChangePwd]      = useState(false)
  const [showBindEmail,      setShowBindEmail]      = useState(false)
  const [showLogoutConfirm,  setShowLogoutConfirm]  = useState(false)
  const [showDeleteAccount,  setShowDeleteAccount]  = useState(false)
  const [showOutlineEditor,  setShowOutlineEditor]  = useState(false)

  // Model picker anchors (CascadingPicker)
  const [newPickerAnchor,     setNewPickerAnchor]     = useState<DOMRect | null>(null)
  const [sessionPickerAnchor, setSessionPickerAnchor] = useState<DOMRect | null>(null)

  const bodyRef  = useRef<HTMLDivElement>(null)
  const textaRef = useRef<HTMLTextAreaElement>(null)
  const fileRef  = useRef<HTMLInputElement>(null)
  const pollRef  = useRef<ReturnType<typeof setInterval> | null>(null)
  const sseRef   = useRef<EventSource | null>(null)
  // Tracks which session a newly-created SSE belongs to (prevents cross-session interference)
  const pendingNewSessionRef = useRef<{ id: number; message: Message } | null>(null)

  const currentId = id ? parseInt(id) : null
  const username  = localStorage.getItem('username') ?? 'U'

  const loadSessions = useCallback(async () => {
    try {
      const data = await listSessions()
      _sessionsCache = data.items
      setSessions(data.items)
    } catch { /* ignore */ }
    finally { setSessLoading(false) }
  }, [])

  useEffect(() => { loadSessions() }, [loadSessions])

  useEffect(() => {
    listUserLLMConfigs().then(setLlmConfigs).catch(() => {})
  }, [])

  // Session detail + messages — also resets streaming state on session switch
  useEffect(() => {
    const pending = pendingNewSessionRef.current
    const isNewSessionNav = pending !== null && pending.id === currentId

    if (!isNewSessionNav) {
      // Switching between sessions (or back to new-session form): close any open SSE
      if (sseRef.current) { sseRef.current.close(); sseRef.current = null }
      setStreaming(false); setStreamText(''); setProgress(null); setTaskId(null)
      setMessages([])
    } else {
      // Navigated to a session we just created — show optimistic message immediately
      setMessages([pending!.message])
      pendingNewSessionRef.current = null
    }

    if (!currentId) {
      setSession(null)
      setSessionRefs([])
      return
    }
    setMsgLoading(true)
    Promise.all([getSession(currentId), listMessages(currentId), listSessionRefs(currentId)])
      .then(([sess, msgs, refs]) => {
        setSession(sess)
        setMessages(msgs)
        setSessionRefs(refs)
        // Reconnect SSE if session is still in an async processing stage (e.g. after page refresh)
        if (ASYNC_STAGES.has(sess.stage)) {
          getActiveTask(currentId!).then(task => {
            if (task && (task.status === 'pending' || task.status === 'running')) {
              setTaskId(task.id)
              subscribeSSE(task.id, currentId!)
            }
          }).catch(() => {})
        }
      })
      .catch(() => {})
      .finally(() => setMsgLoading(false))
  }, [currentId])

  // Scroll to bottom
  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight
  }, [messages, streamText, streaming])

  // Auto-resize textarea
  useEffect(() => {
    if (textaRef.current) {
      textaRef.current.style.height = 'auto'
      textaRef.current.style.height = `${Math.min(textaRef.current.scrollHeight, 160)}px`
    }
  }, [input])


  // SSE subscription — sessionId is passed explicitly to avoid stale-closure interference
  const subscribeSSE = useCallback((tid: number, sessionId: number) => {
    if (sseRef.current) { sseRef.current.close(); sseRef.current = null }
    const es = new EventSource(`/api/tasks/${tid}/stream?token=${getToken()}`)
    sseRef.current = es
    let accumulated = ''
    setStreamText(''); setStreaming(true)

    es.addEventListener('token', e => {
      accumulated += (e as MessageEvent).data
      setStreamText(accumulated)
    })
    es.addEventListener('progress', e => {
      try { const d = JSON.parse((e as MessageEvent).data); setProgress(d.percentage ?? null) }
      catch { /* ignore */ }
    })
    es.addEventListener('done', async (e) => {
      es.close(); sseRef.current = null
      setStreaming(false); setStreamText(''); setProgress(null); setTaskId(null)
      const [msgs, sess] = await Promise.all([listMessages(sessionId), getSession(sessionId)])
      setMessages(msgs); setSession(sess)
      loadSessions()
      // Chain to next task if provided (e.g. outline_generation after requirement_collection)
      try {
        const data = JSON.parse((e as MessageEvent).data)
        if (data.next_task_id) {
          setTaskId(data.next_task_id)
          subscribeSSE(data.next_task_id, sessionId)
        }
      } catch { /* ignore */ }
    })
    es.addEventListener('error', () => {
      es.close(); sseRef.current = null
      setStreaming(false); setStreamText(''); setProgress(null); setTaskId(null)
    })
    es.onerror = () => { es.close(); sseRef.current = null; setStreaming(false) }
  }, [loadSessions])

  // Cleanup on unmount
  useEffect(() => () => {
    if (sseRef.current) { sseRef.current.close(); sseRef.current = null }
    if (pollRef.current) clearInterval(pollRef.current)
  }, [])

  async function handleSend() {
    const text = input.trim()
    if (!text || sending) return

    // RAG validation: block if any linked doc is not ready
    if (ragEnabled) {
      const docs = currentId ? sessionRefs.map(r => r.knowledge_file) : pendingDocs
      const notReady = docs.filter(d => d.status !== 'ready')
      if (notReady.length > 0) {
        toast(`${notReady.length} 个关联文件尚未处理完成，请稍候再发送`, 'error')
        return
      }
    }

    setInput('')
    setSending(true)
    try {
      if (!currentId) {
        const res = await startSession({
          content: text,
          rag_enabled: ragEnabled,
          deep_search_enabled: deepSearch,
          report_file: reportFile,
          llm_config_id: selectedConfig,
        })
        setReportFile(null)
        if (pendingDocs.length > 0) {
          try { await addSessionRefs(res.session_id, pendingDocs.map(d => d.id)) }
          catch { /* ignore ref association errors */ }
        }
        setPendingDocs([])
        await loadSessions()

        // Store optimistic user message so useEffect([currentId]) can display it immediately
        pendingNewSessionRef.current = {
          id: res.session_id,
          message: {
            id: res.message_id,
            session_id: res.session_id,
            role: 'user',
            seq_no: res.seq_no,
            content: text,
            outline_json: null,
            slide_json: null,
            created_at: new Date().toISOString(),
          },
        }

        navigate(`/chat/${res.session_id}`)

        if (res.task_id) {
          setTaskId(res.task_id)
          subscribeSSE(res.task_id, res.session_id)
        } else if (res.reply) {
          const msgs = await listMessages(res.session_id)
          setMessages(msgs)
        }
      } else {
        // Optimistically show user message immediately (before LLM judgment returns)
        const optimisticMsg: Message = {
          id: -Date.now(),
          session_id: currentId,
          role: 'user',
          seq_no: -1,
          content: text,
          outline_json: null,
          slide_json: null,
          created_at: new Date().toISOString(),
        }
        setMessages(prev => [...prev, optimisticMsg])

        const res = await sendMessage(currentId, text)
        const msgs = await listMessages(currentId)
        setMessages(msgs)
        if (res.task_id) {
          setTaskId(res.task_id)
          subscribeSSE(res.task_id, currentId)
        }
      }
    } catch (err: any) {
      if (err.message !== '_auth_redirect') toast(err.message, 'error')
    } finally {
      setSending(false)
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // e.nativeEvent.isComposing is true while IME is active (e.g. typing Chinese pinyin)
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      handleSend()
    }
  }

  async function handleDeleteSession() {
    if (!confirmDel) return
    try {
      await deleteSession(confirmDel.id)
      toast('会话已删除', 'success')
      setConfirmDel(null)
      loadSessions()
      if (confirmDel.id === currentId) navigate('/', { replace: true })
    } catch (err: any) {
      if (err.message !== '_auth_redirect') toast(err.message, 'error')
    }
  }

  async function handleExport() {
    if (!currentId) return
    const res = await fetch(`/api/sessions/${currentId}/export?format=md`, {
      headers: { Authorization: `Bearer ${getToken()}` }
    })
    if (!res.ok) { toast('导出失败', 'error'); return }
    const blob = await res.blob()
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `ppt_${currentId}.md`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  async function handleChangeSessionModel(configId: number | null) {
    if (!currentId) return
    setSessionPickerAnchor(null)
    try {
      const updated = await updateSessionSettings(currentId, { llm_config_id: configId })
      setSession(updated)
      toast('已切换模型', 'success')
    } catch (err: any) {
      if (err.message !== '_auth_redirect') toast(err.message, 'error')
    }
  }

  async function handleToggleRag() {
    if (!currentId || !session) return
    try {
      const updated = await updateSessionSettings(currentId, { rag_enabled: !session.rag_enabled })
      setSession(updated)
      toast(updated.rag_enabled ? '已启用 RAG 知识库检索' : '已关闭 RAG', 'success')
    } catch (err: any) {
      if (err.message !== '_auth_redirect') toast(err.message, 'error')
    }
  }

  async function handleToggleDeepSearch() {
    if (!currentId || !session) return
    try {
      const updated = await updateSessionSettings(currentId, { deep_search_enabled: !session.deep_search_enabled })
      setSession(updated)
      toast(updated.deep_search_enabled ? '已启用联网搜索' : '已关闭联网搜索', 'success')
    } catch (err: any) {
      if (err.message !== '_auth_redirect') toast(err.message, 'error')
    }
  }

  function handleOutlineConfirmed(taskId: number) {
    setShowOutlineEditor(false)
    setTaskId(taskId)
    subscribeSSE(taskId, currentId!)
    // Refresh session stage immediately
    getSession(currentId!).then(setSession).catch(() => {})
  }

  async function doLogout() {
    try { await logout(getToken()) } catch {}
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    navigate('/login', { replace: true })
  }

  async function doDeleteAccount() {
    try {
      await deleteAccount()
      localStorage.removeItem('token')
      localStorage.removeItem('username')
      navigate('/login', { replace: true })
    } catch (err: any) {
      if (err.message !== '_auth_redirect') toast(err.message, 'error')
    }
  }

  const activeConfigs    = llmConfigs.filter(c => c.is_active)
  const defaultCfg       = llmConfigs.find(c => c.is_default) ?? activeConfigs[0]
  const groupedActiveConfigs = (() => {
    const map = new Map<string, typeof activeConfigs>()
    for (const c of activeConfigs) {
      if (!map.has(c.provider_name)) map.set(c.provider_name, [])
      map.get(c.provider_name)!.push(c)
    }
    return map
  })()
  const selectedCfg      = llmConfigs.find(c => c.id === selectedConfig)
  const sessionModelCfg  = session ? llmConfigs.find(c => c.id === session.current_user_llm_config_id) : null
  const docCount         = currentId ? sessionRefs.length : pendingDocs.length

  const modelPickerGroups: CPGroup[] = Array.from(groupedActiveConfigs.entries()).map(([pName, configs]) => ({
    id: pName,
    label: pName,
    items: configs.map(c => ({ id: c.id, label: c.alias || c.model_name, isDefault: c.is_default })),
  }))
  const modelPickerDefault = defaultCfg ? {
    id: null as null,
    label: defaultCfg.alias || defaultCfg.model_name,
    sublabel: defaultCfg.provider_name + '（默认）',
  } : undefined

  // Block input during async generation stages (even after page refresh when streaming=false)
  const isProcessing   = sending || streaming || (!!session && ASYNC_STAGES.has(session.stage))
  const processingHint = session?.stage === 'outline_generation' ? '大纲生成中，请稍候…'
                       : session?.stage === 'content_generation'  ? '内容生成中，请稍候…'
                       : null

  return (
    <div className="app-shell">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        {/* Logo */}
        <div className="sidebar-logo">
          <div className="sidebar-logo-mark"><MessageSquare /></div>
          <div>
            <div className="sidebar-logo-text">PPT 智能生成</div>
            <div className="sidebar-logo-sub">AI 创作助手</div>
          </div>
        </div>

        {/* New session button */}
        <button className="sidebar-new-btn" onClick={() => navigate('/')}>
          <Plus />新建会话
        </button>

        {/* Session list */}
        <div className="sidebar-section-label">最近会话</div>
        <div className="sidebar-sessions">
          {sessLoading && sessions.length === 0 && (
            <div style={{ padding: 12, color: 'var(--sb-t3)', fontSize: 12 }}>加载中…</div>
          )}
          {!sessLoading && sessions.length === 0 && (
            <div style={{ padding: '20px 10px', textAlign: 'center', color: 'var(--sb-t3)', fontSize: 12 }}>
              还没有会话，点击 + 开始
            </div>
          )}
          {sessions.map(s => (
            <div
              key={s.id}
              className={`session-item${s.id === currentId ? ' active' : ''}`}
              onClick={() => navigate(`/chat/${s.id}`)}
            >
              <div className="session-item-icon"><MessageSquare /></div>
              <div className="session-item-body">
                <div className="session-item-title">{s.title || '无标题'}</div>
                <div className="session-item-meta">
                  {STAGE_LABEL[s.stage] ?? s.stage} · {timeSince(s.updated_at)}
                </div>
              </div>
              <button
                className="btn-icon session-delete-btn"
                onClick={e => { e.stopPropagation(); setConfirmDel(s) }}
              >
                <Trash2 style={{ width: 13, height: 13 }} />
              </button>
            </div>
          ))}
        </div>

        {/* Bottom nav */}
        <nav className="sidebar-nav">
          <button
            className={`sidebar-nav-item${window.location.pathname === '/knowledge' ? ' active' : ''}`}
            onClick={() => navigate('/knowledge')}
          >
            <Database />知识库
          </button>
          <button
            className={`sidebar-nav-item${window.location.pathname === '/models' ? ' active' : ''}`}
            onClick={() => navigate('/models')}
          >
            <Cpu />模型配置
          </button>
        </nav>

        {/* User hover area */}
        <div className="sidebar-user-area">
          <div className="sidebar-user-mini">
            <div className="sidebar-user-avatar">{username[0].toUpperCase()}</div>
            <div className="sidebar-user-name">{username}</div>
            <ChevronUp style={{ width: 12, height: 12 }} className="sidebar-user-caret" />
          </div>
          <div className="sidebar-user-popup">
            <div className="sidebar-user-popup-head">
              <div className="sidebar-user-popup-avatar">{username[0].toUpperCase()}</div>
              <div>
                <div className="sidebar-user-popup-name">{username}</div>
                <div className="sidebar-user-popup-role">普通用户</div>
              </div>
            </div>
            <button className="sidebar-user-popup-item" onClick={() => setShowChangePwd(true)}>
              <KeyRound />修改密码
            </button>
            <button className="sidebar-user-popup-item" onClick={() => setShowBindEmail(true)}>
              <Mail />绑定/修改邮箱
            </button>
            <button className="sidebar-user-popup-item danger" onClick={() => setShowLogoutConfirm(true)}>
              <LogOut />退出登录
            </button>
            <button className="sidebar-user-popup-item danger" onClick={() => setShowDeleteAccount(true)}>
              <UserX />注销账户
            </button>
          </div>
        </div>
      </aside>

      {/* ── Main area ── */}
      <div className="main-area">
        {/* Header */}
        <div className="chat-header">
          {/* LEFT: model selector */}
          <div style={{ flex: 1, display: 'flex', alignItems: 'center' }}>
            {session ? (
              <button
                className="header-model-badge"
                onClick={e => {
                  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
                  setSessionPickerAnchor(p => p ? null : rect)
                }}
              >
                <Cpu style={{ width: 11, height: 11 }} />
                <span>{sessionModelCfg
                  ? (sessionModelCfg.alias || sessionModelCfg.model_name)
                  : defaultCfg
                    ? (defaultCfg.alias || defaultCfg.model_name)
                    : '默认配置'}</span>
                <ChevronDown style={{ width: 10, height: 10, opacity: .6 }} />
              </button>
            ) : (
              <button
                className="header-model-badge"
                onClick={e => {
                  if (activeConfigs.length === 0) return
                  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
                  setNewPickerAnchor(p => p ? null : rect)
                }}
                disabled={activeConfigs.length === 0}
                style={activeConfigs.length === 0 ? { opacity: .5, cursor: 'not-allowed' } : {}}
              >
                <Cpu style={{ width: 11, height: 11 }} />
                <span>
                  {activeConfigs.length === 0
                    ? '无可用模型'
                    : selectedCfg
                      ? (selectedCfg.alias || selectedCfg.model_name)
                      : defaultCfg
                        ? (defaultCfg.alias || defaultCfg.model_name)
                        : '默认配置'}
                </span>
                {activeConfigs.length > 0 && <ChevronDown style={{ width: 10, height: 10, opacity: .6 }} />}
              </button>
            )}
          </div>

          {/* CENTER: session title (absolute center) */}
          {session && (
            <div className="chat-header-center">
              <div className="chat-header-title">{session.title || '无标题'}</div>
            </div>
          )}

          {/* RIGHT: stage badge + action buttons */}
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 8 }}>
            {session && (
              <span className="chat-header-stage">{STAGE_LABEL[session.stage] ?? session.stage}</span>
            )}
            {session?.stage === 'outline_confirming' && (
              <button className="btn btn-sm btn-ghost" onClick={() => setShowOutlineEditor(true)}>
                <Pencil style={{ width: 13, height: 13 }} />编辑大纲
              </button>
            )}
            {session && ['content_confirming', 'completed'].includes(session.stage) && (
              <button className="btn btn-sm btn-ghost" onClick={handleExport}>
                <Download />导出
              </button>
            )}
          </div>
        </div>

        {/* Chat body + FAB */}
        <div style={{ flex: 1, overflow: 'hidden', position: 'relative', display: 'flex', flexDirection: 'column' }}>
          <div className="chat-body" ref={bodyRef}>
            <div className="chat-body-inner">
              {!currentId && (
                <div className="chat-empty">
                  <div className="chat-empty-icon"><MessageSquare /></div>
                  <div className="chat-empty-title">开始一次 PPT 创作</div>
                  <div className="chat-empty-sub">
                    描述你的主题、受众或目标，AI 将引导你一步步完成从需求到成品的全过程。
                    你也可以上传一份已有报告，直接生成大纲。
                  </div>
                </div>
              )}

              {msgLoading && messages.length === 0 && (
                <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-3)', fontSize: 13 }}>加载中…</div>
              )}

              {messages.map(m => (
                <MessageBubble key={m.id} msg={m} stage={session?.stage ?? ''} onExport={handleExport} />
              ))}

              {/* AI typing bubble: shown when streaming OR when waiting for async task to start */}
              {(streaming || (!streaming && processingHint)) && (
                <div className="msg-row">
                  <div className="msg-avatar ai-avatar">AI</div>
                  <div className="msg-content">
                    {streaming && progress !== null ? (
                      <div className="task-progress">
                        <div className="task-progress-label">
                          <Zap style={{ width: 12, height: 12 }} />
                          正在生成内容… {Math.round(progress * 100)}%
                        </div>
                        <div className="task-progress-bar">
                          <div className="task-progress-fill" style={{ width: `${progress * 100}%` }} />
                        </div>
                      </div>
                    ) : streaming && streamText ? (
                      <div className="msg-bubble ai-bubble">{streamText}</div>
                    ) : (
                      <div className="msg-bubble ai-bubble">
                        <div className="typing-dots"><span /><span /><span /></div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Floating doc button */}
          <button
            className="chat-doc-fab"
            onClick={() => setShowDocModal(true)}
            title={docCount > 0 ? `${docCount} 个关联文档` : '关联知识文档'}
          >
            <Database style={{ width: 20, height: 20 }} />
            {docCount > 0 && <span className="chat-doc-fab-badge">{docCount}</span>}
          </button>
        </div>

        {/* Input area */}
        <div className="chat-footer">
          <div className="chat-footer-inner">
            {/* Report file card */}
            {!currentId && reportFile && (
              <div className="report-file-card">
                <FileText style={{ width: 16, height: 16, color: 'var(--accent)', flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {reportFile.name}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-3)' }}>{formatSize(reportFile.size)}</div>
                </div>
                <button className="btn-icon" style={{ width: 22, height: 22, color: 'var(--text-3)', flexShrink: 0 }}
                  onClick={() => setReportFile(null)}>
                  <X style={{ width: 12, height: 12 }} />
                </button>
              </div>
            )}

            <div className="chat-input-wrap">
              <textarea
                ref={textaRef}
                className="chat-input-textarea"
                placeholder={currentId ? '发送消息…（Shift+Enter 换行）' : '描述你想做的 PPT 主题、受众、目标…'}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={1}
                disabled={isProcessing}
              />
              <div className="chat-input-actions">
                {!currentId && (
                  <button
                    className="btn-icon"
                    title="上传报告文件（PDF/DOCX/MD/TXT）"
                    onClick={() => fileRef.current?.click()}
                    style={{ color: reportFile ? 'var(--accent)' : undefined }}
                  >
                    <Paperclip style={{ width: 16, height: 16 }} />
                  </button>
                )}
                <button
                  className="btn-send"
                  onClick={handleSend}
                  disabled={!input.trim() || isProcessing}
                >
                  <Send />
                </button>
              </div>
            </div>

            <div className="chat-input-opts">
              {currentId ? (
                <>
                  <button
                    type="button"
                    className={`chat-opt-toggle${session?.rag_enabled ? ' on' : ''}`}
                    onClick={handleToggleRag}
                    title={session?.rag_enabled ? '已启用 RAG 知识库检索（点击关闭）' : '启用 RAG 知识库检索'}
                  >
                    <div className="chat-opt-dot" />
                    <Database style={{ width: 11, height: 11 }} />
                    RAG 检索
                  </button>
                  <button
                    type="button"
                    className={`chat-opt-toggle${session?.deep_search_enabled ? ' on' : ''}`}
                    onClick={handleToggleDeepSearch}
                    title={session?.deep_search_enabled ? '已启用联网搜索（点击关闭）' : '启用联网搜索'}
                  >
                    <div className="chat-opt-dot" />
                    <Globe style={{ width: 11, height: 11 }} />
                    联网搜索
                  </button>
                </>
              ) : (
                <>
                  <label className={`chat-opt-toggle${ragEnabled ? ' on' : ''}`}>
                    <input type="checkbox" checked={ragEnabled} onChange={e => setRagEnabled(e.target.checked)} />
                    <div className="chat-opt-dot" />
                    <Database style={{ width: 11, height: 11 }} />
                    RAG 检索
                  </label>
                  <label className={`chat-opt-toggle${deepSearch ? ' on' : ''}`}>
                    <input type="checkbox" checked={deepSearch} onChange={e => setDeepSearch(e.target.checked)} />
                    <div className="chat-opt-dot" />
                    <Globe style={{ width: 11, height: 11 }} />
                    联网搜索
                  </label>
                </>
              )}
            </div>
          </div>
        </div>

        <input
          ref={fileRef} type="file" accept=".pdf,.docx,.md,.txt,.pptx,.doc"
          style={{ display: 'none' }}
          onChange={e => { setReportFile(e.target.files?.[0] ?? null); e.target.value = '' }}
        />
      </div>

      {/* ── Modals ── */}
      {confirmDel && (
        <Confirm
          title="删除会话"
          message={`确认删除「${confirmDel.title || '无标题'}」？该会话的所有消息和记录将永久删除。`}
          danger loading={false}
          onConfirm={handleDeleteSession}
          onCancel={() => setConfirmDel(null)}
        />
      )}

      {showLogoutConfirm && (
        <Confirm
          title="退出登录"
          message="确认退出登录？退出后需重新登录才能使用。"
          loading={false}
          onConfirm={doLogout}
          onCancel={() => setShowLogoutConfirm(false)}
        />
      )}

      {showChangePwd && <ChangePasswordModal onClose={() => setShowChangePwd(false)} />}
      {showBindEmail && <BindEmailModal onClose={() => setShowBindEmail(false)} />}

      {/* Model pickers — rendered via portal, outside stacking context */}
      {sessionPickerAnchor && (
        <CascadingPicker
          anchorRect={sessionPickerAnchor}
          groups={modelPickerGroups}
          defaultItem={modelPickerDefault}
          selectedId={session?.current_user_llm_config_id ?? null}
          onSelect={id => handleChangeSessionModel(id)}
          onClose={() => setSessionPickerAnchor(null)}
        />
      )}
      {newPickerAnchor && (
        <CascadingPicker
          anchorRect={newPickerAnchor}
          groups={modelPickerGroups}
          defaultItem={modelPickerDefault}
          selectedId={selectedConfig}
          onSelect={id => { setSelectedConfig(id); setNewPickerAnchor(null) }}
          onClose={() => setNewPickerAnchor(null)}
        />
      )}

      {showDeleteAccount && (
        <Confirm
          title="注销账户"
          message="确认注销账户？此操作不可撤销，账户及所有相关数据将被永久删除。"
          danger loading={false}
          onConfirm={doDeleteAccount}
          onCancel={() => setShowDeleteAccount(false)}
        />
      )}

      {showDocModal && (
        <DocModal
          sessionId={currentId}
          pendingDocs={pendingDocs}
          onPendingChange={setPendingDocs}
          sessionRefs={sessionRefs}
          onRefsChange={setSessionRefs}
          ragEnabled={ragEnabled || (session?.rag_enabled ?? false)}
          onClose={() => setShowDocModal(false)}
        />
      )}

      {showOutlineEditor && currentId && (() => {
        const outlineMsg = [...messages].reverse().find(m => m.outline_json)
        const outlineJson = outlineMsg?.outline_json ?? {}
        return (
          <OutlineEditor
            initialOutline={outlineJson as Record<string, unknown>}
            sessionId={currentId}
            onClose={() => setShowOutlineEditor(false)}
            onConfirmed={handleOutlineConfirmed}
          />
        )
      })()}
    </div>
  )
}
