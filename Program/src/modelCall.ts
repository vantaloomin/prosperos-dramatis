import { useEffect, useRef, useState } from 'react'
import { getJson, runs, stopped } from './api'

const STEP_MS = 700

/** One call to the user's model at a time, which the user can stop: `run` passes the call a signal, `stop` aborts
 * it. Stopping drops the request, and the server cancels the model's work with it (dramatis/calls.py). A stopped call
 * shows no error, and what it would have answered is dropped. Leaving the screen stops it too. While it runs, `step`
 * is what the server says it is doing. */
export function useModelCall() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [step, setStep] = useState('')
  const out = useRef<AbortController | null>(null)
  useEffect(() => () => out.current?.abort(), [])
  const run = async <T,>(call: (signal: AbortSignal) => Promise<T>, done: (found: T) => void, failed = 'Your model could not do that.') => {
    out.current?.abort()
    const control = new AbortController()
    const id = Math.random().toString(36).slice(2, 14)
    runs.set(control.signal, id)
    out.current = control
    setBusy(true)
    setError('')
    setStep('')
    const asking = setInterval(() => {
      void getJson<{ step: string }>(`/api/progress/${id}`).then((found) => { if (out.current === control) setStep(found.step) }, () => {})
    }, STEP_MS)
    try {
      const found = await call(control.signal)
      if (!control.signal.aborted) done(found)
    } catch (failure) {
      if (!stopped(failure) && !control.signal.aborted) setError(failure instanceof Error ? failure.message : failed)
    } finally {
      clearInterval(asking)
      if (out.current === control) { out.current = null; setBusy(false); setStep('') }
    }
  }
  const stop = () => { out.current?.abort(); out.current = null; setBusy(false); setStep('') }
  return { busy, error, step, run, stop, setError }
}
