import { useState } from "react"
import { Button } from "@/components/ui/button"

const fieldClass =
  "border rounded-md p-2 text-sm bg-[hsl(var(--background))] text-[hsl(var(--foreground))] border-[hsl(var(--border))]"

export default function ClarificationForm() {
  const questions = props.questions || []

  // Answers live in local component state while typing — updateElement()
  // round-trips to the backend and re-renders the element from scratch,
  // which remounts the <input> DOM node and drops focus on every
  // keystroke if called from onChange. Only touch updateElement for the
  // final `submitted` flag; the answers themselves travel once, in
  // handleSubmit's sendUserMessage, not per keystroke.
  const [answers, setAnswers] = useState(props.answers || {})

  const handleChange = (id, value) => {
    setAnswers((prev) => ({ ...prev, [id]: value }))
  }

  const handleSubmit = () => {
    sendUserMessage(JSON.stringify({
      _sentinel: "__clarification_answer__",
      answers,
    }))
    updateElement(Object.assign(props, { submitted: true }))
  }

  if (props.submitted) {
    return <div className="text-sm opacity-70">Respuesta enviada.</div>
  }

  return (
    <div className="flex flex-col gap-4 w-full max-w-md">
      {questions.map((q) => (
        <div key={q.id} className="flex flex-col gap-1">
          <label className="text-sm font-medium">{q.question}</label>
          {q.options && q.options.length > 0 ? (
            <select
              className={fieldClass}
              value={answers[q.id] || ""}
              onChange={(e) => handleChange(q.id, e.target.value)}
            >
              <option value="" disabled>Elegí una opción</option>
              {q.options.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          ) : (
            <input
              className={fieldClass}
              type="text"
              value={answers[q.id] || ""}
              onChange={(e) => handleChange(q.id, e.target.value)}
            />
          )}
        </div>
      ))}
      <Button onClick={handleSubmit}>Enviar respuestas</Button>
    </div>
  )
}
