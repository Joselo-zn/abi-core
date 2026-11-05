import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Check, ChevronDown, ChevronRight, Info, Pencil, X } from "lucide-react"

// Plan review card — renders abi_core.common.utils.build_plan_view() output
// and answers through the same "plan_confirm" action callback the plain
// buttons use. See
// .abi/specs/not-implemented/ux/chainlit-plan-review-card.md.

const TEXT = {
  es: {
    heading: "Plan propuesto",
    steps: (n) => (n === 1 ? "1 paso" : `${n} pasos`),
    files: (n) => (n === 1 ? "1 archivo" : `${n} archivos`),
    approve: "Aprobar y ejecutar",
    modify: "Modificar",
    reject: "Rechazar",
    modifyPrompt: "¿Qué querés cambiar?",
    modifyPlaceholder: "Por ejemplo: que los fantasmas tengan distintas velocidades",
    sendChanges: "Enviar cambios",
    cancel: "Cancelar",
    instruction: "Instrucción para el agente",
    uses: (list) => `Usa el resultado de: ${list}`,
    newAgent: "Se crea un agente nuevo",
    agent: (name) => `Agente: ${name}`,
    directTool: (tool) => `Herramienta directa (${tool === "write_pdf" ? "PDF" : tool})`,
    model: (m) => `Modelo: ${m}`,
    modelDownload: (m) => `El modelo ${m} se descargará antes de empezar.`,
    approved: "Aprobado",
    rejected: "Rechazado",
    modifySent: "Cambios pedidos",
    showSteps: "Ver pasos",
    hideSteps: "Ocultar pasos",
  },
  en: {
    heading: "Proposed plan",
    steps: (n) => (n === 1 ? "1 step" : `${n} steps`),
    files: (n) => (n === 1 ? "1 file" : `${n} files`),
    approve: "Approve and run",
    modify: "Modify",
    reject: "Reject",
    modifyPrompt: "What should change?",
    modifyPlaceholder: "For example: give each ghost a different speed",
    sendChanges: "Send changes",
    cancel: "Cancel",
    instruction: "Instruction for the agent",
    uses: (list) => `Uses the output of: ${list}`,
    newAgent: "A new agent will be created",
    agent: (name) => `Agent: ${name}`,
    directTool: (tool) => `Direct tool (${tool === "write_pdf" ? "PDF" : tool})`,
    model: (m) => `Model: ${m}`,
    modelDownload: (m) => `Model ${m} will be downloaded before starting.`,
    approved: "Approved",
    rejected: "Rejected",
    modifySent: "Changes requested",
    showSteps: "Show steps",
    hideSteps: "Hide steps",
  },
}

// Only Tailwind classes already compiled into Chainlit's own stylesheet work
// inside a custom element (no JIT for this file) — arbitrary values like
// text-[hsl(...)] and many utilities (gap-x-*, pl-10, sm:inline, ...) are
// silently missing. Semantic token classes below exist; anything else is an
// inline style.
const muted = "text-muted-foreground"
const border = "border-border"
const chip = { flexShrink: 0 }

function StepRow({ step, t, open, onToggle, first }) {
  const Chevron = open ? ChevronDown : ChevronRight
  return (
    <li className={first ? "" : `border-t ${border}`}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="w-full flex items-center gap-3 py-2 text-left hover:bg-accent rounded-md px-1"
      >
        <span style={chip} className="w-6 h-6 rounded-full border border-primary text-primary text-xs flex items-center justify-center">
          {step.index}
        </span>
        <span className="flex-1 min-w-0 text-sm font-medium truncate">{step.title}</span>
        {step.deliverable && (
          <span style={chip} className={`font-mono text-xs px-2 py-0.5 rounded border ${border} ${muted}`}>
            {step.deliverable.tag}
          </span>
        )}
        <Chevron style={chip} className={`h-4 w-4 ${muted}`} />
      </button>
      {open && (
        <div style={{ paddingLeft: "2.5rem", paddingBottom: "0.75rem" }} className="pr-1 flex flex-col gap-2 text-sm">
          <div>
            <div style={{ letterSpacing: "0.04em" }} className={`text-xs uppercase ${muted}`}>{t.instruction}</div>
            <p className="whitespace-pre-wrap break-words">{step.detail}</p>
          </div>
          <div style={{ columnGap: "0.75rem", rowGap: "0.25rem" }} className={`flex flex-wrap text-xs ${muted}`}>
            {step.depends_on && step.depends_on.length > 0 && (
              <span>{t.uses(step.depends_on.join(", "))}</span>
            )}
            <span>
              {step.direct_tool
                ? t.directTool(step.direct_tool)
                : step.agent
                ? t.agent(step.agent)
                : t.newAgent}
            </span>
            {step.model && <span>{t.model(step.model)}</span>}
          </div>
        </div>
      )}
    </li>
  )
}

