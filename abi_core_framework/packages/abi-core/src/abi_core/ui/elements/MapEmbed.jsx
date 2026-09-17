export default function MapEmbed() {
  if (!props.embedUrl) {
    return <div className="text-sm opacity-70">No map URL provided.</div>
  }

  return (
    <iframe
      title={props.title || "Map"}
      src={props.embedUrl}
      className="w-full rounded-lg border-0"
      style={{ height: props.height || "400px" }}
      loading="lazy"
      referrerPolicy="no-referrer-when-downgrade"
      allowFullScreen
    />
  )
}
