// D127 (AU2), CE4: the cut's slider changes in the order the author made them — one waits for the one before (a slider stays live while
// FilmCraft takes a value; disabling it dropped the keys pressed meanwhile).
let queue: Promise<unknown> = Promise.resolve()

export function enqueue(change: () => Promise<unknown>): Promise<unknown> {
  queue = queue.then(change)
  return queue
}