export default function PlanReview() {
  const t = TEXT[props.lang] || TEXT.en
  const view = props.view || {}
  const steps = view.steps || []
  const deliverables = view.deliverables || []
  const notices = view.notices || []
  const state = props.state || "pending"
  const decided = state !== "pending"

  // Expand/collapse and the feedback draft are local state on purpose:
  // updateElement() re-renders the element from the backend, which would
  // drop the textarea's focus on every keystroke (same reason as in
  // ClarificationForm.jsx). updateElement is only called once, on decision.
  const [openSteps, setOpenSteps] = useState({})
  const [listOpen, setListOpen] = useState(!decided)
  const [modifying, setModifying] = useState(false)
  const [feedback, setFeedback] = useState("")

  const toggleStep = (index) => setOpenSteps((prev) => ({ ...prev, [index]: !prev[index] }))

  const decide = (choice, extra) => {
    const nextState = { approve: "approved", reject: "rejected", modify: "modify_sent" }[choice]
    updateElement(Object.assign(props, { state: nextState }, extra || {}))
    callAction({ name: "plan_confirm", payload: { choice, ...(extra || {}) } })
  }

  const badge = {
    approved: { icon: Check, label: t.approved, cls: "text-primary" },
    rejected: { icon: X, label: t.rejected, cls: muted },
    modify_sent: { icon: Pencil, label: t.modifySent, cls: muted },
  }[state]

  const summary = [t.steps(steps.length), deliverables.length > 0 ? t.files(deliverables.length) : null]
    .filter(Boolean)
    .join(" · ")

  return (
    <div style={{ maxWidth: "42rem" }} className={`w-full rounded-lg border ${border} bg-card text-card-foreground p-4 flex flex-col gap-3`}>
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <span className="font-semibold">{t.heading}</span>
          {badge && (
            <span className={`inline-flex items-center gap-1 text-sm ${badge.cls}`}>
              <badge.icon className="h-4 w-4" />
              {badge.label}
            </span>
          )}
        </div>
        {view.objective && <p className="text-sm">{view.objective}</p>}
        <div className={`flex items-center gap-3 text-xs ${muted}`}>
          <span>{summary}</span>
          {decided && steps.length > 0 && (
            <button type="button" style={{ textDecoration: "underline" }} onClick={() => setListOpen(!listOpen)}>
              {listOpen ? t.hideSteps : t.showSteps}
            </button>
          )}
        </div>
      </div>

      {listOpen && steps.length > 0 && (
        <ol className="flex flex-col">
          {steps.map((step, i) => (
            <StepRow
              first={i === 0}
              key={step.task_id || step.index}
              step={step}
              t={t}
              open={!!openSteps[step.index]}
              onToggle={() => toggleStep(step.index)}
            />
          ))}
        </ol>
      )}

      {!decided && notices.length > 0 && (
        <div className={`flex flex-col gap-1 text-sm ${muted}`}>
          {notices.map((n, i) => (
            <div key={i} className="flex items-start gap-2">
              <Info style={chip} className="h-4 w-4 mt-0.5" />
              <span>{n.code === "model_download" ? t.modelDownload(n.model) : n.code}</span>
            </div>
          ))}
        </div>
      )}

      {state === "modify_sent" && props.feedback && (
        <p className={`text-sm italic ${muted}`}>“{props.feedback}”</p>
      )}

      {!decided && !modifying && (
        <div style={{ paddingTop: "0.25rem" }} className="flex flex-wrap gap-2">
          <Button onClick={() => decide("approve")}>
            <Check style={{ marginRight: "0.25rem" }} className="h-4 w-4" />
            {t.approve}
          </Button>
          <Button variant="outline" onClick={() => setModifying(true)}>
            <Pencil style={{ marginRight: "0.25rem" }} className="h-4 w-4" />
            {t.modify}
          </Button>
          <Button variant="ghost" onClick={() => decide("reject")}>
            {t.reject}
          </Button>
        </div>
      )}

      {!decided && modifying && (
        <div style={{ paddingTop: "0.25rem" }} className="flex flex-col gap-2">
          <label className="text-sm font-medium" htmlFor="plan-review-feedback">
            {t.modifyPrompt}
          </label>
          <textarea
            id="plan-review-feedback"
            autoFocus
            rows={3}
            value={feedback}
            placeholder={t.modifyPlaceholder}
            onChange={(e) => setFeedback(e.target.value)}
            className={`border rounded-md p-2 text-sm bg-background text-foreground ${border}`}
          />
          <div className="flex flex-wrap gap-2">
            <Button disabled={!feedback.trim()} onClick={() => decide("modify", { feedback: feedback.trim() })}>
              {t.sendChanges}
            </Button>
            <Button variant="ghost" onClick={() => setModifying(false)}>
              {t.cancel}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
