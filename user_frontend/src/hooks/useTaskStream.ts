import { useCallback, useEffect, useRef, useState } from 'react'
import { getStreamTicket } from '../api'

/**
 * 任务 SSE 流式订阅 Hook。
 *
 * 封装 `GET /api/tasks/{id}/stream` 的 EventSource 生命周期，对外暴露流式状态与
 * 一个命令式的 `start()`。把 SSE 的协议细节（帧解析、心跳、重连、清理）收敛在此处，
 * 让页面组件只关心"什么时候开始订阅"和"任务结束后做什么"。
 *
 * 后端事件契约（task_controller._sse_generator）：
 *   event: token    data: {"token": "片段"}
 *   event: progress data: {"current", "total", "percentage"}
 *   event: done     data: {message_id, text, outline, slides, next_task_id?}
 *   event: error    data: {"error": "..."}
 *
 * 关键修复（相对旧实现）：
 *   - token 事件的 data 是 JSON 对象，必须 JSON.parse 取 .token，
 *     旧实现直接字符串拼接导致页面显示 `{"token":"x"}` 字面量。
 *   - done 事件只解析一次。
 *   - 区分"任务正常结束(done/error)"与"网络中断"：仅后者做有限次指数退避重连，
 *     避免任务已结束还无谓重连。
 */

/** done 事件回调的最小载荷：用于链式触发下一任务，业务数据由组件自行重新拉取。 */
export interface TaskStreamDone {
  next_task_id?: number | null
  [k: string]: unknown
}

export interface UseTaskStreamOptions {
  /** 任务正常完成（done 事件）时触发；done.next_task_id 存在则 hook 会自动续订。 */
  onDone?: (sessionId: number, done: TaskStreamDone) => void
  /** 任务失败（error 事件）时触发。 */
  onError?: (sessionId: number, message: string) => void
  /** 重连彻底放弃（超过最大次数）时触发。 */
  onGiveUp?: (sessionId: number) => void
  /** 最大重连次数，默认 3。 */
  maxRetries?: number
}

export interface TaskStreamState {
  streaming: boolean
  streamText: string
  progress: number | null
  taskId: number | null
}

export interface UseTaskStreamResult extends TaskStreamState {
  /** 开始订阅某任务的流；会先关闭已有订阅。 */
  start: (taskId: number, sessionId: number) => void
  /** 主动停止并清空流式状态（如切换会话）。 */
  stop: () => void
}

const RETRY_BASE_DELAY_MS = 1000
const RETRY_MAX_DELAY_MS = 8000

