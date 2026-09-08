export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL'
export type ThermalStatus = 'NORMAL' | 'MILDLY_ABNORMAL' | 'ABNORMAL'
export type LifecycleState =
  | 'FIRST_SEEN'
  | 'GROWING'
  | 'PERSISTENT'
  | 'DECLINING'
  | 'REIGNITED'
  | 'RESOLVED'

export type ClassificationType =
  | 'Industrial Fire'
  | 'Gas Flare / Persistent Source'
  | 'Wildfire'
  | 'Agricultural Burning'
  | 'Mining Activity'
  | 'Unknown'

export type FacilityType = 'REFINERY' | 'POWER PLANT' | 'MANUFACTURING' | 'MINING' | 'CHEMICAL'

export type ThermalEvent = {
  id: string
  timestamp: string
  latitude: number
  longitude: number
  brightness: number
  confidence: number
  facilityId?: string
  facilityName?: string
  facilityType?: string
  distanceToFacility?: number
  classification: ClassificationType
  classificationConfidence: number
  thermalStatus: ThermalStatus
  deviationScore: number
  riskScore: number
  riskLevel: RiskLevel
  lifecycle: LifecycleState
  detectionCount: number
  environmentalImpact: 'LOW' | 'MODERATE' | 'HIGH'
  riskReasons: string[]
  deviationReasons: string[]
  riskComponents: {
    intensity: number
    persistence: number
    deviation: number
    population: number
    environmental: number
    infrastructure: number
  }
}

export type Facility = {
  id: string
  name: string
  type: FacilityType
  location: string
  latitude: number
  longitude: number
  baselineBrightness: number
  currentBrightness: number
  detections30d: number
  persistence: number
  thermalStatus: ThermalStatus
  normalWindow: string
  riskLevel: RiskLevel
}

export type EventFilters = {
  risk: 'ALL' | RiskLevel
  thermal: 'ALL' | ThermalStatus
  classification: 'ALL' | ClassificationType
  facility: string
  abnormalOnly: boolean
}

export type ApiHealth = {
  status: string
  mode: 'demo' | 'live'
}

export type FingerprintData = {
  facilityId: string
  observed: number[]
  baseline: number[]
  threshold: number[]
  timeLabels: string[]
  typicalWindow: string
  frequency: number
  persistence: number
  currentValue: number
  delta: number
  status: ThermalStatus
}

export type FacilityHistory = {
  date: string
  observedBrightness: number
  baseline: number
  threshold: number
  detectionCount: number
  normalWindow: string
  anomaly: 'NORMAL' | 'MILDLY_ABNORMAL' | 'ABNORMAL'
}
