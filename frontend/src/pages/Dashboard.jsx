import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getJobs, getSearchRuns, runSearch, checkHealth } from '../services/api'

function StatCard({ title, value, subtitle }) {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-sm font-medium text-gray-500">{title}</h3>
      <p className="text-3xl font-bold text-gray-900 mt-2">{value}</p>
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
  const [error, setError] = useState(null)
  const [selectedSource, setSelectedSource] = useState('heb,indeed,wellfound')

  useEffect(() => {
    loadDashboard()
  }, [])

  async function loadDashboard() {
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
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSearching ? 'Searching...' : 'Run'}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <StatCard title="New Jobs" value={stats.newJobs} subtitle="Awaiting review" />
        <StatCard title="Total Jobs" value={stats.totalJobs} subtitle="In database" />
        <StatCard title="Applied" value={stats.applied} subtitle="Applications sent" />
      </div>

      {lastRun && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Last Search</h2>
          <div className="text-sm text-gray-600">
            <p>
              <span className="font-medium">Run at:</span>{' '}
              {new Date(lastRun.run_at).toLocaleString()}
            </p>
            <p>
              <span className="font-medium">Jobs found:</span> {lastRun.jobs_found}
            </p>
            <p>
              <span className="font-medium">New jobs:</span> {lastRun.new_jobs}
            </p>
            <p>
              <span className="font-medium">Duration:</span>{' '}
              {lastRun.duration_seconds.toFixed(2)}s
            </p>
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
