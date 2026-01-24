import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getJob, updateJob, tailorResume, generateCoverLetter, getDocuments, getApplications } from '../services/api'

const STATUS_OPTIONS = ['new', 'reviewed', 'applied', 'rejected', 'archived']
const TONE_OPTIONS = [
  { value: 'professional', label: 'Professional' },
  { value: 'enthusiastic', label: 'Enthusiastic' },
  { value: 'casual', label: 'Casual' },
]

export default function JobDetail() {
  const { id } = useParams()
  const [job, setJob] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [notes, setNotes] = useState('')

  // Document availability
  const [hasResume, setHasResume] = useState(false)

  // Generation state
  const [generatingResume, setGeneratingResume] = useState(false)
  const [generatingCover, setGeneratingCover] = useState(false)
  const [selectedTone, setSelectedTone] = useState('professional')

  // Generated content
  const [tailoredResume, setTailoredResume] = useState(null)
  const [resumeHighlights, setResumeHighlights] = useState([])
  const [coverLetter, setCoverLetter] = useState(null)
  const [coverTone, setCoverTone] = useState(null)

  // Copy feedback
  const [copiedResume, setCopiedResume] = useState(false)
  const [copiedCover, setCopiedCover] = useState(false)

  useEffect(() => {
    loadJob()
    checkDocuments()
    loadApplication()
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

  async function checkDocuments() {
    try {
      const docs = await getDocuments()
      setHasResume(docs.has_resume)
    } catch (err) {
      console.error('Failed to check documents:', err)
    }
  }

  async function loadApplication() {
    try {
      const apps = await getApplications(id)
      if (apps.length > 0) {
        const app = apps[0]
        if (app.tailored_resume) {
          setTailoredResume(app.tailored_resume)
          if (app.resume_highlights) {
            try {
              setResumeHighlights(JSON.parse(app.resume_highlights))
            } catch {
              setResumeHighlights([])
            }
          }
        }
        if (app.cover_letter) {
          setCoverLetter(app.cover_letter)
          setCoverTone(app.cover_tone)
        }
      }
    } catch (err) {
      console.error('Failed to load application:', err)
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
    if (!hasResume) {
      setError('Please create backend/profile/resume.md with your master resume first.')
      return
    }

    setGeneratingResume(true)
    setError(null)
    try {
      const result = await tailorResume(id)
      setTailoredResume(result.tailored_resume)
      setResumeHighlights(result.highlights || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setGeneratingResume(false)
    }
  }

  async function handleGenerateCover() {
    setGeneratingCover(true)
    setError(null)
    try {
      const result = await generateCoverLetter(id, { tone: selectedTone })
      setCoverLetter(result.cover_letter)
      setCoverTone(result.tone_used)
    } catch (err) {
      setError(err.message)
    } finally {
      setGeneratingCover(false)
    }
  }

  function handleCopyResume() {
    if (tailoredResume) {
      navigator.clipboard.writeText(tailoredResume)
      setCopiedResume(true)
      setTimeout(() => setCopiedResume(false), 2000)
    }
  }

  function handleCopyCover() {
    if (coverLetter) {
      navigator.clipboard.writeText(coverLetter)
      setCopiedCover(true)
      setTimeout(() => setCopiedCover(false), 2000)
    }
  }

  if (loading) {
    return <div className="p-8 text-center text-gray-500">Loading...</div>
  }

  if (error && !job) {
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

      {error && (
        <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          {error}
        </div>
      )}

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
              {(job.salary_min || job.salary_max) && (
                <span className="text-green-700 font-medium">
                  {job.salary_min && job.salary_max && job.salary_min !== job.salary_max
                    ? `$${job.salary_min.toLocaleString()} - $${job.salary_max.toLocaleString()}`
                    : `$${(job.salary_min || job.salary_max).toLocaleString()}`}
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
            disabled={generatingResume}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {generatingResume ? 'Tailoring...' : 'Tailor Resume'}
          </button>

          <div className="flex items-center gap-2">
            <select
              value={selectedTone}
              onChange={(e) => setSelectedTone(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
            >
              {TONE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <button
              onClick={handleGenerateCover}
              disabled={generatingCover}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              {generatingCover ? 'Generating...' : 'Generate Cover Letter'}
            </button>
          </div>

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

        {!hasResume && (
          <p className="mt-4 text-sm text-amber-600">
            Note: Create backend/profile/resume.md with your master resume to enable resume tailoring.
          </p>
        )}
      </div>

      {/* Tailored Resume */}
      {tailoredResume && (
        <div className="mt-6 bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium text-gray-900">Tailored Resume</h2>
            <button
              onClick={handleCopyResume}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              {copiedResume ? 'Copied!' : 'Copy to Clipboard'}
            </button>
          </div>

          {resumeHighlights.length > 0 && (
            <div className="mb-4 p-4 bg-blue-50 rounded-lg">
              <p className="text-sm font-medium text-blue-900 mb-2">Key Highlights for This Role:</p>
              <ul className="list-disc list-inside text-sm text-blue-800 space-y-1">
                {resumeHighlights.map((highlight, i) => (
                  <li key={i}>{highlight}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="prose max-w-none text-gray-700 whitespace-pre-wrap bg-gray-50 p-4 rounded-lg text-sm font-mono">
            {tailoredResume}
          </div>
        </div>
      )}

      {/* Cover Letter */}
      {coverLetter && (
        <div className="mt-6 bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-medium text-gray-900">Cover Letter</h2>
              {coverTone && (
                <span className="text-sm text-gray-500">Tone: {coverTone}</span>
              )}
            </div>
            <button
              onClick={handleCopyCover}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              {copiedCover ? 'Copied!' : 'Copy to Clipboard'}
            </button>
          </div>

          <div className="prose max-w-none text-gray-700 whitespace-pre-wrap">
            {coverLetter}
          </div>
        </div>
      )}

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