export function useTaskStream(options: UseTaskStreamOptions = {}): UseTaskStreamResult {
  const { maxRetries = 3 } = options

  const [streaming, setStreaming] = useState(false)
  const [streamText, setStreamText] = useState('')
  const [progress, setProgress] = useState<number | null>(null)
  const [taskId, setTaskId] = useState<number | null>(null)

  const esRef = useRef<EventSource | null>(null)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // 累积的流式文本——用 ref 而非闭包变量，重连后可继续累积同一段内容。
  const accumulatedRef = useRef('')
  // 当前订阅上下文，重连时复用。
  const ctxRef = useRef<{ taskId: number; sessionId: number; retries: number } | null>(null)
  // 连接代次：每次 teardown/start 自增，用于丢弃"换票据期间已被取消/替换"的过期连接。
  const genRef = useRef(0)

  // 把回调放进 ref，保证 EventSource 监听器始终调用到最新的业务回调，避免 stale closure。
  // 在 effect 中同步（而非 render 期间写 ref），符合 React 的 ref 使用约束。
  const optionsRef = useRef(options)
  useEffect(() => { optionsRef.current = options })

  const clearTimers = useCallback(() => {
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current)
      retryTimerRef.current = null
    }
  }, [])

  const teardown = useCallback(() => {
    clearTimers()
    // 代次自增：使任何在途的换票据请求在 resolve 后识别到自己已过期，不再开连接。
    genRef.current += 1
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }
  }, [clearTimers])

  const stop = useCallback(() => {
    teardown()
    ctxRef.current = null
    accumulatedRef.current = ''
    setStreaming(false)
    setStreamText('')
    setProgress(null)
    setTaskId(null)
  }, [teardown])

  // 内部连接函数。done 链式续订与 onerror 重连都需要递归调用 connect 自身，
  // 通过 connectRef（在 effect 中同步）间接调用，既避免把 connect 列入自身依赖，
  // 也满足"不在 render 期间写 ref"的约束。
  const connectRef = useRef<(taskId: number, sessionId: number) => void | Promise<void>>(() => {})

  const connect = useCallback(async (tid: number, sessionId: number) => {
    teardown()
    // 认领本次连接的代次；换票据是异步的，期间若发生 stop/新 connect，代次会变化。
    const myGen = genRef.current
    setTaskId(tid)
    setStreaming(true)
    setProgress(null)

    // 有限次指数退避重连：网络中断与"换票据失败"共用此逻辑。
    const scheduleRetry = () => {
      const ctx = ctxRef.current
      if (!ctx) return
      teardown()
      setStreaming(false)
      if (ctx.retries >= maxRetries) {
        ctxRef.current = null
        setProgress(null)
        setTaskId(null)
        optionsRef.current.onGiveUp?.(sessionId)
        return
      }
      const delay = Math.min(RETRY_BASE_DELAY_MS * 2 ** ctx.retries, RETRY_MAX_DELAY_MS)
      ctx.retries += 1
      retryTimerRef.current = setTimeout(() => {
        connectRef.current(ctx.taskId, ctx.sessionId)
      }, delay)
    }

    // EventSource 无法携带 Authorization 头，先换取一次性票据再用 ?ticket= 连接。
    let ticket: string
    try {
      const resp = await getStreamTicket(tid)
      ticket = resp.ticket
    } catch {
      // 换票据失败（网络/鉴权）：按重连逻辑处理，超限则放弃。
      if (genRef.current === myGen) scheduleRetry()
      return
    }

    // 换票据期间若已被取消或被新的连接替换，丢弃本次结果。
    if (genRef.current !== myGen) return

    const es = new EventSource(`/api/tasks/${tid}/stream?ticket=${encodeURIComponent(ticket)}`)
    esRef.current = es

    es.addEventListener('token', e => {
      try {
        const payload = JSON.parse((e as MessageEvent).data) as { token?: string }
        if (payload.token) {
          accumulatedRef.current += payload.token
          setStreamText(accumulatedRef.current)
        }
      } catch {
        /* 单帧解析失败忽略，不影响后续 token */
      }
    })

    es.addEventListener('progress', e => {
      try {
        const d = JSON.parse((e as MessageEvent).data) as { percentage?: number }
        setProgress(d.percentage ?? null)
      } catch {
        /* ignore */
      }
    })

    es.addEventListener('done', e => {
      let done: TaskStreamDone = {}
      try {
        done = JSON.parse((e as MessageEvent).data) as TaskStreamDone
      } catch {
        /* 即使 done 数据异常也要正常收尾 */
      }
      teardown()
      accumulatedRef.current = ''
      setStreaming(false)
      setStreamText('')
      setProgress(null)

      const nextId = done.next_task_id
      if (typeof nextId === 'number') {
        // 链式续订下一任务（如 requirement_collection → outline_generation）
        ctxRef.current = { taskId: nextId, sessionId, retries: 0 }
        connectRef.current(nextId, sessionId)
      } else {
        ctxRef.current = null
        setTaskId(null)
      }

      optionsRef.current.onDone?.(sessionId, done)
    })

    es.addEventListener('error', e => {
      // 服务端显式 error 事件（区别于 EventSource 的网络 onerror）：任务失败，终止不重连。
      let msg = '任务执行失败'
      try {
        const d = JSON.parse((e as MessageEvent).data) as { error?: string }
        if (d.error) msg = d.error
      } catch {
        /* ignore */
      }
      teardown()
      stop()
      optionsRef.current.onError?.(sessionId, msg)
    })

    es.onerror = () => {
      // 网络层中断：EventSource 默认自动重连不可控且会重复触发，
      // 这里改为手动有限次指数退避重连（与换票据失败共用 scheduleRetry）。
      scheduleRetry()
    }
  }, [teardown, stop, maxRetries])

  // 在 effect 中同步 connectRef，供 connect 内部递归调用（done 链式 / 重连）。
  useEffect(() => { connectRef.current = connect }, [connect])

  const start = useCallback((tid: number, sessionId: number) => {
    accumulatedRef.current = ''
    setStreamText('')
    ctxRef.current = { taskId: tid, sessionId, retries: 0 }
    void connect(tid, sessionId)
  }, [connect])

  // 卸载时彻底清理，避免泄漏 EventSource 与定时器。
  useEffect(() => () => { teardown() }, [teardown])

  return { streaming, streamText, progress, taskId, start, stop }
}
