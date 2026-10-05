import { useSuite } from './suiteRegistry'

export function Stage() {
  const suite = useSuite()
  const SuiteStage = suite.Stage
  return <section className="stage"><SuiteStage key={suite.id} /></section>
}
