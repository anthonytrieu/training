import { useEffect, useRef, useState } from "react"
import ReactMarkdown from "react-markdown"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

interface ChatMessage {
  role: "user" | "assistant"
  text: string
  tools: string[]
  streaming?: boolean
}

interface SseEvent {
  type: "text" | "tool" | "done" | "error"
  text?: string
  label?: string
  message?: string
  session_id?: string
}

const SUGGESTIONS = [
  "How was my last ride?",
  "Am I recovered enough for intervals tomorrow?",
  "How is this week tracking against my Whistler plan?",
  "What should I focus on this weekend?",
]

async function* readSse(resp: Response): AsyncGenerator<SseEvent> {
  const reader = resp.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split("\n\n")
    buffer = parts.pop() ?? ""
    for (const part of parts) {
      const line = part.trim()
      if (line.startsWith("data: ")) yield JSON.parse(line.slice(6)) as SseEvent
    }
  }
}

export default function Coach() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [busy, setBusy] = useState(false)
  const sessionRef = useRef<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [messages])

  async function send(text: string) {
    const question = text.trim()
    if (!question || busy) return
    setBusy(true)
    setInput("")
    setMessages((m) => [
      ...m,
      { role: "user", text: question, tools: [] },
      { role: "assistant", text: "", tools: [], streaming: true },
    ])

    const update = (fn: (last: ChatMessage) => ChatMessage) =>
      setMessages((m) => [...m.slice(0, -1), fn(m[m.length - 1])])

    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: question, session_id: sessionRef.current }),
      })
      if (!resp.ok || !resp.body) throw new Error(`Chat request failed (${resp.status})`)
      for await (const event of readSse(resp)) {
        if (event.type === "text" && event.text) {
          update((last) => ({ ...last, text: last.text + event.text }))
        } else if (event.type === "tool" && event.label) {
          update((last) =>
            last.tools.at(-1) === event.label ? last : { ...last, tools: [...last.tools, event.label!] },
          )
        } else if (event.type === "done") {
          if (event.session_id) sessionRef.current = event.session_id
          update((last) => ({ ...last, streaming: false }))
        } else if (event.type === "error") {
          update((last) => ({
            ...last,
            streaming: false,
            text: last.text || `⚠ ${event.message ?? "Something went wrong."}`,
          }))
        }
      }
    } catch (e) {
      update((last) => ({
        ...last,
        streaming: false,
        text: last.text || `⚠ ${e instanceof Error ? e.message : "Chat failed."}`,
      }))
    } finally {
      setBusy(false)
      update((last) => ({ ...last, streaming: false }))
    }
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-0px)] max-w-3xl flex-col p-6">
      <div className="mb-2">
        <h1 className="text-xl font-semibold tracking-tight">Coach</h1>
        <p className="text-sm text-muted-foreground">
          Claude with live access to your Garmin data. Advice, not medicine.
        </p>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto py-4 pr-1">
        {messages.length === 0 && (
          <div className="mt-10 flex flex-col items-center gap-2">
            <p className="mb-2 text-sm text-muted-foreground">Try asking:</p>
            {SUGGESTIONS.map((s) => (
              <Button key={s} variant="outline" size="sm" onClick={() => send(s)}>
                {s}
              </Button>
            ))}
          </div>
        )}
        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-4 py-2 text-sm text-primary-foreground">
                {m.text}
              </div>
            </div>
          ) : (
            <div key={i} className="flex flex-col gap-1.5">
              {m.tools.map((t, j) => (
                <div key={j} className="flex items-center gap-2 pl-1 text-xs text-muted-foreground">
                  <span className="inline-block size-1.5 rounded-full bg-[var(--viz-load)]" />
                  {t}…
                </div>
              ))}
              {(m.text || m.streaming) && (
                <div className="max-w-[95%] rounded-2xl rounded-bl-sm border bg-card px-4 py-3">
                  <article className="prose prose-sm dark:prose-invert max-w-none">
                    <ReactMarkdown>{m.text}</ReactMarkdown>
                  </article>
                  {m.streaming && (
                    <span className="mt-1 inline-block size-2 animate-pulse rounded-full bg-muted-foreground" />
                  )}
                </div>
              )}
            </div>
          ),
        )}
      </div>

      <form
        className="flex gap-2 border-t pt-4"
        onSubmit={(e) => {
          e.preventDefault()
          send(input)
        }}
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask your coach anything about your training…"
          disabled={busy}
        />
        <Button type="submit" disabled={busy || !input.trim()}>
          {busy ? "Thinking…" : "Send"}
        </Button>
      </form>
    </div>
  )
}
