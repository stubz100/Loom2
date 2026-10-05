import { useSuite } from './suiteRegistry'

export function Strip() {
  const suite = useSuite()
  const SuiteStrip = suite.Strip
  return <div className="strip"><SuiteStrip key={suite.id} /></div>
}
