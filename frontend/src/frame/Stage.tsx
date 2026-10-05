import { useSuite } from './suiteRegistry'

export function Stage() {
  const suite = useSuite()
  return <section className="stage">{suite.Stage()}</section>
}
