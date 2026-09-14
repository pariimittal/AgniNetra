export const riskColors: Record<string, string> = {
  LOW: '#34d399',
  MODERATE: '#fbbf24',
  HIGH: '#f97316',
  CRITICAL: '#ef4444',
}

export const riskLabels: Record<string, string> = {
  LOW: 'Low',
  MODERATE: 'Moderate',
  HIGH: 'High',
  CRITICAL: 'Critical',
}

export const thermalColors: Record<string, string> = {
  NORMAL: '#22c55e',
  MILDLY_ABNORMAL: '#fbbf24',
  ABNORMAL: '#f97316',
}

export const lifecycleLabels: Record<string, string> = {
  FIRST_SEEN: 'First Seen',
  GROWING: 'Growing',
  PERSISTENT: 'Persistent',
  DECLINING: 'Declining',
  REIGNITED: 'Reignited',
  RESOLVED: 'Resolved',
}

export const classificationOptions = [
  'Industrial Fire',
  'Gas Flare / Persistent Source',
  'Wildfire',
  'Agricultural Burning',
  'Mining Activity',
  'Unknown',
] as const

export const riskOptions = ['LOW', 'MODERATE', 'HIGH', 'CRITICAL'] as const
export const thermalOptions = ['NORMAL', 'MILDLY_ABNORMAL', 'ABNORMAL'] as const
export const routeLabels = {
  '/': 'Command Center',
  '/command-center': 'Command Center',
  '/events': 'Thermal Events',
  '/facilities': 'Facilities',
  '/intelligence/fast-filter': 'Physics Filter',
  '/intelligence/fingerprint': 'Thermal Fingerprint',
  '/intelligence/deviation': 'Deviation Engine',
  '/intelligence/classification': 'Type Attribution',
  '/intelligence/risk': 'Risk Intelligence',
  '/intelligence/lifecycle': 'Lifecycle Tracking',
}

export const INDIA_CENTER = { lat: 22.5, lng: 78.96 }
