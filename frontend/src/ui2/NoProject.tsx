// W1 (= F1): the centre with no project — the words and the two ways in, not the words alone.
import { CommandButton } from '../frame/CommandButton'

export function NoProject() {
  return (
    <div className="w-empty" data-testid="no-project">Open or create a project
      <div className="w-verbs"><CommandButton id="global.project.open" text /><CommandButton id="global.project.new" text /></div>
    </div>
  )
}
