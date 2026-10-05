import { useSuite } from './suiteRegistry'

export function Strip() {
  const suite = useSuite()
  return <div className="strip">{suite.Strip()}</div>
}
