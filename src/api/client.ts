import { demoEvents, facilities, facilityHistory, fingerprintData } from '../data/demo'
import type { ApiHealth, Facility, FacilityHistory, FingerprintData, ThermalEvent } from '../types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''
const USE_DEMO_DATA = import.meta.env.VITE_USE_DEMO_DATA !== 'false'

async function request<T>(endpoint: string): Promise<T> {
  if (!API_BASE_URL || USE_DEMO_DATA) {
    throw new Error('Demo mode enabled')
  }

  const res = await fetch(`${API_BASE_URL}${endpoint}`)

  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`)
  }

  return res.json() as Promise<T>
}

export async function getHealth(): Promise<ApiHealth> {
  try {
    return await request<ApiHealth>('/api/health')
  } catch {
    return { status: 'OPERATIONAL', mode: 'demo' }
  }
}

export async function getEvents(): Promise<ThermalEvent[]> {
  if (USE_DEMO_DATA) return demoEvents
  try {
    return await request<ThermalEvent[]>('/api/events')
  } catch {
    return demoEvents
  }
}

export async function getEvent(id: string): Promise<ThermalEvent | undefined> {
  if (USE_DEMO_DATA) return demoEvents.find((event) => event.id === id)
  try {
    return await request<ThermalEvent>(`/api/events/${id}`)
  } catch {
    return demoEvents.find((event) => event.id === id)
  }
}

export async function getFacilities(): Promise<Facility[]> {
  if (USE_DEMO_DATA) return facilities
  try {
    return await request<Facility[]>('/api/facilities')
  } catch {
    return facilities
  }
}

export async function getFacility(id: string): Promise<Facility | undefined> {
  if (USE_DEMO_DATA) return facilities.find((facility) => facility.id === id)
  try {
    return await request<Facility>(`/api/facilities/${id}`)
  } catch {
    return facilities.find((facility) => facility.id === id)
  }
}

export async function getFacilityHistory(id: string): Promise<FacilityHistory[]> {
  if (USE_DEMO_DATA) return facilityHistory[id] ?? []
  try {
    return await request<FacilityHistory[]>(`/api/facilities/${id}/history`)
  } catch {
    return facilityHistory[id] ?? []
  }
}

export async function getFingerprint(id: string): Promise<FingerprintData | undefined> {
  if (USE_DEMO_DATA) return fingerprintData[id]
  try {
    return await request<FingerprintData>(`/api/facilities/${id}/fingerprint`)
  } catch {
    return fingerprintData[id]
  }
}

export async function getStats() {
  if (USE_DEMO_DATA) {
    const abnormalCount = demoEvents.filter((event) => event.thermalStatus === 'ABNORMAL').length
    const criticalCount = demoEvents.filter((event) => event.riskLevel === 'CRITICAL').length
    return {
      thermalEvents: demoEvents.length,
      abnormal: abnormalCount,
      highCritical: criticalCount,
      facilitiesMonitored: facilities.length,
    }
  }

  try {
    return await request('/api/stats')
  } catch {
    const abnormalCount = demoEvents.filter((event) => event.thermalStatus === 'ABNORMAL').length
    const criticalCount = demoEvents.filter((event) => event.riskLevel === 'CRITICAL').length
    return {
      thermalEvents: demoEvents.length,
      abnormal: abnormalCount,
      highCritical: criticalCount,
      facilitiesMonitored: facilities.length,
    }
  }
}
