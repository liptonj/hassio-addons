export interface Device {
  id: string
  name: string
  name_by_user?: string
  manufacturer?: string
  model?: string
  area_id?: string
}

export interface Area {
  area_id: string
  name: string
  aliases?: string[]
  picture?: string
}

export interface InviteCode {
  code: string
  max_uses: number
  uses: number
  is_active: boolean
  expires_at?: string
  note?: string
  created_by?: string
  created_at: string
  last_used_at?: string
}

export interface InviteCodeCreate {
  max_uses: number
  expires_in_hours?: number
  note?: string
}
