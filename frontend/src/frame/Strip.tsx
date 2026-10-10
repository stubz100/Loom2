import { useSuite } from './suiteRegistry'

export function Strip({ wide = false }: { wide?: boolean }) {
  const suite = useSuite()
  const SuiteStrip = suite.Strip
  return <div className={`strip${wide ? ' wide' : ''}`}><SuiteStrip key={suite.id} /></div>
}
