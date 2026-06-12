/** AutoDL Manager — TypeScript 类型定义 */

export interface GPUProcess {
  pid: number
  name: string
  gpu_mem_mb: number
}

export interface GPUData {
  uuid?: string
  util_percent?: number
  mem_used_gb?: number
  mem_total_gb?: number
  temp_c?: number
  gpu_name?: string
  processes?: GPUProcess[]
}

export interface Instance {
  uuid: string
  source: 'pro' | 'web' | 'ssh'
  alias: string
  status: 'running' | 'stopped' | 'no_gpu' | 'reachable' | 'powering_on' | 'powering_off'
  gpu_type: string
  region: string
  price_per_hour: number
  ssh_host: string
  ssh_port: number
  ssh_user: string
  ssh_password?: string
  ssh_key_path?: string
  is_current: boolean
  tags: string[]
}

export interface InstancesResponse {
  instances: Instance[]
  stats: {
    total: number
    running: number
    stopped: number
    by_source: { web: number; pro: number; ssh: number }
  }
}

export interface CostData {
  balance_yuan: number
  today_cost: number
  week_cost: number
  total_spent: number
  voucher_balance: number
  daily_rate_yuan: number
  runway_days: number | null
}

export interface ProbeResult {
  reachable: boolean
  status?: string
  gpu_present?: boolean
  gpu?: GPUData
  hostname?: string
  python?: string
  disk?: string
  ram?: string
  os?: string
  error?: string
  processes?: GPUProcess[]
}

export interface Alert {
  id: string
  instance_uuid?: string
  timestamp: string
  severity: 'info' | 'warning' | 'critical'
  type: string
  message: string
  dismissed: number
}

export interface SettingsData {
  token: string
  ssh_key: string
  ssh_user?: string
  hasToken: boolean
}

export type TabId = 'dashboard' | 'instances' | 'agent' | 'cost' | 'logs' | 'settings'

export interface Tab {
  id: TabId
  label: string
  icon: string
}

export type SourceType = 'web' | 'ssh' | 'pro'

export type InstanceStatus = 'running' | 'stopped' | 'no_gpu' | 'reachable' | 'powering_on' | 'powering_off'

export type BadgeType = 'running' | 'stopped' | 'warning'
