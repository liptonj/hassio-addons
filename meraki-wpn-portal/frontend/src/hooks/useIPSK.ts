import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listIPSKs,
  createIPSK,
  deleteIPSK,
  revokeIPSK,
  revealIPSKPassphrase,
  getIPSKStats,
} from '../api/client'
import type { IPSKCreate } from '../types/ipsk'

export function useIPSKs(filters?: {
  network_id?: string
  ssid_number?: number
  status?: string
}) {
  return useQuery({
    queryKey: ['ipsks', filters],
    queryFn: () => listIPSKs(filters),
  })
}

export function useIPSKStats() {
  return useQuery({
    queryKey: ['ipsk-stats'],
    queryFn: getIPSKStats,
  })
}

export function useCreateIPSK() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (ipsk: IPSKCreate) => createIPSK(ipsk),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ipsks'] })
      queryClient.invalidateQueries({ queryKey: ['ipsk-stats'] })
    },
  })
}

export function useDeleteIPSK() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => deleteIPSK(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ipsks'] })
      queryClient.invalidateQueries({ queryKey: ['ipsk-stats'] })
    },
  })
}

export function useRevokeIPSK() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => revokeIPSK(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ipsks'] })
      queryClient.invalidateQueries({ queryKey: ['ipsk-stats'] })
    },
  })
}

export function useRevealPassphrase() {
  return useMutation({
    mutationFn: (id: string) => revealIPSKPassphrase(id),
  })
}
