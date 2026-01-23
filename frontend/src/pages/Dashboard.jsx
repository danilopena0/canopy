import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getJobs, getSearchRuns, runSearch, checkHealth } from '../services/api'

function formatRelativeTime(dateString) {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now - date
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffSecs < 60) return 'just now'
  if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`
  if (diffDays === 1) return 'yesterday'
  if (diffDays < 7) return `${diffDays} days ago`
  return date.toLocaleDateString()
}

function LoadingSpinner({ size = 'md', light = false }) {
  const sizes = {
    sm: 'h-4 w-4',
    md: 'h-6 w-6',
    lg: 'h-8 w-8',
  }
  const color = light ? 'border-white' : 'border-blue-600'
  return (
    <div className={`animate-spin rounded-full border-b-2 ${color} ${sizes[size]}`}></div>
  )
}

function StatCard({ title, value, subtitle, loading }) {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-sm font-medium text-gray-500">{title}</h3>
      {loading ? (
        <div className="mt-2">
          <LoadingSpinner size="md" />
        </div>
      ) : (
        <p className="text-3xl font-bold text-gray-900 mt-2">{value}</p>
      )}
      {subtitle && <p className="text-sm text-gray-500 mt-1">{subtitle}</p>}
    </div>
  )
}

const SOURCE_OPTIONS = [
  { value: 'heb,indeed,wellfound', label: 'All Sources' },
  { value: 'heb', label: 'H-E-B' },
  { value: 'indeed', label: 'Indeed' },
  { value: 'wellfound', label: 'Wellfound' },
]

export default function Dashboard() {
  const [stats, setStats] = useState({
    newJobs: 0,
    totalJobs: 0,
    applied: 0,
  })
  const [lastRun, setLastRun] = useState(null)
  const [isHealthy, setIsHealthy] = useState(false)
  const [isSearching, setIsSearching] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedSource, setSelectedSource] = useState('heb,indeed,wellfound')

  useEffect(() => {
    loadDashboard()
  }, [])

  async function loadDashboard() {
    setIsLoading(true)
    try {
      // Check API health
      await checkHealth()
      setIsHealthy(true)

      // Load jobs stats
      const [newJobs, allJobs, appliedJobs] = await Promise.all([
        getJobs({ status: 'new' }),
        getJobs({}),
        getJobs({ status: 'applied' }),
      ])

      setStats({
        newJobs: newJobs.total,
        totalJobs: allJobs.total,
        applied: appliedJobs.total,
      })

      // Load last search run
      const runs = await getSearchRuns(1)
      if (runs.length > 0) {
        setLastRun(runs[0])
      }

      setError(null)
    } catch (err) {
      setError(err.message)
      setIsHealthy(false)
    } finally {
      setIsLoading(false)
    }
  }

  async function handleRunSearch() {
    setIsSearching(true)
    setError(null)
    try {
      const result = await runSearch({ sources: selectedSource })
      await loadDashboard()
      if (result.errors && result.errors.length > 0) {
        setError(`Completed with errors: ${result.errors.join('; ')}`)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setIsSearching(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500 mt-1">
            {isHealthy ? (
              <span className="text-green-600">API Connected</span>
            ) : (
              <span className="text-red-600">API Disconnected</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={selectedSource}
            onChange={(e) => setSelectedSource(e.target.value)}
            disabled={isSearching || !isHealthy}
            className="px-3 py-2 border border-gray-300 rounded-lg bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          >
            {SOURCE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <button
            onClick={handleRunSearch}
            disabled={isSearching || !isHealthy}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {isSearching && <LoadingSpinner size="sm" light />}
            {isSearching ? 'Searching...' : 'Run Search'}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <StatCard title="New Jobs" value={stats.newJobs} subtitle="Awaiting review" loading={isLoading} />
        <StatCard title="Total Jobs" value={stats.totalJobs} subtitle="In database" loading={isLoading} />
        <StatCard title="Applied" value={stats.applied} subtitle="Applications sent" loading={isLoading} />
      </div>

      {lastRun && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium text-gray-900">Last Search</h2>
            <span className="text-sm text-gray-500" title={new Date(lastRun.run_at).toLocaleString()}>
              {formatRelativeTime(lastRun.run_at)}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold text-gray-900">{lastRun.jobs_found}</p>
              <p className="text-sm text-gray-500">Found</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-blue-600">{lastRun.new_jobs}</p>
              <p className="text-sm text-gray-500">New</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{lastRun.duration_seconds.toFixed(1)}s</p>
              <p className="text-sm text-gray-500">Duration</p>
            </div>
          </div>
        </div>
      )}

      <div className="mt-8">
        <Link
          to="/jobs"
          className="text-blue-600 hover:text-blue-800 font-medium"
        >
          View all jobs &rarr;
        </Link>
      </div>
    </div>
  )
}
