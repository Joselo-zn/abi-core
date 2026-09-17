import { Button } from "@/components/ui/button"

export default function ClarificationForm() {
  const questions = props.questions || []
  const answers = props.answers || {}

  const handleChange = (id, value) => {
    updateElement(Object.assign(props, { answers: { ...answers, [id]: value } }))
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
              className="border rounded-md p-2 text-sm"
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
              className="border rounded-md p-2 text-sm"
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
