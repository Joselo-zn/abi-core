import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Check, HelpCircle } from "lucide-react"

// The routing's follow-up question ("is X what you want?") when it is unsure
// or failed. Answers through the "route_clarify" action callback; the choice
// is resolved by code, never by a model. Texts come as keys + params so they
// follow the UI language. See
// .abi/specs/not-implemented/ux/routing-clarification-ui.md.

const TEXT = {
  es: {
    "plan_reply.approve": "¿Querés aprobar el plan y empezar?",
    "plan_reply.modify": "¿Querés cambiar algo del plan?",
    "plan_reply.reject": "¿Querés cancelar el plan?",
    "plan_reply.unrelated": "¿Tu mensaje es sobre otra cosa, no sobre el plan?",
    "plan_reply.unsure": "No entendí si tu mensaje es sobre el plan pendiente.",
    "delivery.which": "¿A qué entrega te referís?",
    "route.artifact_or_answer": "¿Querés que lo arme como entregable, o solo una respuesta acá?",
    "route.unsure": "No entendí bien qué querés hacer con tu mensaje.",
    "plan.approve": "Sí, aprobar",
    "plan.modify": "Quiero cambiar algo",
    "plan.reject": "No, cancelar",
    "route.unrelated": "Mi mensaje era sobre otra cosa",
    "delivery.pick": "{delivery}",
    "delivery.modify": "Modificar {delivery}",
    "delivery.new": "Ninguna, es algo nuevo",
    "route.artifact": "Armarlo (archivo o flujo)",
    "route.new_artifact": "Algo nuevo, para entregar",
    "route.answer": "Solo responder",
    yourMessage: "Tu mensaje:",
    send: "Enviar",
    cancel: "Cancelar",
    expired: "Esta pregunta ya no está vigente.",
  },
  en: {
    "plan_reply.approve": "Do you want to approve the plan and start?",
    "plan_reply.modify": "Do you want to change something in the plan?",
    "plan_reply.reject": "Do you want to cancel the plan?",
    "plan_reply.unrelated": "Is your message about something else, not the plan?",
    "plan_reply.unsure": "I couldn't tell whether your message is about the pending plan.",
    "delivery.which": "Which delivery do you mean?",
    "route.artifact_or_answer": "Should I build it as a deliverable, or just answer here?",
    "route.unsure": "I couldn't tell what you want to do with your message.",
    "plan.approve": "Yes, approve",
    "plan.modify": "I want to change something",
    "plan.reject": "No, cancel",
    "route.unrelated": "My message was about something else",
    "delivery.pick": "{delivery}",
    "delivery.modify": "Modify {delivery}",
    "delivery.new": "None, it's something new",
    "route.artifact": "Build it (file or workflow)",
    "route.new_artifact": "Something new, to deliver",
    "route.answer": "Just answer",
    yourMessage: "Your message:",
    send: "Send",
    cancel: "Cancel",
    expired: "This question is no longer current.",
  },
}

// Only Tailwind classes already compiled into Chainlit's own stylesheet work
// inside a custom element; anything else is an inline style (same rule as
// PlanReview.jsx).
const muted = "text-muted-foreground"
const border = "border-border"

function render(t, key, params) {
  const template = t[key] || key
  return template.replace(/\{(\w+)\}/g, (_, name) => (params && params[name] != null ? String(params[name]) : `{${name}}`))
}

export default function RouteClarification() {
  const t = TEXT[props.lang] || TEXT.en
  const options = props.options || []
  const state = props.state || "pending"
  const params = props.params || {}

  // Text being written lives in local state: updateElement() re-renders from
  // the backend and would drop focus on every keystroke (as in
  // ClarificationForm.jsx). updateElement is called once, on answer.
  const [openText, setOpenText] = useState(null)
  const [text, setText] = useState(props.original_message || "")

  const answer = (option, extra) => {
    updateElement(Object.assign(props, { state: "answered", answer: { option: option.id, ...(extra || {}) } }))
    callAction({ name: "route_clarify", payload: { clarify_id: props.clarify_id, option: option.id, ...(extra || {}) } })
  }

  const label = (option) => render(t, option.label_key, { ...params, ...(option.params || {}) })
  const chosen = state === "answered" && props.answer ? options.find((o) => o.id === props.answer.option) : null

  return (
    <div style={{ maxWidth: "42rem" }} className={`w-full rounded-lg border ${border} bg-card text-card-foreground p-4 flex flex-col gap-3`}>
      <div className="flex items-start gap-2">
        <HelpCircle style={{ flexShrink: 0, marginTop: "0.125rem" }} className="h-4 w-4 text-primary" />
        <span className="font-medium">{render(t, props.question_key, params)}</span>
      </div>

      {props.original_message && (
        <p className={`text-sm ${muted} truncate`}>
          {t.yourMessage} “{props.original_message}”
        </p>
      )}

      {state === "expired" && <p className={`text-sm ${muted}`}>{t.expired}</p>}

      {state === "answered" && chosen && (
        <div className="flex flex-col gap-1">
          <span className="inline-flex items-center gap-1 text-sm text-primary">
            <Check className="h-4 w-4" />
            {label(chosen)}
          </span>
          {props.answer.text && <p className={`text-sm italic ${muted}`}>“{props.answer.text}”</p>}
        </div>
      )}

      {state === "pending" && openText === null && (
        <div className="flex flex-wrap gap-2">
          {options.filter((o) => o.kind !== "link").map((option) =>
            option.kind === "text" ? (
              <Button key={option.id} variant="outline" onClick={() => setOpenText(option)}>
                {label(option)}
              </Button>
            ) : (
              <Button key={option.id} variant={option.primary ? "default" : "outline"} onClick={() => answer(option)}>
                {label(option)}
              </Button>
            )
          )}
          {options.filter((o) => o.kind === "link").map((option) => (
            <button
              key={option.id}
              type="button"
              onClick={() => answer(option)}
              style={{ textDecoration: "underline", flexBasis: "100%", textAlign: "left" }}
              className={`text-sm ${muted}`}
            >
              {label(option)}
            </button>
          ))}
        </div>
      )}

      {state === "pending" && openText !== null && (
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium" htmlFor="route-clarification-text">
            {label(openText)}
          </label>
          <textarea
            id="route-clarification-text"
            autoFocus
            rows={3}
            value={text}
            onChange={(e) => setText(e.target.value)}
            className={`border rounded-md p-2 text-sm bg-background text-foreground ${border}`}
          />
          <div className="flex flex-wrap gap-2">
            <Button disabled={!text.trim()} onClick={() => answer(openText, { text: text.trim() })}>
              {t.send}
            </Button>
            <Button variant="ghost" onClick={() => setOpenText(null)}>
              {t.cancel}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
