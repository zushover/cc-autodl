/** AutoDL Manager — API 调用 + SSE 封装 */

import type { InstancesResponse, CostData, ProbeResult, Alert, SettingsData, GPUData, Instance } from './types'

const API_BASE = 'http://127.0.0.1:8899'

let serverReady = false

export function isServerReady(): boolean {
  return serverReady
}

export async function waitForServer(maxRetries = 20): Promise<boolean> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const res = await fetch(API_BASE + '/api/stats', { signal: AbortSignal.timeout(2000) })
      if (res.ok) {
        serverReady = true
        return true
      }
    } catch (_) { /* server not up yet */ }
    await new Promise(r => setTimeout(r, 300))
  }
  return false
}

async function api<T>(url: string, opts: RequestInit = {}): Promise<T | null> {
  if (!serverReady) {
    const ok = await waitForServer()
    if (!ok) return null
  }
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 30000)
  try {
    const headers: Record<string, string> = { 'Content-Type': 'application/json; charset=utf-8' }
    if (opts.headers) Object.assign(headers, opts.headers as Record<string, string>)
    const res = await fetch(API_BASE + url, { ...opts, headers, signal: controller.signal })
    clearTimeout(timer)
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      return { error: true, message: err?.error || `Server error (${res.status})` } as unknown as T
    }
    return await res.json() as T
  } catch (e: unknown) {
    clearTimeout(timer)
    if (e instanceof DOMException && e.name === 'AbortError') {
      return { error: true, message: 'Request timeout' } as unknown as T
    }
    if (e instanceof TypeError && e.message === 'Failed to fetch') {
      serverReady = false
    }
    return null
  }
}

// ─── 实例 API ───

export async function loadInstances(): Promise<InstancesResponse | null> {
  return api<InstancesResponse>('/api/instances')
}

export async function setCurrent(uuid: string): Promise<{ ok: boolean } | null> {
  return api('/api/instances/' + uuid + '/set-current', { method: 'POST' })
}

export async function getGPU(uuid: string): Promise<GPUData | null> {
  return api<GPUData>('/api/instances/' + uuid + '/gpu')
}

export async function probeInstance(uuid: string): Promise<ProbeResult | null> {
  return api<ProbeResult>('/api/instances/' + uuid + '/probe', { method: 'POST' })
}

export async function removeInstance(uuid: string): Promise<{ ok: boolean } | null> {
  return api('/api/instances/' + uuid, { method: 'DELETE' })
}

export async function shutdownInstance(uuid: string): Promise<{ ok: boolean; error?: string } | null> {
  return api('/api/instances/' + uuid + '/shutdown', { method: 'POST' })
}

export async function registerInstance(body: Record<string, unknown>): Promise<{ instance?: Instance; error?: string; message?: string } | null> {
  return api('/api/instances/register', { method: 'POST', body: JSON.stringify(body) })
}

// ─── API 同步 ───

export async function syncPro(): Promise<{ ok: boolean; synced: number; error?: string; message?: string } | null> {
  return api('/api/pro/sync', { method: 'POST' })
}

// ─── 费用 ───

export async function loadCost(force = false): Promise<CostData | null> {
  return api<CostData>('/api/cost' + (force ? '?refresh=1' : ''))
}

// ─── 告警 ───

export async function loadAlerts(): Promise<{ alerts: Alert[] } | null> {
  return api('/api/alerts')
}

export async function dismissAlert(id: string): Promise<{ ok: boolean } | null> {
  return api('/api/alerts/' + id + '/dismiss', { method: 'POST' })
}

// ─── GPU 型号 / 区域 ───

export async function loadGpuTypes(source = 'web'): Promise<{ gpu_types: { name: string; vram: string; price: number }[] } | null> {
  return api('/api/gpu-types?source=' + source)
}

export async function loadRegions(): Promise<{ regions: string[] } | null> {
  return api('/api/regions')
}

// ─── SSH 解析 ───

export async function parseSshString(sshString: string): Promise<{ host: string; port: number; user: string } | null> {
  return api('/api/parse-ssh', { method: 'POST', body: JSON.stringify({ ssh_string: sshString }) })
}

// ─── 设置 ───

export async function loadSettings(): Promise<SettingsData | null> {
  return api<SettingsData>('/api/settings')
}

export async function saveSettings(token: string, sshKey: string): Promise<{ ok: boolean; error?: string; message?: string } | null> {
  return api('/api/settings', { method: 'POST', body: JSON.stringify({ token, ssh_key: sshKey }) })
}

// ─── SSE 实时流 ───

export function createSSEStream(
  onGpu: (data: GPUData) => void,
  onInstanceRegistered: () => void,
  onInstanceStatus: () => void,
  onInstanceRemoved: () => void,
  onCurrentChanged: () => void,
  onProSynced: () => void,
  onSettingsUpdated: () => void,
): { close: () => void } {
  const source = new EventSource(API_BASE + '/api/stream')
  let reconnectTimer: ReturnType<typeof setTimeout>

  source.addEventListener('gpu', (e: MessageEvent) => {
    try { const d = JSON.parse(e.data); onGpu(d) } catch (_) { /* ignore */ }
  })
  source.addEventListener('instance_registered', () => onInstanceRegistered())
  source.addEventListener('instance_status', () => onInstanceStatus())
  source.addEventListener('instance_removed', () => onInstanceRemoved())
  source.addEventListener('current_changed', () => onCurrentChanged())
  source.addEventListener('pro_synced', () => onProSynced())
  source.addEventListener('settings_updated', () => onSettingsUpdated())
  source.onerror = () => {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    reconnectTimer = setTimeout(() => {
      source.close()
      createSSEStream(onGpu, onInstanceRegistered, onInstanceStatus, onInstanceRemoved, onCurrentChanged, onProSynced, onSettingsUpdated)
    }, 5000)
  }

  return {
    close: () => {
      if (reconnectTimer) clearTimeout(reconnectTimer)
      source.close()
    },
  }
}
