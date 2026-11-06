import { Loader2 } from "lucide-react"

// The first thing a new chat shows, before any network wait (the agent's
// session, the token sync): with everything cold, those take seconds and
// the chat would look dead. chainlit_app.on_start removes it once ready.

const TEXT = { es: "Preparando el sistema…", en: "Getting the system ready…" }

export default function Preparing() {
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 style={{ flexShrink: 0 }} className="h-4 w-4 animate-spin text-primary" />
      <span>{TEXT[props.lang] || TEXT.en}</span>
    </div>
  )
}
