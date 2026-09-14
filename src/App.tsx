import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from 'react'
import {
  Activity,
  Bell,
  Building2,
  FlaskConical,
  Layers3,
  Menu,
  Radar,
  Search,
  ShieldAlert,
  ThermometerSun,
  TrendingUp,
  X,
  Zap,
} from 'lucide-react'
import {
  Line,
  LineChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import {
  MapContainer,
  TileLayer,
  Marker,
  CircleMarker,
  Popup,
  useMap,
} from 'react-leaflet'
import * as L from 'leaflet'
import { BrowserRouter, Link, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { getEvents, getFacilities, getFacilityHistory } from './api/client'
import { demoEvents, facilities, fingerprintData } from './data/demo'
import type { Facility, FacilityHistory, ThermalEvent } from './types'

const navGroups = [
  {
    title: 'OVERVIEW',
    items: [
      { label: 'Command Center', to: '/command-center', icon: Radar },
      { label: 'Thermal Events', to: '/events', icon: ThermometerSun },
      { label: 'Facilities', to: '/facilities', icon: Building2 },
    ],
  },
  {
    title: 'INTELLIGENCE',
    items: [
      { label: 'Physics Filter', to: '/intelligence/fast-filter', icon: FlaskConical },
      { label: 'Thermal Fingerprint', to: '/intelligence/fingerprint', icon: Activity },
      { label: 'Deviation Engine', to: '/intelligence/deviation', icon: TrendingUp },
      { label: 'Type Attribution', to: '/intelligence/classification', icon: Layers3 },
      { label: 'Risk Intelligence', to: '/intelligence/risk', icon: ShieldAlert },
      { label: 'Lifecycle Tracking', to: '/intelligence/lifecycle', icon: Zap },
    ],
  },
]

const riskBadgeClasses = {
  LOW: 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/20',
  MODERATE: 'bg-amber-500/15 text-amber-300 border border-amber-500/20',
  HIGH: 'bg-orange-500/15 text-orange-300 border border-orange-500/20',
  CRITICAL: 'bg-red-500/15 text-red-300 border border-red-500/20',
} as const

const thermalBadgeClasses = {
  NORMAL: 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/20',
  MILDLY_ABNORMAL: 'bg-amber-500/15 text-amber-300 border border-amber-500/20',
  ABNORMAL: 'bg-orange-500/15 text-orange-300 border border-orange-500/20',
} as const

function formatDate(value: string) {
  return new Date(value).toLocaleString('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

function formatEventTime(value: string) {
  return new Date(value).toLocaleString('en-IN', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function getRiskColor(level: string) {
  const map: Record<string, string> = {
    LOW: '#34d399',
    MODERATE: '#fbbf24',
    HIGH: '#f97316',
    CRITICAL: '#ef4444',
  }
  return map[level] ?? '#94a3b8'
}

function RiskBadge({ level }: { level: string }) {
  return (
    <span className={`rounded px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] ${riskBadgeClasses[level as keyof typeof riskBadgeClasses] ?? 'bg-slate-800 text-slate-200'}`}>
      {level}
    </span>
  )
}

function ThermalStatusBadge({ status }: { status: string }) {
  return (
    <span className={`rounded px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] ${thermalBadgeClasses[status as keyof typeof thermalBadgeClasses] ?? 'bg-slate-800 text-slate-200'}`}>
      {status.replace('_', ' ')}
    </span>
  )
}

function SectionHeader({ eyebrow, title, description }: { eyebrow: string; title: string; description?: string }) {
  return (
    <div className="section-header mb-5">
      <div className="text-[10px] uppercase tracking-[0.28em] text-slate-500">{eyebrow}</div>
      <h2 className="mt-2 text-2xl font-medium tracking-tight text-slate-100">{title}</h2>
      {description && <p className="mt-2 max-w-2xl text-sm text-slate-400">{description}</p>}
    </div>
  )
}

function MetricCard({ label, value, subtext }: { label: string; value: string; subtext?: string }) {
  return (
    <div className="tech-card metric-card rounded border border-slate-800 p-4">
      <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">{label}</div>
      <div className="mt-3 text-xl font-semibold text-slate-50">{value}</div>
      {subtext && <div className="mt-2 text-xs text-slate-400">{subtext}</div>}
    </div>
  )
}

function LoadingSkeleton({ label }: { label: string }) {
  return (
    <div className="rounded border border-slate-800 bg-[#0d1218] p-6">
      <div className="h-3 w-28 animate-pulse rounded bg-slate-700/80" />
      <div className="mt-5 space-y-3">
        <div className="h-4 w-full animate-pulse rounded bg-slate-800" />
        <div className="h-4 w-5/6 animate-pulse rounded bg-slate-800" />
        <div className="h-4 w-4/5 animate-pulse rounded bg-slate-800" />
      </div>
      <div className="mt-6 text-[10px] uppercase tracking-[0.22em] text-slate-500">{label}</div>
    </div>
  )
}

function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return (
    <div className="rounded border border-dashed border-slate-700 bg-[#101821] p-10 text-center">
      <div className="text-[10px] uppercase tracking-[0.24em] text-slate-500">No data</div>
      <h3 className="mt-2 text-xl text-slate-100">{title}</h3>
      <p className="mt-2 text-sm text-slate-400">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

function ErrorState({ title, message, retry }: { title: string; message: string; retry?: () => void }) {
  return (
    <div className="rounded border border-red-500/30 bg-red-500/10 p-6">
      <div className="text-[10px] uppercase tracking-[0.24em] text-red-300">INTELLIGENCE DATA UNAVAILABLE</div>
      <h3 className="mt-2 text-xl text-slate-50">{title}</h3>
      <p className="mt-2 text-sm text-slate-300">{message}</p>
      {retry && (
        <button onClick={retry} className="mt-4 rounded border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">
          Retry
        </button>
      )}
    </div>
  )
}

function RiskBars({ values }: { values: Record<string, number> }) {
  return (
    <div className="space-y-3">
      {Object.entries(values).map(([label, value]) => (
        <div key={label}>
          <div className="mb-1 flex items-center justify-between text-[10px] uppercase tracking-[0.18em] text-slate-400">
            <span>{label}</span>
            <span>{value}</span>
          </div>
          <div className="risk-track h-2 rounded-full bg-slate-800">
            <div className="risk-fill h-2 rounded-full bg-gradient-to-r from-slate-400 via-orange-400 to-red-500" style={{ width: `${value}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}

function RiskMeter({ score, level }: { score: number; level: string }) {
  return (
    <div className="risk-meter" style={{ '--risk-score': `${score * 3.6}deg` } as CSSProperties}>
      <div className="risk-meter-inner">
        <span className="text-3xl font-semibold text-slate-50">{score}</span>
        <span className="text-[9px] uppercase tracking-[0.2em] text-slate-500">/ 100</span>
        <span className="mt-1 text-[10px] uppercase tracking-[0.18em] text-red-300">{level}</span>
      </div>
    </div>
  )
}

function AppShell({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState<Array<{ id: string; label: string; type: 'event' | 'facility'; route: string; meta: string }>>([])

  useEffect(() => {
    const q = query.trim().toLowerCase()
    if (!q) {
      setSearchResults([])
      return
    }

    const eventResults = demoEvents
      .filter((event) => {
        const searchable = [event.id, event.classification, event.riskLevel, event.facilityName ?? '', event.latitude, event.longitude].join(' ').toLowerCase()
        return searchable.includes(q)
      })
      .slice(0, 5)
      .map((event) => ({
        id: event.id,
        label: `${event.id} — ${event.classification}`,
        type: 'event' as const,
        route: `/events/${event.id}`,
        meta: `${event.riskLevel} • ${event.facilityName ?? 'Unknown site'}`,
      }))

    const facilityResults = facilities
      .filter((facility) => {
        const searchable = [facility.id, facility.name, facility.location, facility.type].join(' ').toLowerCase()
        return searchable.includes(q)
      })
      .slice(0, 4)
      .map((facility) => ({
        id: facility.id,
        label: `${facility.id} — ${facility.name}`,
        type: 'facility' as const,
        route: `/facilities/${facility.id}`,
        meta: facility.location,
      }))

    setSearchResults([...eventResults, ...facilityResults])
  }, [query])

  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])

  const pageTitle = useMemo(() => {
    const map: Record<string, string> = {
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
    return map[location.pathname] ?? 'Thermal Intelligence'
  }, [location.pathname])

  return (
    <div className="tech-shell min-h-screen text-slate-100">
      <div className="flex min-h-screen">
        <aside className={`${sidebarOpen ? 'translate-x-0' : '-translate-x-full'} tech-panel fixed inset-y-0 left-0 z-40 w-72 border-r border-slate-800 transition-transform duration-200 lg:static lg:translate-x-0`}>
          <div className="flex h-full flex-col px-5 py-6">
            <div className="mb-8 flex items-center gap-3 px-2">
              <div className="brand-mark glow-orb flex h-10 w-10 items-center justify-center rounded border border-orange-400/40 bg-slate-900 text-[10px] font-bold tracking-[0.2em] text-orange-300"><span>AL</span></div>
              <div>
                <div className="brand-name text-xs tracking-[0.28em] text-slate-200">AGNILENS</div>
                <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Thermal Intelligence</div>
              </div>
            </div>

            <nav className="space-y-6">
              {navGroups.map((group) => (
                <div key={group.title}>
                  <div className="mb-2 px-2 text-[10px] font-medium uppercase tracking-[0.24em] text-slate-500">{group.title}</div>
                  <div className="space-y-1">
                    {group.items.map(({ label, to, icon: Icon }) => (
                      <NavLink
                        key={to}
                        to={to}
                        className={({ isActive }) => `flex items-center gap-3 rounded-md border px-3 py-2 text-sm transition-colors ${isActive ? 'border-slate-700 bg-slate-800 text-white' : 'border-transparent text-slate-300 hover:border-slate-700 hover:bg-slate-900/80 hover:text-slate-100'}`}
                      >
                        <Icon size={14} className="text-slate-400" />
                        {label}
                      </NavLink>
                    ))}
                  </div>
                </div>
              ))}
            </nav>

            <div className="mt-auto border-t border-slate-800 pt-4" />
          </div>
        </aside>

        <div className="flex min-h-screen w-full flex-col">
          <header className="tech-topbar border-b border-slate-800 backdrop-blur-sm">
            <div className="flex items-center justify-between gap-4 px-5 py-4">
              <div className="flex items-center gap-3">
                <button className="lg:hidden rounded border border-slate-700 p-2 text-slate-300" aria-label="Toggle menu" onClick={() => setSidebarOpen((value) => !value)}>
                  {sidebarOpen ? <X size={16} /> : <Menu size={16} />}
                </button>
                <div>
                  <div className="status-pill text-[10px] uppercase tracking-[0.28em] text-slate-300"><span className="live-dot" /> Thermal Intelligence</div>
                  <h1 className="mt-1 text-lg font-medium text-slate-100">{pageTitle}</h1>
                </div>
              </div>

              <div className="flex flex-1 items-center justify-end gap-3">
                <div className="hidden items-center gap-2 rounded border border-slate-700 bg-slate-900/70 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-slate-300 md:flex">
                  <span className="text-slate-500">India / Industrial Monitoring</span>
                </div>
                <button className="tech-button rounded border border-slate-700 bg-slate-900/70 p-2 text-slate-300" aria-label="Notifications">
                  <Bell size={15} />
                </button>
                <div className="relative">
                  <div className="tech-input flex items-center gap-2 rounded border border-slate-700 bg-slate-900/70 px-2 py-1.5">
                    <Search size={14} className="text-slate-400" />
                    <input
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      placeholder="Search events or facilities"
                      aria-label="Search event or facility"
                      className="w-40 bg-transparent text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none"
                    />
                  </div>
                  {searchResults.length > 0 && (
                    <div className="absolute right-0 top-12 z-50 w-[320px] rounded border border-slate-700 bg-[#101821] p-2 shadow-lg">
                      {searchResults.map((result) => (
                        <Link key={`${result.type}-${result.id}`} to={result.route} className="block rounded border border-transparent px-2 py-2 hover:border-slate-700 hover:bg-slate-900/80">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-medium uppercase tracking-[0.18em] text-slate-300">{result.id}</span>
                            <span className="text-[9px] uppercase tracking-[0.18em] text-slate-500">{result.type}</span>
                          </div>
                          <div className="mt-1 text-sm text-slate-100">{result.label}</div>
                          <div className="mt-1 text-[10px] uppercase tracking-[0.14em] text-slate-500">{result.meta}</div>
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
                <div className="glow-orb flex h-9 w-9 items-center justify-center rounded-full border border-slate-600 bg-slate-700 text-xs font-semibold text-slate-100">AL</div>
              </div>
            </div>
          </header>

          <main className="tech-surface flex-1 overflow-auto p-4 md:p-6">{children}</main>
        </div>
      </div>
    </div>
  )
}

function SummaryStrip({ stats }: { stats: { thermalEvents: number; abnormal: number; highCritical: number; facilitiesMonitored: number } }) {
  const items = [
    { label: 'Thermal Events', value: stats.thermalEvents },
    { label: 'Abnormal', value: stats.abnormal },
    { label: 'High / Critical', value: stats.highCritical },
    { label: 'Facilities Monitored', value: stats.facilitiesMonitored },
  ]

  return (
    <section className="command-metrics mb-6 grid grid-cols-2 gap-2 md:grid-cols-4 md:gap-3">
      {items.map((item) => (
        <div key={item.label} className="tech-card rounded border border-slate-800 p-3 md:p-4">
          <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">{item.label}</div>
          <div className="mt-2 text-xl font-semibold text-slate-50 md:text-2xl">{item.value}</div>
        </div>
      ))}
    </section>
  )
}

function CommandCenterPage() {
  const [events, setEvents] = useState<ThermalEvent[]>([])
  const [liveFacilities, setLiveFacilities] = useState<Facility[]>(facilities)
  const [selectedEventId, setSelectedEventId] = useState<string>('EVT-001')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true
    getEvents()
      .then((data) => {
        if (!mounted) return
        setEvents(data)
        setSelectedEventId(data[0]?.id ?? 'EVT-001')
      })
      .catch(() => setError('The intelligence service could not be reached.'))
      .finally(() => mounted && setLoading(false))

    getFacilities().then((data) => {
      if (mounted) setLiveFacilities(data)
    })
    return () => {
      mounted = false
    }
  }, [])

  const stats = useMemo(
    () => ({
      thermalEvents: events.length,
      abnormal: events.filter((event) => event.thermalStatus === 'ABNORMAL').length,
      highCritical: events.filter((event) => event.riskLevel === 'HIGH' || event.riskLevel === 'CRITICAL').length,
      facilitiesMonitored: liveFacilities.length,
    }),
    [events, liveFacilities],
  )

  const selectedEvent = events.find((event) => event.id === selectedEventId) ?? events[0]

  return (
    <div className="command-center-page">
      <SummaryStrip stats={stats} />
      {loading ? (
        <LoadingSkeleton label="COMMAND CENTER" />
      ) : error ? (
        <ErrorState title="INTELLIGENCE SERVICE UNAVAILABLE" message={error} retry={() => window.location.reload()} />
      ) : (
        <div className="grid gap-5 xl:grid-cols-[1.55fr_0.7fr]">
          <div className="command-map-panel tech-panel rounded border border-slate-800 bg-[#0d1218] p-3">
            <MapView events={events} facilities={liveFacilities} selectedEventId={selectedEventId} onSelectEvent={setSelectedEventId} />
          </div>

          <div className="command-intelligence-panel tech-panel rounded border border-slate-800 p-4">
            {selectedEvent ? (
              <div className="space-y-5">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.24em] text-slate-500">Event Intelligence</div>
                  <div className="mt-2 flex items-center justify-between">
                    <div>
                      <div className="text-xl font-semibold text-slate-100">{selectedEvent.id}</div>
                      <div className="text-sm text-slate-400">{formatEventTime(selectedEvent.timestamp)}</div>
                    </div>
                    <RiskBadge level={selectedEvent.riskLevel} />
                  </div>
                </div>

                <div className="investigation-hero rounded border border-slate-800 bg-[#0d1218] p-3">
                  <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">{selectedEvent.classification}</div>
                  <div className="mt-3 flex items-center justify-between gap-4">
                    <RiskMeter score={selectedEvent.riskScore} level={selectedEvent.riskLevel} />
                    <div className="min-w-0 text-right">
                      <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Confidence</div>
                      <div className="mt-2 text-2xl font-semibold text-cyan-200">{selectedEvent.classificationConfidence}%</div>
                      <div className="confidence-line mt-2"><span style={{ width: `${selectedEvent.classificationConfidence}%` }} /></div>
                    </div>
                  </div>
                  <div className="mt-2 text-xs uppercase tracking-[0.18em] text-slate-400">{selectedEvent.classificationConfidence}% classification confidence</div>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="rounded border border-slate-800 bg-slate-950/80 p-2">
                    <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Thermal status</div>
                    <div className="mt-2"><ThermalStatusBadge status={selectedEvent.thermalStatus} /></div>
                  </div>
                  <div className="rounded border border-slate-800 bg-slate-950/80 p-2">
                    <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Deviation</div>
                    <div className="mt-2 text-lg font-semibold text-slate-100">{selectedEvent.deviationScore} / 100</div>
                  </div>
                  <div className="rounded border border-slate-800 bg-slate-950/80 p-2">
                    <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Lifecycle</div>
                    <div className="mt-2 text-sm font-medium uppercase tracking-[0.14em] text-slate-200">{selectedEvent.lifecycle}</div>
                  </div>
                  <div className="rounded border border-slate-800 bg-slate-950/80 p-2">
                    <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Risk</div>
                    <div className="mt-2 text-lg font-semibold text-slate-100">{selectedEvent.riskLevel}</div>
                  </div>
                </div>

                <div>
                  <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Why this matters</div>
                  <ul className="mt-3 space-y-2 text-sm text-slate-300">
                    {selectedEvent.deviationReasons.map((reason) => (
                      <li key={reason} className="flex gap-2"><span className="mt-1 text-orange-400">•</span><span>{reason}</span></li>
                    ))}
                  </ul>
                </div>

                <div>
                  <div className="mb-3 text-[10px] uppercase tracking-[0.2em] text-slate-500">Risk drivers</div>
                  <RiskBars values={selectedEvent.riskComponents} />
                </div>

                <Link to={`/events/${selectedEvent.id}`} className="block w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-center text-sm font-medium text-slate-100 hover:border-orange-500/40 hover:text-orange-200">
                  View Full Event Intelligence →
                </Link>
              </div>
            ) : (
              <div className="flex h-full items-center justify-center text-slate-300">Select a thermal event</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function MapView({ events, facilities: mapFacilities, selectedEventId, onSelectEvent }: { events: ThermalEvent[]; facilities: Facility[]; selectedEventId: string; onSelectEvent: (id: string) => void }) {
  const [selectedEvent, setSelectedEvent] = useState<ThermalEvent | null>(null)

  useEffect(() => {
    setSelectedEvent(events.find((event) => event.id === selectedEventId) ?? null)
  }, [events, selectedEventId])

  return (
    <div className="space-y-3">
      <div className="map-toolbar flex items-center justify-between border-b border-slate-800 pb-2">
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] text-slate-400"><span className="live-dot" /> Live thermal field</div>
        <div className="flex gap-2 text-[10px] uppercase tracking-[0.18em] text-slate-400">
          <button className="rounded border border-slate-700 px-2 py-1">Reset view</button>
          <button className="rounded border border-slate-700 px-2 py-1">Show facilities</button>
        </div>
      </div>

      <div className="map-shell relative h-[560px] overflow-hidden rounded border border-slate-800">
        <MapLeaflet events={events} facilities={mapFacilities} selectedEvent={selectedEvent} onSelect={onSelectEvent} />
        <div className="map-overlay pointer-events-none absolute left-4 top-4 z-[500] rounded border border-cyan-300/20 bg-slate-950/70 px-3 py-2 backdrop-blur-md">
          <div className="text-[9px] uppercase tracking-[0.24em] text-cyan-200/80">India / Industrial Monitoring</div>
          <div className="mt-2 flex gap-3 text-[10px] uppercase tracking-[0.16em] text-slate-300">
            <span>{events.length} events</span><span>{mapFacilities.length} facilities</span>
          </div>
        </div>
        <div className="map-legend pointer-events-none absolute bottom-4 left-4 z-[500] rounded border border-slate-700/80 bg-slate-950/75 px-3 py-2 backdrop-blur-md">
          <div className="mb-2 text-[9px] uppercase tracking-[0.22em] text-slate-500">Risk intensity</div>
          <div className="flex gap-3 text-[9px] uppercase tracking-[0.14em] text-slate-300"><span><i className="legend-dot bg-emerald-400" />Low</span><span><i className="legend-dot bg-amber-300" />Moderate</span><span><i className="legend-dot bg-red-400" />Critical</span></div>
        </div>
        <div className="map-crosshair pointer-events-none absolute right-5 top-5 z-[500] h-10 w-10 rounded-full border border-cyan-300/25" />
      </div>
    </div>
  )
}

function MapLeaflet({ events, facilities: mapFacilities, selectedEvent, onSelect }: { events: ThermalEvent[]; facilities: Facility[]; selectedEvent: ThermalEvent | null; onSelect: (id: string) => void }) {
  function MapController() {
    const map = useMap()
    useEffect(() => {
      if (selectedEvent) {
        map.flyTo([selectedEvent.latitude, selectedEvent.longitude], 7, { duration: 0.8 })
      } else {
        map.setView([22.5, 78.96], 5)
      }
    }, [map, selectedEvent])

    return null
  }

  return (
    <MapContainer center={[22.5, 78.96]} zoom={5} scrollWheelZoom className="h-full w-full" style={{ height: '100%', width: '100%' }}>
      <MapController />
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap contributors" />
      {mapFacilities.map((facility) => (
        <Marker key={facility.id} position={[facility.latitude, facility.longitude]} icon={facilityIcon(facility.riskLevel)}>
          <Popup>
            <div className="text-xs text-slate-700">
              <strong>{facility.name}</strong><br />
              {facility.location}<br />
              {facility.type}
            </div>
          </Popup>
        </Marker>
      ))}
      {events.map((event) => (
        <CircleMarker
          key={event.id}
          center={[event.latitude, event.longitude]}
          radius={selectedEvent?.id === event.id ? 14 : 9}
          pathOptions={{
            color: getRiskColor(event.riskLevel),
            fillColor: getRiskColor(event.riskLevel),
            fillOpacity: selectedEvent?.id === event.id ? 1 : 0.85,
            weight: selectedEvent?.id === event.id ? 3 : 1,
          }}
          eventHandlers={{ click: () => onSelect(event.id) }}
        >
          <Popup>
            <div className="text-xs text-slate-700">
              <div className="font-semibold">{event.id}</div>
              <div>{event.classification}</div>
              <div>Risk: {event.riskLevel}</div>
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  )
}

function facilityIcon(level: string) {
  const color = getRiskColor(level)
  return L.divIcon({
    className: 'custom-facility',
    html: `<div class="facility-dot ${level === 'CRITICAL' ? 'facility-dot-critical' : ''}" style="--marker-color:${color};"></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  })
}

function ThermalEventsPage() {
  const [events, setEvents] = useState<ThermalEvent[]>([])
  const [liveFacilities, setLiveFacilities] = useState<Facility[]>(facilities)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState({
    risk: 'ALL',
    thermal: 'ALL',
    classification: 'ALL',
    facility: 'ALL',
    abnormalOnly: false,
    search: '',
  })

  useEffect(() => {
    getEvents()
      .then(setEvents)
      .catch(() => setError('Events are unavailable in demo mode.'))
      .finally(() => setLoading(false))
    getFacilities().then(setLiveFacilities)
  }, [])

  const filtered = useMemo(() => {
    return events.filter((event) => {
      if (filters.risk !== 'ALL' && event.riskLevel !== filters.risk) return false
      if (filters.thermal !== 'ALL' && event.thermalStatus !== filters.thermal) return false
      if (filters.classification !== 'ALL' && event.classification !== filters.classification) return false
      if (filters.facility !== 'ALL' && event.facilityId !== filters.facility) return false
      if (filters.abnormalOnly && event.thermalStatus === 'NORMAL') return false
      if (filters.search) {
        const text = `${event.id} ${event.classification} ${event.facilityName ?? ''} ${event.riskLevel} ${event.latitude} ${event.longitude}`.toLowerCase()
        if (!text.includes(filters.search.toLowerCase())) return false
      }
      return true
    })
  }, [events, filters])

  return (
    <div>
      <SectionHeader eyebrow="OPERATIONS" title="Thermal Event Queue" description="Every detection is contextualized before it reaches the operator." />
      <div className="mb-5 rounded border border-slate-800 bg-[#0d1218] p-4">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6 lg:gap-3">
          <input value={filters.search} onChange={(event) => setFilters((prev) => ({ ...prev, search: event.target.value }))} placeholder="Search" className="col-span-2 rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 sm:col-span-3 lg:col-span-1" />
          <select value={filters.risk} onChange={(event) => setFilters((prev) => ({ ...prev, risk: event.target.value }))} className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"><option value="ALL">All risk</option><option value="LOW">Low</option><option value="MODERATE">Moderate</option><option value="HIGH">High</option><option value="CRITICAL">Critical</option></select>
          <select value={filters.thermal} onChange={(event) => setFilters((prev) => ({ ...prev, thermal: event.target.value }))} className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"><option value="ALL">All thermal</option><option value="NORMAL">Normal</option><option value="MILDLY_ABNORMAL">Mildly Abnormal</option><option value="ABNORMAL">Abnormal</option></select>
          <select value={filters.classification} onChange={(event) => setFilters((prev) => ({ ...prev, classification: event.target.value }))} className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"><option value="ALL">All classifications</option><option value="Industrial Fire">Industrial Fire</option><option value="Gas Flare / Persistent Source">Gas Flare</option><option value="Wildfire">Wildfire</option><option value="Agricultural Burning">Agricultural Burning</option><option value="Mining Activity">Mining Activity</option><option value="Unknown">Unknown</option></select>
          <select value={filters.facility} onChange={(event) => setFilters((prev) => ({ ...prev, facility: event.target.value }))} className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"><option value="ALL">All facilities</option>{liveFacilities.map((facility) => <option key={facility.id} value={facility.id}>{facility.name}</option>)}</select>          <label className="flex items-center gap-2 rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200"><input type="checkbox" checked={filters.abnormalOnly} onChange={(event) => setFilters((prev) => ({ ...prev, abnormalOnly: event.target.checked }))} /> Abnormal only</label>
        </div>
        <div className="mt-4"><button className="rounded border border-slate-700 px-3 py-2 text-xs uppercase tracking-[0.18em] text-slate-300" onClick={() => setFilters({ risk: 'ALL', thermal: 'ALL', classification: 'ALL', facility: 'ALL', abnormalOnly: false, search: '' })}>Reset Filters</button></div>
      </div>

      {loading ? (
        <LoadingSkeleton label="EVENT QUEUE" />
      ) : error ? (
        <ErrorState title="Event feed unavailable" message={error} retry={() => getEvents().then(setEvents).catch(() => setError('Events are unavailable in demo mode.'))} />
      ) : filtered.length === 0 ? (
        <EmptyState title="NO THERMAL EVENTS MATCH YOUR FILTERS" description="Try adjusting your filters." action={<button className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm" onClick={() => setFilters({ risk: 'ALL', thermal: 'ALL', classification: 'ALL', facility: 'ALL', abnormalOnly: false, search: '' })}>Reset filters</button>} />
      ) : (
        <div className="overflow-hidden rounded border border-slate-800 bg-[#0d1218]">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-800 bg-slate-950/80 text-[10px] uppercase tracking-[0.22em] text-slate-500">
              <tr>
                <th className="px-4 py-3">Event</th>
                <th className="px-4 py-3">Time</th>
                <th className="px-4 py-3">Classification</th>
                <th className="px-4 py-3">Facility</th>
                <th className="px-4 py-3">Thermal status</th>
                <th className="px-4 py-3">Deviation</th>
                <th className="px-4 py-3">Risk</th>
                <th className="px-4 py-3">Lifecycle</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((event) => (
                <tr key={event.id} className="border-b border-slate-800 hover:bg-slate-900/60">
                  <td className="px-4 py-3 text-slate-100"><Link to={`/events/${event.id}`}>{event.id}</Link></td>
                  <td className="px-4 py-3 text-slate-300">{formatEventTime(event.timestamp)}</td>
                  <td className="px-4 py-3 text-slate-300">{event.classification}</td>
                  <td className="px-4 py-3 text-slate-300">{event.facilityName ?? 'Unknown'}</td>
                  <td className="px-4 py-3"><ThermalStatusBadge status={event.thermalStatus} /></td>
                  <td className="px-4 py-3 text-slate-300">{event.deviationScore}</td>
                  <td className="px-4 py-3"><RiskBadge level={event.riskLevel} /></td>
                  <td className="px-4 py-3 text-slate-300 uppercase tracking-[0.12em]">{event.lifecycle}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function EventDetailPage() {
  const location = useLocation()
  const id = location.pathname.split('/').pop() ?? ''
  const [event, setEvent] = useState<ThermalEvent | null>(null)
  const [liveFacilities, setLiveFacilities] = useState<Facility[]>(facilities)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getEvents()
      .then((events) => setEvent(events.find((item) => item.id === id) ?? null))
      .finally(() => setLoading(false))
    getFacilities().then(setLiveFacilities)
  }, [id])

  if (loading) return <LoadingSkeleton label="EVENT INTELLIGENCE" />
  if (!event) return <EmptyState title="Event not found" description="The requested event does not exist in the simulation." />

  return (
    <div className="space-y-6">
      <SectionHeader eyebrow="EVENT INVESTIGATION" title={event.id} description="Detailed intelligence for the selected thermal anomaly." />
      <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-5">
          <div className="analytics-panel rounded border border-slate-800 bg-[#0d1218] p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Event ID</div>
                <div className="mt-2 text-2xl font-semibold text-slate-100">{event.id}</div>
              </div>
              <div className="flex gap-2">
                <RiskBadge level={event.riskLevel} />
                <ThermalStatusBadge status={event.thermalStatus} />
              </div>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
              <MetricCard label="Timestamp" value={formatDate(event.timestamp)} />
              <MetricCard label="Coordinates" value={`${event.latitude.toFixed(3)}, ${event.longitude.toFixed(3)}`} />
              <MetricCard label="Classification" value={event.classification} />
              <MetricCard label="Confidence" value={`${event.classificationConfidence}%`} />
            </div>
          </div>

          <div className="rounded border border-slate-800 bg-[#0d1218] p-5">
            <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Thermal Observation</div>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <MetricCard label="Brightness" value={`${event.brightness} K`} />
              <MetricCard label="Satellite confidence" value={`${Math.round(event.confidence * 100)}%`} />
              <MetricCard label="Detection count" value={`${event.detectionCount}`} />
            </div>
          </div>

          <div className="rounded border border-slate-800 bg-[#0d1218] p-5">
            <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Deviation Analysis</div>
            <div className="mt-4 space-y-3">
              {[
                ['Location deviation', event.deviationScore, 'New hotspot location'],
                ['Intensity deviation', Math.min(96, event.riskComponents.intensity), 'Intensity exceeds baseline by 3.8×'],
                ['Temporal deviation', 82, 'Outside normal thermal window'],
                ['Persistence deviation', event.riskComponents.persistence, 'Event remains active'],
              ].map(([title, score, reason]) => (
                <div key={title as string} className="rounded border border-slate-800 bg-slate-950/80 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-medium text-slate-100">{title as string}</div>
                    <div className="text-sm text-slate-300">{score as number} / 100</div>
                  </div>
                  <div className="mt-2 h-2 rounded-full bg-slate-800"><div className="h-2 rounded-full bg-gradient-to-r from-orange-400 to-red-500" style={{ width: `${Number(score)}%` }} /></div>
                  <div className="mt-2 text-xs text-slate-400">{reason as string}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-5">
          <div className="rounded border border-slate-800 bg-[#0d1218] p-5">
            <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Risk Analysis</div>
            <div className="mt-3 text-4xl font-semibold text-slate-50">{event.riskScore} / 100</div>
            <div className="mt-2 text-xs uppercase tracking-[0.18em] text-red-300">{event.riskLevel}</div>
            <div className="mt-5 space-y-3">
              <RiskBars values={{ intensity: event.riskComponents.intensity, persistence: event.riskComponents.persistence, deviation: event.riskComponents.deviation, population: event.riskComponents.population, environmental: event.riskComponents.environmental, infrastructure: event.riskComponents.infrastructure }} />
            </div>
          </div>

          <div className="rounded border border-slate-800 bg-[#0d1218] p-5">
            <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Facility Context</div>
            <div className="mt-3 space-y-2 text-sm text-slate-300">
              <div>Facility: {event.facilityName ?? 'Unknown'}</div>
              <div>Type: {event.facilityType ?? 'Unknown'}</div>
              <div>Distance: {event.distanceToFacility ?? 0} km</div>
              <div>Baseline: {event.facilityId ? liveFacilities.find((item) => item.id === event.facilityId)?.baselineBrightness ?? 0 : 0} K</div>
              <div>Current thermal value: {event.brightness} K</div>
            </div>
          </div>

          <div className="rounded border border-slate-800 bg-[#0d1218] p-5">
            <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Environment</div>
            <div className="mt-3 space-y-2 text-sm text-slate-300">
              <div>Population proximity: Moderate</div>
              <div>Forest proximity: Low</div>
              <div>Land context: Industrial perimeter</div>
              <div>Environmental impact: {event.environmentalImpact}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function FacilitiesPage() {
  const [items, setItems] = useState<Facility[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getFacilities().then(setItems).finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingSkeleton label="FACILITIES" />

  return (
    <div>
      <SectionHeader eyebrow="SITE INTELLIGENCE" title="Facility Thermal Intelligence" description="What AgniLens knows about each monitored industrial site." />
      <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
        {items.map((facility) => (
          <div key={facility.id} className="rounded border border-slate-800 bg-[#0d1218] p-5">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">{facility.type}</div>
                <h3 className="mt-2 text-xl font-medium text-slate-100">{facility.name}</h3>
              </div>
              <ThermalStatusBadge status={facility.thermalStatus} />
            </div>
            <div className="mt-4 text-sm text-slate-400">{facility.location}</div>
            <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded border border-slate-800 bg-slate-950/80 p-3">
                <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Baseline</div>
                <div className="mt-2 text-lg text-slate-100">{facility.baselineBrightness} K</div>
              </div>
              <div className="rounded border border-slate-800 bg-slate-950/80 p-3">
                <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Current</div>
                <div className="mt-2 text-lg text-slate-100">{facility.currentBrightness} K</div>
              </div>
            </div>
            <div className="mt-5 flex items-center justify-between text-[10px] uppercase tracking-[0.18em] text-slate-500">
              <span>30D detections</span>
              <span>{facility.detections30d}</span>
            </div>
            <div className="mt-2 h-2 rounded-full bg-slate-800"><div className="h-2 rounded-full bg-gradient-to-r from-emerald-400 to-orange-400" style={{ width: `${facility.persistence}%` }} /></div>
            <div className="mt-2 text-right text-xs text-slate-400">Persistence {facility.persistence}%</div>
            <Link to={`/facilities/${facility.id}`} className="mt-5 inline-flex rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 hover:border-orange-500/40 hover:text-orange-200">VIEW THERMAL INTELLIGENCE →</Link>
          </div>
        ))}
      </div>
    </div>
  )
}

function FacilityDetailPage() {
  const location = useLocation()
  const id = location.pathname.split('/').pop() ?? ''
  const [facility, setFacility] = useState<Facility | null>(null)
  const [history, setHistory] = useState<FacilityHistory[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getFacilities()
      .then((items) => setFacility(items.find((entry) => entry.id === id) ?? null))
      .finally(() => setLoading(false))
    getFacilityHistory(id).then(setHistory)
  }, [id])

  if (loading) return <LoadingSkeleton label="FACILITY INTELLIGENCE" />
  if (!facility) return <EmptyState title="No facility matched" description="The selected facility is not available in the demo set." />

  return (
    <div className="space-y-6">
      <SectionHeader eyebrow="FACILITY OPERATIONS" title={`${facility.name} — ${facility.location}`} description="Facility-specific thermal profile and context." />
      <div className="rounded border border-slate-800 bg-[#0d1218] p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">{facility.type}</div>
            <div className="mt-2 text-3xl text-slate-100">{facility.id}</div>
          </div>
          <ThermalStatusBadge status={facility.thermalStatus} />
        </div>
        <div className="mt-6 grid gap-3 md:grid-cols-4">
          <MetricCard label="Baseline brightness" value={`${facility.baselineBrightness} K`} />
          <MetricCard label="Current brightness" value={`${facility.currentBrightness} K`} />
          <MetricCard label="Persistence" value={`${facility.persistence}%`} />
          <MetricCard label="Normal window" value={facility.normalWindow} />
        </div>
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="analytics-panel rounded border border-slate-800 bg-[#0d1218] p-5">
          <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Normal thermal profile</div>
          <div className="mt-4 space-y-3 text-sm text-slate-300">
            <div>Current thermal activity: {facility.currentBrightness} K</div>
            <div>Historical thermal activity: {facility.baselineBrightness} K baseline</div>
            <div>Typical hotspot zones: process area, flare stack, storage perimeter</div>
            <div>Frequency: {facility.detections30d} detections in 30 days</div>
            <div>Persistence: {facility.persistence}%</div>
            <div>Typical time window: {facility.normalWindow}</div>
          </div>
        </div>
        <div className="rounded border border-slate-800 bg-[#0d1218] p-5">
          <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Facility history</div>
          <div className="mt-4 space-y-3">
            {history.slice(0, 3).map((entry) => (
              <div key={entry.date} className="rounded border border-slate-800 bg-slate-950/80 p-3 text-sm text-slate-300">
                <div className="flex justify-between"><span>{entry.date}</span><span>{entry.anomaly}</span></div>
                <div className="mt-2">Observed {entry.observedBrightness} K • Baseline {entry.baseline} K • Threshold {entry.threshold} K</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function FeatureMeta({ role, input, output }: { role: string; input: string; output: string }) {
  return (
    <div className="feature-meta-grid grid gap-3 md:grid-cols-3">
      <div className="tech-card rounded border border-slate-800 p-4"><div className="eyebrow">Role</div><div className="mt-2 text-sm text-slate-200">{role}</div></div>
      <div className="tech-card rounded border border-slate-800 p-4"><div className="eyebrow">Input</div><div className="mt-2 text-sm text-slate-200">{input}</div></div>
      <div className="tech-card rounded border border-slate-800 p-4"><div className="eyebrow">Output</div><div className="mt-2 text-sm text-slate-200">{output}</div></div>
    </div>
  )
}

function WorkspaceSection({ eyebrow, title, children }: { eyebrow: string; title: string; children: ReactNode }) {
  return (
    <section className="workspace-section">
      <div className="eyebrow">{eyebrow}</div>
      <h3 className="mt-2 text-xl font-medium text-slate-100">{title}</h3>
      <div className="mt-4">{children}</div>
    </section>
  )
}

function PipelinePosition({ current }: { current: string }) {
  const stages = ['Physics Filter', 'Thermal Fingerprint', 'Deviation Engine', 'Type Attribution', 'Risk Intelligence', 'Lifecycle Tracking']
  return (
    <div className="pipeline-position tech-panel rounded border border-slate-800 p-4">
      <div className="eyebrow">AgniLens intelligence pipeline</div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        {stages.map((stage, index) => <div key={stage} className={`pipeline-stage ${stage === current ? 'is-current' : ''}`}><span>{String(index + 1).padStart(2, '0')}</span>{stage}</div>)}
      </div>
    </div>
  )
}

function EvidencePanel({ title, items, decision }: { title: string; items: string[]; decision: string }) {
  return (
    <div className="evidence-panel tech-panel rounded border border-slate-800 p-5">
      <div className="eyebrow">{title}</div>
      <div className="mt-4 space-y-3">{items.map((item) => <div key={item} className="flex items-start gap-3 text-sm text-slate-300"><span className="evidence-check">+</span><span>{item}</span></div>)}</div>
      <div className="mt-5 border-t border-slate-800 pt-4"><div className="eyebrow">Decision output</div><div className="mt-2 text-lg font-semibold text-orange-200">{decision}</div></div>
    </div>
  )
}

function SignalBar({ label, value, color = 'cyan', detail }: { label: string; value: number; color?: 'cyan' | 'amber' | 'red' | 'green'; detail?: string }) {
  return (
    <div className="signal-row">
      <div className="mb-2 flex items-center justify-between gap-3"><span className="text-xs uppercase tracking-[0.16em] text-slate-300">{label}</span><span className="text-sm font-semibold text-slate-100">{value}</span></div>
      <div className="signal-track"><div className={`signal-fill ${color}`} style={{ width: `${value}%` }} /></div>
      {detail && <div className="mt-1 text-xs text-slate-500">{detail}</div>}
    </div>
  )
}

function PhysicsFilterPage() {
  const [activeStage, setActiveStage] = useState(0)
  const stages = [
    { name: 'Thermal Detection', question: 'What signal entered the system?', output: 'FIRMS thermal detection', detail: 'Brightness, timestamp, coordinates and satellite confidence establish the initial candidate.' },
    { name: 'Spatial Check', question: 'Does the location align with known context?', output: 'Facility proximity / new location', detail: 'Distance to monitored facilities and land context separate expected industrial heat from a new hotspot.' },
    { name: 'Known Source Check', question: 'Is this a persistent known source?', output: 'Known source / unknown source', detail: 'Historical detections and facility baselines reveal repeatable operating signatures.' },
    { name: 'Persistence Check', question: 'Does the signal persist or escalate?', output: 'Stable / growing / transient', detail: 'Detection count and thermal continuity indicate whether the signal deserves deeper analysis.' },
    { name: 'Temporal Check', question: 'Does timing fit the facility window?', output: 'Expected / outside window', detail: 'Observed time is compared with the facility-specific normal operating window.' },
    { name: 'Decision', question: 'Should downstream intelligence investigate?', output: 'Expected source / investigate', detail: 'The transparent rule trace reduces noise before fingerprint, deviation and risk analysis.' },
  ]
  const event = demoEvents[1]
  return (
    <div className="feature-workspace space-y-6">
      <SectionHeader eyebrow="01 / PRE-PROCESSING" title="Physics-Based Fast Filter" description="Remove obvious thermal sources before they become noise." />
      <FeatureMeta role="Fast screening before deeper intelligence" input="Thermal detections + spatial and temporal context" output="Expected source / Investigate" />
      <WorkspaceSection eyebrow="Why physics first?" title="Reduce noise before analysis gets expensive">
        <div className="signal-flow tech-panel rounded border border-slate-800 p-5"><div className="flow-node">RAW THERMAL DETECTIONS<span>Many signals enter</span></div><div className="flow-line" /><div className="flow-node">EXPECTED SOURCES<span>Routine industrial heat</span></div><div className="flow-line" /><div className="flow-node active">FAST PHYSICS FILTER<span>Transparent rule trace</span></div><div className="flow-line" /><div className="flow-node result">REDUCED CANDIDATE SET<span>Deeper intelligence</span></div></div>
      </WorkspaceSection>
      <WorkspaceSection eyebrow="Interactive rule architecture" title="Select a stage to inspect its reasoning">
        <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="stage-grid">{stages.map((stage, index) => <button key={stage.name} onClick={() => setActiveStage(index)} className={`stage-node ${activeStage === index ? 'active' : ''}`}><span>{String(index + 1).padStart(2, '0')}</span><strong>{stage.name}</strong><small>{index === 0 ? 'Signal intake' : index === 5 ? 'Decision output' : 'Rule evaluation'}</small></button>)}</div>
          <div className="analysis-detail tech-panel rounded border border-slate-800 p-5"><div className="eyebrow">Stage {String(activeStage + 1).padStart(2, '0')} / analysis</div><div className="mt-3 text-lg font-medium text-slate-100">{stages[activeStage].name}</div><div className="mt-4 text-sm text-cyan-200">{stages[activeStage].question}</div><div className="mt-4 text-sm leading-6 text-slate-400">{stages[activeStage].detail}</div><div className="mt-5 border-t border-slate-800 pt-4"><div className="eyebrow">Output</div><div className="mt-2 text-orange-200">{stages[activeStage].output}</div></div></div>
        </div>
      </WorkspaceSection>
      <WorkspaceSection eyebrow="Deterministic demo analysis" title="Run the rule trace on a known sample event">
        <div className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="tech-panel rounded border border-slate-800 p-5"><div className="eyebrow">Sample event / {event.id}</div><div className="mt-3 text-2xl font-semibold text-slate-100">{event.classification}</div><div className="mt-4 grid grid-cols-2 gap-3"><MetricCard label="Brightness" value={`${event.brightness} K`} /><MetricCard label="Confidence" value={`${Math.round(event.confidence * 100)}%`} /><MetricCard label="Detection count" value={`${event.detectionCount}`} /><MetricCard label="Facility distance" value={`${event.distanceToFacility} km`} /></div></div>
          <EvidencePanel title="Decision trace" items={['Known industrial source context: YES', 'Persistent historical location: YES', 'Temporal pattern: EXPECTED', 'Spatial consistency: HIGH']} decision="EXPECTED THERMAL SOURCE" />
        </div>
      </WorkspaceSection>
      <WorkspaceSection eyebrow="Technical method" title="Signals used by the filter"><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4"><SignalBar label="Spatial consistency" value={92} detail="Facility and land context" /><SignalBar label="Persistence" value={event.riskComponents.persistence} color="amber" detail="Historical repeat signal" /><SignalBar label="Temporal fit" value={88} color="green" detail="Known operating window" /><SignalBar label="Source confidence" value={Math.round(event.confidence * 100)} detail="Satellite detection confidence" /></div></WorkspaceSection>
      <PipelinePosition current="Physics Filter" />
    </div>
  )
}

function FingerprintPage() {
  const facility = facilities[0]
  const data = fingerprintData[facility.id]
  const [view, setView] = useState<'baseline' | 'observed'>('observed')
  const chartData = data.timeLabels.map((label, index) => ({ label, observed: view === 'observed' ? data.observed[index] : data.baseline[index], baseline: data.baseline[index], threshold: data.threshold[index] }))
  return (
    <div className="feature-workspace space-y-6">
      <SectionHeader eyebrow="02 / FACILITY BASELINE" title="Facility Thermal Fingerprint" description="Every facility gets its own baseline and anomaly threshold." />
      <FeatureMeta role="Learn normal facility-specific thermal behavior" input="Historical detections, intensity, timing and location" output="Baseline, threshold and current deviation" />
      <WorkspaceSection eyebrow="What is a thermal fingerprint?" title="Normal behavior is a facility-specific signal">
        <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="tech-panel rounded border border-slate-800 p-5"><div className="eyebrow">DEMO FACILITY / {facility.id}</div><div className="mt-3 text-3xl font-semibold text-slate-100">{facility.name}</div><p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">AgniLens compresses repeated thermal observations into a baseline: where heat appears, how intense it is, when it normally occurs, and how long it persists.</p><div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4"><MetricCard label="Baseline" value={`${facility.baselineBrightness} K`} /><MetricCard label="Frequency" value={`${data.frequency} / 30d`} /><MetricCard label="Persistence" value={`${data.persistence}%`} /><MetricCard label="Window" value={data.typicalWindow} /></div></div>
          <div className="fingerprint-orbit tech-panel rounded border border-slate-800 p-5"><div className="eyebrow">Thermal signature</div><div className="thermal-orbit"><span className="orbit-core" /><span className="orbit-ring ring-one" /><span className="orbit-ring ring-two" /></div><div className="text-center text-xs uppercase tracking-[0.18em] text-slate-400">Historical source pattern</div></div>
        </div>
      </WorkspaceSection>
      <div className="grid gap-5 xl:grid-cols-[0.8fr_1.4fr]">
        <div className="space-y-5"><div className="analytics-panel rounded border border-slate-800 bg-[#0d1218] p-5"><div className="eyebrow">Facility profile</div><div className="mt-3 text-2xl font-semibold text-slate-100">{facility.name}</div><div className="mt-4 grid gap-3"><MetricCard label="Thermal baseline" value={`${facility.baselineBrightness} K`} /><MetricCard label="Current intensity" value={`${facility.currentBrightness} K`} /><MetricCard label="Normal range" value={`${facility.baselineBrightness - 20}-${facility.baselineBrightness + 25} K`} /><MetricCard label="Operating window" value={facility.normalWindow} /></div></div><div className="analytics-panel rounded border border-slate-800 bg-[#0d1218] p-5"><div className="eyebrow">Current status</div><div className="mt-4 flex items-center justify-between"><span className="text-slate-300">Delta from baseline</span><span className="text-2xl text-red-300">+{data.delta} K</span></div><div className="mt-4"><ThermalStatusBadge status={data.status} /></div></div></div>
        <div className="analytics-panel chart-workspace rounded border border-slate-800 bg-[#0d1218] p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><div className="eyebrow">Observed vs baseline</div><div className="mt-1 text-sm text-slate-400">Threshold bands expose when current behavior breaks the learned pattern.</div></div><div className="toggle-group"><button className={view === 'baseline' ? 'active' : ''} onClick={() => setView('baseline')}>Baseline</button><button className={view === 'observed' ? 'active' : ''} onClick={() => setView('observed')}>Observed</button></div></div><div className="mt-4 h-80"><ResponsiveContainer width="100%" height="100%"><LineChart data={chartData}><CartesianGrid stroke="#1e293b" strokeDasharray="3 3" /><XAxis dataKey="label" stroke="#94a3b8" /><YAxis stroke="#94a3b8" /><Tooltip contentStyle={{ background: '#0b1724', border: '1px solid #2dd4bf', color: '#e2e8f0' }} /><Line type="monotone" dataKey="baseline" stroke="#22d3ee" dot={false} strokeWidth={2} /><Line type="monotone" dataKey="threshold" stroke="#facc15" dot={false} strokeWidth={2} /><Line type="monotone" dataKey="observed" stroke={view === 'observed' ? '#f97316' : '#67e8f9'} dot={{ r: 4 }} strokeWidth={3} /></LineChart></ResponsiveContainer></div></div>
      </div>
      <WorkspaceSection eyebrow="What changed?" title="Current observation versus learned normal"><div className="grid gap-3 md:grid-cols-4"><SignalBar label="New location" value={94} color="red" detail="Outside normal zone" /><SignalBar label="Higher intensity" value={91} color="amber" detail={`Current ${data.currentValue} K`} /><SignalBar label="Unusual time" value={82} detail="Outside expected window" /><SignalBar label="Increased frequency" value={76} color="amber" detail={`${data.frequency} detections / 30d`} /></div></WorkspaceSection>
      <EvidencePanel title="Fingerprint evidence" items={['Baseline learned from repeated facility observations', 'Current brightness is above threshold', 'Observed signal overlaps the facility context', 'Deviation is passed to the next intelligence stage']} decision="ABNORMAL THERMAL SIGNATURE" />
      <PipelinePosition current="Thermal Fingerprint" />
    </div>
  )
}

function DeviationPage() {
  const [selected, setSelected] = useState('Location')
  const metrics = [{ label: 'Location', value: 94, detail: 'New hotspot outside normal zone' }, { label: 'Intensity', value: 91, detail: '388 K versus 342 K baseline' }, { label: 'Timing', value: 82, detail: 'Outside 20:00-23:00 window' }, { label: 'Persistence', value: 76, detail: 'Signal remains active across detections' }]
  return (
    <div className="feature-workspace space-y-6">
      <SectionHeader eyebrow="03" title="Deviation Engine" description="Normal is facility-specific and context-aware." />
      <FeatureMeta role="Compare current behavior against learned normal" input="Baseline + current event + context" output="Normal, mildly abnormal or abnormal" />
      <WorkspaceSection eyebrow="Expected versus observed" title="Deviation is a structured comparison, not a single guess">
        <div className="rounded border border-slate-800 bg-[#0d1218] p-5">
          <div className="grid gap-5 lg:grid-cols-3">
            <div className="rounded border border-slate-800 bg-slate-950/80 p-4">
              <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Facility Baseline</div>
              <div className="mt-3 text-3xl text-slate-100">342 K</div>
              <div className="mt-2 text-sm text-slate-300">Normal location</div>
              <div className="mt-2 text-sm text-slate-300">20:00–23:00</div>
              <div className="mt-2 text-sm text-slate-300">Typical persistence</div>
            </div>
            <div className="rounded border border-slate-800 bg-slate-950/80 p-4">
              <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Current Observation</div>
              <div className="mt-3 text-3xl text-slate-100">388 K</div>
              <div className="mt-2 text-sm text-slate-300">New location</div>
              <div className="mt-2 text-sm text-slate-300">01:40</div>
              <div className="mt-2 text-sm text-slate-300">High persistence</div>
            </div>
            <div className="rounded border border-slate-800 bg-slate-950/80 p-4">
              <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Comparison</div>
              <div className="mt-6 text-center text-3xl font-semibold text-slate-100">VS</div>
              <div className="mt-3 text-center text-sm text-slate-300">Deviation result</div>
            </div>
          </div>
        </div>
      </WorkspaceSection>
      <WorkspaceSection eyebrow="Interactive decomposition" title="Select a dimension to inspect its evidence"><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">{metrics.map((metric) => <button key={metric.label} onClick={() => setSelected(metric.label)} className={`deviation-module ${selected === metric.label ? 'active' : ''}`}><div className="eyebrow">{metric.label}</div><div className="mt-3 text-3xl font-semibold text-slate-100">{metric.value}</div><SignalBar label="" value={metric.value} color={metric.value > 90 ? 'red' : 'amber'} /><div className="mt-3 text-left text-xs text-slate-400">{metric.detail}</div></button>)}</div><div className="mt-4 tech-panel rounded border border-slate-800 p-4"><div className="eyebrow">Selected dimension / {selected}</div><div className="mt-2 text-sm text-slate-300">{metrics.find((metric) => metric.label === selected)?.detail}</div></div></WorkspaceSection>
      <div className="analytics-panel rounded border border-slate-800 bg-[#0d1218] p-5">
        <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Final result</div>
        <div className="mt-3 text-3xl font-semibold text-orange-200">ABNORMAL / 94 / 100</div>
        <div className="mt-4 text-sm text-slate-300">Reasons: new hotspot location, intensity above baseline, outside normal thermal window.</div>
      </div>
      <EvidencePanel title="Explainable deviation evidence" items={metrics.map((metric) => `${metric.label}: ${metric.detail}`)} decision="STRONGLY ABNORMAL" />
      <PipelinePosition current="Deviation Engine" />
    </div>
  )
}

function ClassificationPage() {
  const [selected, setSelected] = useState('Industrial Fire')
  const candidates = [['Industrial Fire', 91], ['Gas Flare / Persistent Source', 4], ['Wildfire', 2], ['Agricultural Burning', 1], ['Unknown', 2]] as const
  return (
    <div className="feature-workspace space-y-6">
      <SectionHeader eyebrow="04 / CONTEXTUAL INFERENCE" title="Context-Aware Type Attribution" description="Turn a hotspot into a probable source type." />
      <FeatureMeta role="Attribute a likely source type" input="Thermal signal + facility, land and temporal context" output="Ranked candidate classes with evidence" />
      <WorkspaceSection eyebrow="How attribution works" title="Context narrows the explanation"><div className="classification-flow tech-panel rounded border border-slate-800 p-5"><div>THERMAL SIGNAL</div><span>+</span><div>FACILITY CONTEXT</div><span>+</span><div>LAND CONTEXT</div><span>+</span><div>TEMPORAL BEHAVIOUR</div><span>{'->'}</span><div className="active">PROBABLE EVENT TYPE</div></div></WorkspaceSection>
      <WorkspaceSection eyebrow="Demo model output" title="Ranked candidate classes"><div className="grid gap-5 lg:grid-cols-[1.25fr_0.75fr]"><div className="tech-panel rounded border border-slate-800 p-5"><div className="eyebrow">Deterministic demonstration / EVT-001</div><div className="mt-4 space-y-4">{candidates.map(([label, value]) => <button key={label} onClick={() => setSelected(label)} className={`probability-row ${selected === label ? 'active' : ''}`}><div className="flex justify-between gap-3 text-sm"><span>{label}</span><strong>{value}%</strong></div><div className="signal-track mt-2"><div className={`signal-fill ${value > 50 ? 'red' : 'cyan'}`} style={{ width: `${Math.max(value, 3)}%` }} /></div></button>)}</div></div><div className="analysis-detail tech-panel rounded border border-slate-800 p-5"><div className="eyebrow">Selected interpretation</div><div className="mt-3 text-3xl font-semibold text-orange-200">{selected}</div><div className="mt-4 text-sm leading-6 text-slate-400">This is an illustrative demo model output, not a claim of scientifically validated probability. The selected candidate is supported by the contextual evidence below.</div></div></div></WorkspaceSection>
      <WorkspaceSection eyebrow="Contextual evidence" title="Why the leading class wins"><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5"><SignalBar label="Land cover" value={89} detail="Industrial perimeter" /><SignalBar label="Facility proximity" value={94} color="amber" detail="0.7 km from refinery" /><SignalBar label="Thermal pattern" value={91} color="red" detail="High intensity deviation" /><SignalBar label="Persistence" value={79} color="amber" detail="Six detections" /><SignalBar label="Spatial context" value={86} detail="Within monitored site" /></div></WorkspaceSection>
      <EvidencePanel title="Attribution evidence" items={['Industrial facility proximity', 'New thermal location', 'High intensity deviation', 'Abnormal persistence']} decision="INDUSTRIAL FIRE / DEMO OUTPUT" />
      <PipelinePosition current="Type Attribution" />
    </div>
  )
}

function RiskPage() {
  const score = 91
  const drivers = {
    Thermal: 95,
    Persistence: 79,
    Deviation: 96,
    Population: 72,
    Environment: 45,
    Infrastructure: 88,
  }

  return (
    <div className="feature-workspace space-y-6">
      <SectionHeader eyebrow="05 / DECISION SUPPORT" title="Explainable Risk Intelligence" description="A score is useful only when you can explain it." />
      <FeatureMeta role="Translate evidence into a decision-support index" input="Thermal, deviation, persistence and context" output="Risk score, level and contributing factors" />
      <div className="risk-hero rounded border border-slate-800 bg-[#0d1218] p-6 text-center">
        <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Risk score</div>
        <div className="mt-4 flex justify-center"><RiskMeter score={score} level="CRITICAL" /></div>
      </div>
      <WorkspaceSection eyebrow="Risk decomposition" title="Every contributor remains visible"><div className="tech-panel rounded border border-slate-800 p-5"><div className="space-y-4">
        {Object.entries(drivers).map(([label, value]) => (
          <SignalBar key={label} label={label} value={value} color={value > 90 ? 'red' : value > 70 ? 'amber' : 'cyan'} detail="Contribution to explainable index" />
        ))}
      </div></div></WorkspaceSection>
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="analytics-panel rounded border border-slate-800 bg-[#0d1218] p-5">
          <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Why this is critical</div>
          <ol className="mt-4 list-decimal space-y-3 pl-5 text-sm text-slate-300">
            <li>Intensity is 3.8x above baseline.</li>
            <li>Hotspot is outside the facility's normal thermal zone.</li>
            <li>Event is actively growing.</li>
            <li>Population is within the exposure radius.</li>
          </ol>
        </div>
        <div className="analytics-panel rounded border border-slate-800 bg-[#0d1218] p-5">
          <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">How risk is calculated</div>
          <div className="mt-4 space-y-3 text-sm text-slate-300">
            <div>Thermal 25%</div>
            <div>Persistence 20%</div>
            <div>Deviation 25%</div>
            <div>Population 15%</div>
            <div>Environment 10%</div>
            <div>Infrastructure 5%</div>
            <div className="mt-4 text-orange-300">↓ Risk Score</div>
          </div>
        </div>
      </div>
      <EvidencePanel title="Decision support evidence" items={['Strong deviation from facility baseline', 'Elevated thermal intensity', 'Persistent activity across detections', 'Sensitive context contributes to exposure']} decision="CRITICAL / EXPLAINABLE INDEX" />
      <PipelinePosition current="Risk Intelligence" />
    </div>
  )
}

function LifecyclePage() {
  const [step, setStep] = useState(1)
  const timeline = [{ label: 'FIRST SEEN', time: '20 Aug / 18:20', intensity: 64, risk: 42 }, { label: 'GROWING', time: '20 Aug / 19:10', intensity: 78, risk: 63 }, { label: 'PERSISTENT', time: '20 Aug / 20:05', intensity: 86, risk: 78 }, { label: 'DECLINING', time: '20 Aug / 21:00', intensity: 72, risk: 69 }, { label: 'REIGNITED', time: '20 Aug / 21:30', intensity: 95, risk: 91 }]
  const current = timeline[step]
  return (
    <div className="feature-workspace space-y-6">
      <SectionHeader eyebrow="06 / TEMPORAL ANALYSIS" title="Thermal Event Lifecycle" description="Follow an event from first detection to resolution." />
      <FeatureMeta role="Track how an anomaly evolves over time" input="Repeated detections, intensity, risk and state" output="Current lifecycle state and trend evidence" />
      <WorkspaceSection eyebrow="Interactive event timeline" title="Move through the event and inspect the state transition"><div className="lifecycle-workspace tech-panel rounded border border-slate-800 p-5"><div className="lifecycle-track">{timeline.map((item, index) => <button key={item.label} onClick={() => setStep(index)} className={`lifecycle-node ${step === index ? 'active' : ''}`}><span>{String(index + 1).padStart(2, '0')}</span><strong>{item.label}</strong><small>{item.time}</small></button>)}</div><input className="lifecycle-slider mt-7 w-full" type="range" min="0" max={timeline.length - 1} value={step} onChange={(event) => setStep(Number(event.target.value))} aria-label="Lifecycle timeline" /><div className="mt-7 grid gap-5 md:grid-cols-3"><MetricCard label="Current state" value={current.label} /><MetricCard label="Thermal intensity" value={`${current.intensity} / 100`} /><MetricCard label="Risk evolution" value={`${current.risk} / 100`} /></div></div></WorkspaceSection>
      <div className="grid gap-5 lg:grid-cols-2"><div className="analytics-panel rounded border border-slate-800 bg-[#0d1218] p-5"><div className="eyebrow">Signal evolution</div><div className="mt-5 space-y-5">{timeline.map((item, index) => <div key={item.label} className={`timeline-row ${step === index ? 'active' : ''}`}><div><span className="text-sm font-semibold text-slate-200">{item.label}</span><div className="text-xs text-slate-500">{item.time}</div></div><div className="flex-1"><SignalBar label="" value={item.intensity} color={item.intensity > 90 ? 'red' : 'amber'} /></div></div>)}</div></div><EvidencePanel title="Lifecycle evidence" items={[`State selected: ${current.label}`, `Thermal signal: ${current.intensity} / 100`, `Risk signal: ${current.risk} / 100`, 'Repeated detections preserve the event history']} decision={`${current.label} / EVENT STATE`} /></div>
      <PipelinePosition current="Lifecycle Tracking" />
    </div>
  )
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<CommandCenterPage />} />
      <Route path="/command-center" element={<CommandCenterPage />} />
      <Route path="/events" element={<ThermalEventsPage />} />
      <Route path="/events/:eventId" element={<EventDetailPage />} />
      <Route path="/facilities" element={<FacilitiesPage />} />
      <Route path="/facilities/:facilityId" element={<FacilityDetailPage />} />
      <Route path="/intelligence/fast-filter" element={<PhysicsFilterPage />} />
      <Route path="/intelligence/fingerprint" element={<FingerprintPage />} />
      <Route path="/intelligence/deviation" element={<DeviationPage />} />
      <Route path="/intelligence/classification" element={<ClassificationPage />} />
      <Route path="/intelligence/risk" element={<RiskPage />} />
      <Route path="/intelligence/lifecycle" element={<LifecyclePage />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <AppRoutes />
      </AppShell>
    </BrowserRouter>
  )
}
