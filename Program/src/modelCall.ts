import { useEffect, useRef, useState } from 'react'
import { stopped } from './api'

/** One call to the user's model at a time, which the user can stop: `run` passes the call a signal, `stop` aborts
 * it. A stopped call shows no error, and what it would have answered is dropped. Leaving the screen stops it too. */
export function useModelCall() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const out = useRef<AbortController | null>(null)
  useEffect(() => () => out.current?.abort(), [])
  const run = async <T,>(call: (signal: AbortSignal) => Promise<T>, done: (found: T) => void, failed = 'Your model could not do that.') => {
    out.current?.abort()
    const control = new AbortController()
    out.current = control
    setBusy(true)
    setError('')
    try {
      const found = await call(control.signal)
      if (!control.signal.aborted) done(found)
    } catch (failure) {
      if (!stopped(failure) && !control.signal.aborted) setError(failure instanceof Error ? failure.message : failed)
    } finally {
      if (out.current === control) { out.current = null; setBusy(false) }
    }
  }
  const stop = () => { out.current?.abort(); out.current = null; setBusy(false) }
  return { busy, error, run, stop, setError }
}
