import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getJobs, searchJobs, updateJob } from '../services/api'

const STATUS_OPTIONS = [
  { value: '', label: 'All', color: 'bg-gray-100 text-gray-700 hover:bg-gray-200' },
  { value: 'new', label: 'New', color: 'bg-blue-100 text-blue-800 hover:bg-blue-200' },
  { value: 'reviewed', label: 'Reviewed', color: 'bg-yellow-100 text-yellow-800 hover:bg-yellow-200' },
  { value: 'applied', label: 'Applied', color: 'bg-green-100 text-green-800 hover:bg-green-200' },
  { value: 'rejected', label: 'Rejected', color: 'bg-red-100 text-red-800 hover:bg-red-200' },
  { value: 'archived', label: 'Archived', color: 'bg-gray-100 text-gray-600 hover:bg-gray-200' },
]

function StatusBadge({ status }) {
  const colors = {
    new: 'bg-blue-100 text-blue-800',
    reviewed: 'bg-yellow-100 text-yellow-800',
    applied: 'bg-green-100 text-green-800',
    rejected: 'bg-red-100 text-red-800',
    archived: 'bg-gray-100 text-gray-800',
  }

  return (
    <span className={`px-2 py-1 text-xs font-medium rounded-full ${colors[status] || colors.new}`}>
      {status}
    </span>
  )
}

function formatRelativeTime(dateString) {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now - date
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffSecs < 60) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays === 1) return 'yesterday'
  if (diffDays < 7) return `${diffDays}d ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`
  return date.toLocaleDateString()
}

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center p-8">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      <span className="ml-3 text-gray-500">Loading jobs...</span>
    </div>
  )
}

function SortableHeader({ label, field, currentSort, currentOrder, onSort }) {
  const isActive = currentSort === field
  const arrow = isActive ? (currentOrder === 'asc' ? '↑' : '↓') : ''

  return (
    <th
      className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 select-none"
      onClick={() => onSort(field)}
    >
      <span className="flex items-center gap-1">
        {label}
        <span className="text-blue-600">{arrow}</span>
      </span>
    </th>
  )
}

function formatSalary(min, max) {
  if (!min && !max) return null
  const fmt = (n) => '$' + n.toLocaleString()
  if (min && max && min !== max) {
    return `${fmt(min)} - ${fmt(max)}`
  }
  return fmt(min || max)
}

function SourceBadge({ source }) {
  const colors = {
    heb: 'bg-red-50 text-red-700',
    indeed: 'bg-purple-50 text-purple-700',
    wellfound: 'bg-orange-50 text-orange-700',
  }
  const labels = {
    heb: 'H-E-B',
    indeed: 'Indeed',
    wellfound: 'Wellfound',
  }
  return (
    <span className={`px-1.5 py-0.5 text-xs rounded ${colors[source] || 'bg-gray-50 text-gray-600'}`}>
      {labels[source] || source}
    </span>
  )
}

function DuplicateBadge() {
  return (
    <span className="px-1.5 py-0.5 text-xs rounded bg-amber-50 text-amber-700" title="Duplicate of another job">
      Dup
    </span>
  )
}

function JobRow({ job, onArchive }) {
  return (
    <tr className={`hover:bg-gray-50 ${job.duplicate_of ? 'opacity-60' : ''}`}>
      <td className="px-6 py-4">
        <Link to={`/jobs/${job.id}`} className="text-blue-600 hover:text-blue-800 font-medium">
          {job.title}
        </Link>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-sm text-gray-500">{job.company}</span>
          <SourceBadge source={job.source} />
          {job.duplicate_of && <DuplicateBadge />}
        </div>
      </td>
      <td className="px-6 py-4 text-sm text-gray-600">
        {job.location || 'Not specified'}
      </td>
      <td className="px-6 py-4 text-sm text-gray-600">
        {formatSalary(job.salary_min, job.salary_max) || '-'}
      </td>
      <td className="px-6 py-4 text-sm text-gray-600">
        {job.work_type || '-'}
      </td>
      <td className="px-6 py-4">
        {job.fit_score !== null ? (
          <span className="font-medium">{job.fit_score.toFixed(0)}</span>
        ) : (
          <span className="text-gray-400">-</span>
        )}
      </td>
      <td className="px-6 py-4">
        <StatusBadge status={job.status} />
      </td>
      <td className="px-6 py-4 text-sm text-gray-500" title={new Date(job.scraped_at).toLocaleString()}>
        {formatRelativeTime(job.scraped_at)}
      </td>
      <td className="px-6 py-4">
        {job.status !== 'archived' && (
          <button
            onClick={() => onArchive(job.id)}
            className="text-gray-400 hover:text-gray-600"
            title="Archive job"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
            </svg>
          </button>
        )}
      </td>
    </tr>
  )
}

