import React, { useState, useRef, useEffect, useCallback } from 'react'

const SUGGESTIONS = [
  "What are the top fintech unicorns?",
  "Tell me about SaaS startups in Bangalore",
  "What is DPIIT recognition?",
  "Which sectors are growing fastest?",
  "Compare edtech vs healthtech",
  "Latest news about Indian startups 2025",
]

// ─── XSS Prevention: escape HTML special chars ────────────────────────────────
function escapeHtml(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
}

// ─── XSS Prevention: strip script tags and event handlers ─────────────────────
function sanitizeChatContent(text) {
  if (!text) return ''
  let t = text
  // Remove script tags
  t = t.replace(/<script[^>]*>.*?<\/script>/gi, '')
  // Remove iframe tags
  t = t.replace(/<iframe[^>]*>.*?<\/iframe>/gi, '')
  // Remove event handlers (onerror, onclick, etc.)
  t = t.replace(/\son\w+\s*=\s*["']?[^"'>]*["']?/gi, '')
  // Remove javascript: and data: URLs
  t = t.replace(/(javascript|data|vbscript):/gi, '')
  // Remove meta refresh
  t = t.replace(/<meta[^>]*http-equiv\s*=\s*["']?refresh["']?[^>]*>/gi, '')
  return t
}

// ─── Render sanitized text with basic Markdown (no raw HTML) ──────────────────
function SafeMarkdown({ text }) {
  if (!text) return null
  const sanitized = sanitizeChatContent(text)
  // Convert **bold**, *italic*, `code`, and bullet points to HTML safely
  let html = escapeHtml(sanitized)
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Bullet points (simple)
    .replace(/^\s*-\s+/gm, '• ')
    // Numbered lists
    .replace(/^\s*(\d+)\.\s+/gm, '$1. ')
    // Line breaks
    .replace(/\n/g, '<br>')

  return <span dangerouslySetInnerHTML={{ __html: html }} />
}

export default function ChatWidget({ onClose }) {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: "👋 Hi! I'm Bharat Tech Atlas AI. Ask me about Indian startups, sectors, funding trends, or any company!" }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [retryCount, setRetryCount] = useState(0)
  const scrollRef = useRef(null)
  const messagesRef = useRef(messages)
  useEffect(() => { messagesRef.current = messages }, [messages])

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const clearChat = useCallback(() => {
    setMessages([
      { role: 'assistant', content: "👋 Hi! I'm Bharat Tech Atlas AI. Ask me about Indian startups, sectors, funding trends, or any company!" }
    ])
    setError(null)
    setRetryCount(0)
    setInput('')
  }, [])

  const sendMessage = useCallback(async (text, isRetry = false) => {
    if (!text.trim() || loading) return
    const userMsg = { role: 'user', content: text }

    if (!isRetry) {
      setMessages(prev => [...prev, userMsg])
      setInput('')
      setError(null)
      setRetryCount(0)
    }
    setLoading(true)

    const currentMessages = [...messagesRef.current, ...(isRetry ? [] : [userMsg])]
    const payload = {
      messages: currentMessages.map(m => ({ role: m.role, content: m.content })),
      stream: false,
    }

    try {
      const resp = await fetch('/api/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!resp.ok) {
        const errText = await resp.text()
        throw new Error(`HTTP ${resp.status}: ${errText}`)
      }
      const data = await resp.json()
      const safeContent = sanitizeChatContent(data.content) || 'Sorry, I had trouble responding. Try again!'
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: safeContent
      }])
      setError(null)
      setRetryCount(0)
    } catch (err) {
      console.error('Chat error:', err)
      setError({ message: err.message, lastText: text })
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '⚠️ Network error. Please try again in a moment.',
        isError: true
      }])
    } finally {
      setLoading(false)
    }
  }, [loading])

  const handleRetry = useCallback(() => {
    if (error?.lastText) {
      setRetryCount(c => c + 1)
      // Remove the last error message
      setMessages(prev => prev.filter(m => !m.isError))
      sendMessage(error.lastText, true)
    }
  }, [error, sendMessage])

  const QUICK_ACTIONS = [
    { label: 'Top Unicorns', message: 'Show me the top unicorn startups in India' },
    { label: 'My State', message: 'Show me startups in my state' },
    { label: 'Mentors', message: 'Find mentors for startups' },
    { label: 'Investors', message: 'Find investors for startups' },
  ]

  return (
    <div className="fixed bottom-4 right-4 z-50 w-[380px] max-w-[calc(100vw-2rem)] h-[560px] max-h-[calc(100vh-2rem)] bg-atlas-bg border border-atlas-border rounded-2xl shadow-2xl flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-atlas-border bg-atlas-surface">
        <div className="flex items-center gap-2">
          <span className="text-lg">🤖</span>
          <div>
            <h3 className="text-sm font-semibold text-atlas-text">Bharat Tech Atlas AI</h3>
            <p className="text-[10px] text-atlas-muted">Powered by Qwen2.5-0.5B + Web Search</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={clearChat}
            className="text-atlas-muted hover:text-atlas-text p-1 rounded-md hover:bg-atlas-border/50 transition-colors"
            title="Clear chat"
            aria-label="Clear chat"
          >
            🗑️
          </button>
          <button onClick={onClose} className="text-atlas-muted hover:text-atlas-text p-1 rounded-md hover:bg-atlas-border/50 transition-colors" aria-label="Close chat">✕</button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed whitespace-pre-wrap ${
              m.role === 'user'
                ? 'bg-brand-500/20 text-brand-300 rounded-br-none'
                : m.isError
                  ? 'bg-red-500/10 text-red-300 rounded-bl-none border border-red-500/20'
                  : 'bg-atlas-surface text-atlas-muted rounded-bl-none'
            }`}>
              {m.role === 'user' ? (
                <span>{m.content}</span>
              ) : (
                <SafeMarkdown text={m.content} />
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-atlas-surface rounded-xl rounded-bl-none px-3 py-2.5">
              <div className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 bg-brand-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-1.5 h-1.5 bg-brand-400 rounded-full animate-bounce" style={{ animationDelay: '120ms' }} />
                <span className="w-1.5 h-1.5 bg-brand-400 rounded-full animate-bounce" style={{ animationDelay: '240ms' }} />
                <span className="ml-1 text-[10px] text-atlas-muted/60">Typing…</span>
              </div>
            </div>
          </div>
        )}
        {error && !loading && (
          <div className="flex justify-center">
            <button
              onClick={handleRetry}
              disabled={retryCount >= 3}
              className="text-[10px] px-3 py-1.5 rounded-full bg-brand-500/10 text-brand-400 hover:bg-brand-500/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {retryCount >= 3 ? 'Max retries reached' : `↻ Retry${retryCount > 0 ? ` (${retryCount})` : ''}`}
            </button>
          </div>
        )}
        <div ref={scrollRef} />
      </div>

      {/* Suggestions */}
      {messages.length < 3 && (
        <div className="px-3 pb-2 flex flex-wrap gap-1.5">
          {SUGGESTIONS.map(s => (
            <button key={s} onClick={() => sendMessage(s)}
              className="text-[10px] px-2 py-1 rounded-full bg-atlas-surface border border-atlas-border text-atlas-muted hover:text-atlas-text hover:border-brand-500/30 transition-colors">
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Quick Actions */}
      <div className="px-3 pb-2 border-t border-atlas-border/50 pt-2">
        <div className="flex flex-wrap gap-1.5">
          {QUICK_ACTIONS.map(action => (
            <button
              key={action.label}
              onClick={() => sendMessage(action.message)}
              disabled={loading}
              className="text-[10px] px-2.5 py-1 rounded-full bg-brand-500/10 text-brand-400 hover:bg-brand-500/20 transition-colors disabled:opacity-40 font-medium"
            >
              {action.label}
            </button>
          ))}
        </div>
      </div>

      {/* Input */}
      <div className="px-3 py-2 border-t border-atlas-border flex gap-2">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && sendMessage(input)}
          placeholder="Ask about startups, sectors, funding, latest news..."
          maxLength={2000}
          className="flex-1 bg-atlas-surface border border-atlas-border rounded-lg px-3 py-2 text-xs text-atlas-text placeholder:text-atlas-muted/50 focus:outline-none focus:border-brand-500/50"
        />
        <button onClick={() => sendMessage(input)} disabled={loading || !input.trim()}
          className="px-3 py-2 bg-brand-500/20 text-brand-400 rounded-lg text-xs font-medium hover:bg-brand-500/30 disabled:opacity-30 transition-colors">
          Send
        </button>
      </div>
    </div>
  )
}
