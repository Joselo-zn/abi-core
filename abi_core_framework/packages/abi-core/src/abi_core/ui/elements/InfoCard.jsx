import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Clock, User, Tag } from "lucide-react"

export default function InfoCard() {
  const progressPercent = Math.round((props.progress || 0) * 100)

  return (
    <Card className="w-full max-w-md">
      <CardHeader className="pb-2">
        <div className="flex justify-between items-center">
          <CardTitle className="text-lg font-medium">
            {props.title || "Untitled"}
          </CardTitle>
          {props.status && <Badge variant="outline">{props.status}</Badge>}
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {props.progress !== undefined && (
            <Progress value={progressPercent} className="h-2" />
          )}
          <div className="grid grid-cols-2 gap-4 text-sm">
            {props.assignee && (
              <div className="flex items-center gap-2">
                <User className="h-4 w-4 opacity-70" />
                <span>{props.assignee}</span>
              </div>
            )}
            {props.date && (
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 opacity-70" />
                <span>{props.date}</span>
              </div>
            )}
            {props.tags && props.tags.length > 0 && (
              <div className="flex items-center gap-2 col-span-2">
                <Tag className="h-4 w-4 opacity-70" />
                <span>{props.tags.join(", ")}</span>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
