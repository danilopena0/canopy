import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { getJob, updateJob, tailorResume, generateCoverLetter } from '../services/api'

const STATUS_OPTIONS = ['new', 'reviewed', 'applied', 'rejected', 'archived']

export default function JobDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [job, setJob] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [notes, setNotes] = useState('')

  useEffect(() => {
    loadJob()
  }, [id])

  async function loadJob() {
    setLoading(true)
    try {
      const data = await getJob(id)
      setJob(data)
      setNotes(data.notes || '')
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleStatusChange(newStatus) {
    setSaving(true)
    try {
      const updated = await updateJob(id, { status: newStatus })
      setJob(updated)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleSaveNotes() {
    setSaving(true)
    try {
      const updated = await updateJob(id, { notes })
      setJob(updated)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleTailorResume() {
    try {
      const result = await tailorResume(id)
      alert(result.message)
    } catch (err) {
      alert(err.message)
    }
  }

  async function handleGenerateCover() {
    try {
      const result = await generateCoverLetter(id)
      alert(result.message)
    } catch (err) {
      alert(err.message)
    }
  }

  if (loading) {
    return <div className="p-8 text-center text-gray-500">Loading...</div>
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          {error}
        </div>
        <Link to="/jobs" className="mt-4 inline-block text-blue-600 hover:text-blue-800">
          &larr; Back to jobs
        </Link>
      </div>
    )
  }

  if (!job) {
    return null
  }

  return (
    <div>
      <Link to="/jobs" className="text-blue-600 hover:text-blue-800 text-sm">
        &larr; Back to jobs
      </Link>

      <div className="mt-4 bg-white rounded-lg shadow p-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{job.title}</h1>
            <p className="text-lg text-gray-600">{job.company}</p>
            <div className="mt-2 flex items-center gap-4 text-sm text-gray-500">
              {job.location && <span>{job.location}</span>}
              {job.work_type && (
                <span className="px-2 py-1 bg-gray-100 rounded">{job.work_type}</span>
              )}
              {job.salary_min && job.salary_max && (
                <span>
                  ${job.salary_min.toLocaleString()} - ${job.salary_max.toLocaleString()}
                </span>
              )}
            </div>
          </div>

          {job.fit_score !== null && (
            <div className="text-center">
              <div className="text-3xl font-bold text-blue-600">{job.fit_score.toFixed(0)}</div>
              <div className="text-sm text-gray-500">Fit Score</div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="mt-6 flex flex-wrap gap-3">
          <select
            value={job.status}
            onChange={(e) => handleStatusChange(e.target.value)}
            disabled={saving}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            {STATUS_OPTIONS.map((status) => (
              <option key={status} value={status}>
                {status.charAt(0).toUpperCase() + status.slice(1)}
              </option>
            ))}
          </select>

          <button
            onClick={handleTailorResume}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Tailor Resume
          </button>

          <button
            onClick={handleGenerateCover}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
          >
            Generate Cover Letter
          </button>

          {job.url && (
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              View Original &rarr;
            </a>
          )}
        </div>
      </div>

      {/* Fit Rationale */}
      {job.fit_rationale && (
        <div className="mt-6 bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-3">Fit Analysis</h2>
          <p className="text-gray-700 whitespace-pre-wrap">{job.fit_rationale}</p>
        </div>
      )}

      {/* Description */}
      {job.description && (
        <div className="mt-6 bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-3">Description</h2>
          <div className="prose max-w-none text-gray-700 whitespace-pre-wrap">
            {job.description}
          </div>
        </div>
      )}

      {/* Requirements */}
      {job.requirements && (
        <div className="mt-6 bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-3">Requirements</h2>
          <div className="prose max-w-none text-gray-700 whitespace-pre-wrap">
            {job.requirements}
          </div>
        </div>
      )}

      {/* Notes */}
      <div className="mt-6 bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-3">Notes</h2>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={4}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          placeholder="Add your notes here..."
        />
        <button
          onClick={handleSaveNotes}
          disabled={saving}
          className="mt-3 px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-900 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save Notes'}
        </button>
      </div>

      {/* Metadata */}
      <div className="mt-6 bg-gray-50 rounded-lg p-4 text-sm text-gray-500">
        <p>Source: {job.source}</p>
        <p>Added: {new Date(job.scraped_at).toLocaleString()}</p>
        {job.posted_date && <p>Posted: {new Date(job.posted_date).toLocaleDateString()}</p>}
      </div>
    </div>
  )
}