export default function JobList() {
  const [jobs, setJobs] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Filters
  const [statusFilter, setStatusFilter] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [hideDuplicates, setHideDuplicates] = useState(true)

  // Sorting
  const [sortField, setSortField] = useState('scraped_at')
  const [sortOrder, setSortOrder] = useState('desc')

  const pageSize = 20

  useEffect(() => {
    loadJobs()
  }, [page, statusFilter, sortField, sortOrder])

  async function loadJobs() {
    setLoading(true)
    try {
      const params = {
        page,
        page_size: pageSize,
      }
      if (statusFilter) {
        params.status = statusFilter
      }

      const result = await getJobs(params)
      setJobs(result.items)
      setTotal(result.total)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleSearch(e) {
    e.preventDefault()
    if (!searchQuery.trim()) {
      loadJobs()
      return
    }

    setLoading(true)
    try {
      const result = await searchJobs(searchQuery, { page: 1, page_size: pageSize })
      setJobs(result.items)
      setTotal(result.total)
      setPage(1)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const totalPages = Math.ceil(total / pageSize)

  function handleSort(field) {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortOrder('desc')
    }
    setPage(1)
  }

  async function handleArchive(jobId) {
    try {
      await updateJob(jobId, { status: 'archived' })
      // Refresh job list
      loadJobs()
    } catch (err) {
      setError(err.message)
    }
  }

  // Filter and sort jobs client-side
  const filteredJobs = hideDuplicates ? jobs.filter(job => !job.duplicate_of) : jobs
  const sortedJobs = [...filteredJobs].sort((a, b) => {
    let aVal = a[sortField]
    let bVal = b[sortField]

    // Handle null/undefined
    if (aVal == null) return sortOrder === 'asc' ? 1 : -1
    if (bVal == null) return sortOrder === 'asc' ? -1 : 1

    // Handle dates
    if (sortField === 'scraped_at') {
      aVal = new Date(aVal).getTime()
      bVal = new Date(bVal).getTime()
    }

    // Handle numbers
    if (sortField === 'fit_score' || sortField === 'salary_min') {
      aVal = Number(aVal) || 0
      bVal = Number(bVal) || 0
    }

    // Handle strings
    if (typeof aVal === 'string') {
      aVal = aVal.toLowerCase()
      bVal = bVal.toLowerCase()
    }

    if (aVal < bVal) return sortOrder === 'asc' ? -1 : 1
    if (aVal > bVal) return sortOrder === 'asc' ? 1 : -1
    return 0
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Jobs</h1>
        <span className="text-gray-500">{total} total</span>
      </div>

      {/* Search */}
      <div className="bg-white rounded-lg shadow p-4 mb-4">
        <form onSubmit={handleSearch}>
          <input
            type="text"
            placeholder="Search jobs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </form>
      </div>

      {/* Status Filter Buttons */}
      <div className="flex flex-wrap items-center gap-2 mb-6">
        {STATUS_OPTIONS.map((option) => {
          const isActive = statusFilter === option.value
          return (
            <button
              key={option.value}
              onClick={() => {
                setStatusFilter(option.value)
                setPage(1)
              }}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? option.color.replace('hover:', '') + ' ring-2 ring-offset-1 ring-blue-500'
                  : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200'
              }`}
            >
              {option.label}
            </button>
          )
        })}
        <div className="h-6 w-px bg-gray-300 mx-2"></div>
        <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
          <input
            type="checkbox"
            checked={hideDuplicates}
            onChange={(e) => setHideDuplicates(e.target.checked)}
            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          Hide duplicates
        </label>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      {/* Job table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        {loading ? (
          <LoadingSpinner />
        ) : filteredJobs.length === 0 ? (
          <div className="p-8 text-center">
            <p className="text-gray-500 mb-2">No jobs found</p>
            <p className="text-sm text-gray-400">
              {jobs.length > 0 && hideDuplicates
                ? 'All matching jobs are duplicates. Uncheck "Hide duplicates" to see them.'
                : 'Try adjusting your search or filters'}
            </p>
          </div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <SortableHeader
                  label="Job"
                  field="title"
                  currentSort={sortField}
                  currentOrder={sortOrder}
                  onSort={handleSort}
                />
                <SortableHeader
                  label="Location"
                  field="location"
                  currentSort={sortField}
                  currentOrder={sortOrder}
                  onSort={handleSort}
                />
                <SortableHeader
                  label="Salary"
                  field="salary_min"
                  currentSort={sortField}
                  currentOrder={sortOrder}
                  onSort={handleSort}
                />
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Type
                </th>
                <SortableHeader
                  label="Score"
                  field="fit_score"
                  currentSort={sortField}
                  currentOrder={sortOrder}
                  onSort={handleSort}
                />
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <SortableHeader
                  label="Added"
                  field="scraped_at"
                  currentSort={sortField}
                  currentOrder={sortOrder}
                  onSort={handleSort}
                />
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {sortedJobs.map((job) => (
                <JobRow key={job.id} job={job} onArchive={handleArchive} />
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-6">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-4 py-2 border border-gray-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
          >
            Previous
          </button>
          <span className="text-gray-600">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-4 py-2 border border-gray-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
