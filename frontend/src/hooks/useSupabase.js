import { useEffect, useCallback, useState } from 'react'

/**
 * Bharat Tech Atlas v4.10.00 — Supabase Realtime Hook
 * 
 * Connects to Supabase WebSocket to listen for live entity inserts.
 * Displays toast notifications when new entities are registered.
 * 
 * Usage:
 *   const { liveEntities, toasts, clearToast } = useLiveEntities()
 */

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || 'https://empzzqlwsxlajgqmbkdp.supabase.co'
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || 'sb_publishable_U1dQ4_Hs7v_A3JMPaABtnw_MhVU4Bf0'

export function useLiveEntities(enabled = true) {
  const [liveEntities, setLiveEntities] = useState([])
  const [toasts, setToasts] = useState([])
  const [connected, setConnected] = useState(false)

  const addToast = useCallback((entity) => {
    const id = Date.now()
    const typeEmoji = {
      startup: '🚀', mentor: '🧠', investor: '💰',
      incubator: '🧪', accelerator: '⚡', corporate: '🏛️',
      government_body: '🏛️', sme: '🏢', college_ecell: '🎓',
    }[entity.entity_type] || '📍'

    const toast = {
      id,
      type: entity.entity_type,
      emoji: typeEmoji,
      name: entity.name,
      city: entity.city,
      state: entity.state,
      message: `${typeEmoji} New ${entity.entity_type} in ${entity.city || entity.state || 'India'}: ${entity.name}`,
      timestamp: new Date().toLocaleTimeString(),
    }

    setToasts(prev => [...prev.slice(-4), toast])

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 5000)
  }, [])

  const clearToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  useEffect(() => {
    if (!enabled) return

    let channel = null
    let ws = null

    const connect = () => {
      try {
        // Use Supabase REST API for polling fallback (if WebSocket not available)
        // Or use native WebSocket to Supabase Realtime
        const wsUrl = `${SUPABASE_URL.replace('https://', 'wss://')}/realtime/v1/websocket?apikey=${SUPABASE_ANON_KEY}&vsn=1.0.0`
        ws = new WebSocket(wsUrl)

        ws.onopen = () => {
          setConnected(true)
          // Subscribe to entities table changes
          const joinMsg = {
            topic: 'realtime:public:entities',
            event: 'phx_join',
            payload: {},
            ref: '1',
          }
          ws.send(JSON.stringify(joinMsg))
        }

        ws.onmessage = (event) => {
          const msg = JSON.parse(event.data)
          if (msg.payload && msg.payload.data) {
            const change = msg.payload.data
            if (change.type === 'INSERT') {
              const entity = change.record
              setLiveEntities(prev => [entity, ...prev.slice(0, 99)])
              addToast(entity)
            }
          }
        }

        ws.onclose = () => {
          setConnected(false)
          // Reconnect after 5 seconds
          setTimeout(connect, 5000)
        }

        ws.onerror = (err) => {
          console.warn('Supabase realtime error:', err)
          setConnected(false)
        }
      } catch (e) {
        console.warn('Supabase realtime connection failed:', e)
      }
    }

    connect()

    return () => {
      if (ws) ws.close()
    }
  }, [enabled, addToast])

  return { liveEntities, toasts, clearToast, connected }
}

/**
 * Hook for fetching entity detail lazily (full profile on click)
 */
export function useEntityDetail(slug) {
  const [entity, setEntity] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!slug) return

    setLoading(true)
    setError(null)

    fetch(`/api/entities/detail/${slug}`)
      .then(r => r.json())
      .then(data => {
        setEntity(data)
        setLoading(false)
      })
      .catch(err => {
        setError(err.message)
        setLoading(false)
      })
  }, [slug])

  return { entity, loading, error }
}

/**
 * Hook for SSE chat streaming
 */
export function useSSEChat() {
  const [messages, setMessages] = useState([])
  const [streaming, setStreaming] = useState(false)
  const [currentStream, setCurrentStream] = useState('')
  const abortRef = useRef(null)

  const sendMessage = useCallback(async (messagesList) => {
    setStreaming(true)
    setCurrentStream('')
    const abortController = new AbortController()
    abortRef.current = abortController

    try {
      const resp = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: messagesList }),
        signal: abortController.signal,
      })

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.type === 'token') {
                setCurrentStream(prev => prev + data.text)
              } else if (data.type === 'done') {
                setStreaming(false)
              } else if (data.type === 'error') {
                setStreaming(false)
                console.error('SSE error:', data.text)
              }
            } catch (e) {
              // Ignore malformed lines
            }
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.error('Chat stream error:', err)
      }
      setStreaming(false)
    }
  }, [])

  const abort = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort()
    }
    setStreaming(false)
  }, [])

  return { messages, streaming, currentStream, sendMessage, abort, setMessages }
}

import { useRef } from 'react'

export { useRef }
