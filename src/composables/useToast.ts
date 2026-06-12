/** Toast 通知 composable */

import { reactive } from 'vue'

interface ToastState {
  show: boolean
  msg: string
  ok: boolean
  id: number
}

let toastTimer: ReturnType<typeof setTimeout> | null = null

const toast = reactive<ToastState>({ show: false, msg: '', ok: true, id: 0 })

export function useToast() {
  function notify(msg: string, ok = true) {
    if (toastTimer) clearTimeout(toastTimer)
    toast.id = Date.now()
    toast.show = true
    toast.msg = msg
    toast.ok = ok
    toastTimer = setTimeout(() => { toast.show = false }, 5000)
  }

  function clearToast() {
    if (toastTimer) clearTimeout(toastTimer)
    toast.show = false
  }

  return { toast, notify, clearToast }
}
