import { useState, useEffect } from 'react'
import { getProfile, updateProfile, getSources, addSource } from '../services/api'

function ProfileSection() {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadProfile()
  }, [])

  async function loadProfile() {
    try {
      const data = await getProfile()
      setProfile(data)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    setSaving(true)
    try {
      await updateProfile(profile)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="p-4 text-gray-500">Loading profile...</div>
  }

  if (!profile) {
    return <div className="p-4 text-red-600">{error || 'Failed to load profile'}</div>
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-lg font-medium text-gray-900 mb-4">Profile</h2>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
          <input
            type="text"
            value={profile.name || ''}
            onChange={(e) => setProfile({ ...profile, name: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Target Titles (comma-separated)
          </label>
          <input
            type="text"
            value={profile.target_titles?.join(', ') || ''}
            onChange={(e) =>
              setProfile({
                ...profile,
                target_titles: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
              })
            }
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Years of Experience
          </label>
          <input
            type="number"
            value={profile.experience_years || 0}
            onChange={(e) =>
              setProfile({ ...profile, experience_years: parseInt(e.target.value) || 0 })
            }
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Preferred Locations (comma-separated)
          </label>
          <input
            type="text"
            value={profile.locations?.join(', ') || ''}
            onChange={(e) =>
              setProfile({
                ...profile,
                locations: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
              })
            }
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Work Types</label>
          <div className="flex gap-4">
            {['remote', 'hybrid', 'onsite'].map((type) => (
              <label key={type} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={profile.work_types?.includes(type) || false}
                  onChange={(e) => {
                    const types = profile.work_types || []
                    setProfile({
                      ...profile,
                      work_types: e.target.checked
                        ? [...types, type]
                        : types.filter((t) => t !== type),
                    })
                  }}
                  className="rounded border-gray-300"
                />
                <span className="text-sm text-gray-700 capitalize">{type}</span>
              </label>
            ))}
          </div>
        </div>

        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save Profile'}
        </button>
      </div>
    </div>
  )
}

function SourcesSection() {
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showAdd, setShowAdd] = useState(false)
  const [newSource, setNewSource] = useState({
    company_name: '',
    careers_url: '',
    category: '',
  })

  useEffect(() => {
    loadSources()
  }, [])

  async function loadSources() {
    try {
      const data = await getSources()
      setSources(data)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleAddSource(e) {
    e.preventDefault()
    try {
      await addSource(newSource)
      setNewSource({ company_name: '', careers_url: '', category: '' })
      setShowAdd(false)
      loadSources()
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading) {
    return <div className="p-4 text-gray-500">Loading sources...</div>
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-medium text-gray-900">Job Sources</h2>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="text-sm text-blue-600 hover:text-blue-800"
        >
          {showAdd ? 'Cancel' : '+ Add Source'}
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      {showAdd && (
        <form onSubmit={handleAddSource} className="mb-6 p-4 bg-gray-50 rounded-lg">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <input
              type="text"
              placeholder="Company Name"
              value={newSource.company_name}
              onChange={(e) => setNewSource({ ...newSource, company_name: e.target.value })}
              required
              className="px-3 py-2 border border-gray-300 rounded-lg"
            />
            <input
              type="url"
              placeholder="Careers URL"
              value={newSource.careers_url}
              onChange={(e) => setNewSource({ ...newSource, careers_url: e.target.value })}
              required
              className="px-3 py-2 border border-gray-300 rounded-lg"
            />
            <input
              type="text"
              placeholder="Category (e.g., tech, defense)"
              value={newSource.category}
              onChange={(e) => setNewSource({ ...newSource, category: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-lg"
            />
          </div>
          <button
            type="submit"
            className="mt-3 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
          >
            Add Source
          </button>
        </form>
      )}

      {sources.length === 0 ? (
        <p className="text-gray-500 text-sm">No sources configured yet.</p>
      ) : (
        <div className="space-y-2">
          {sources.map((source) => (
            <div
              key={source.id}
              className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
            >
              <div>
                <p className="font-medium text-gray-900">{source.company_name}</p>
                <p className="text-sm text-gray-500">{source.careers_url}</p>
              </div>
              <div className="flex items-center gap-2">
                {source.category && (
                  <span className="px-2 py-1 bg-gray-200 text-gray-700 text-xs rounded">
                    {source.category}
                  </span>
                )}
                <span
                  className={`px-2 py-1 text-xs rounded ${
                    source.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                  }`}
                >
                  {source.enabled ? 'Enabled' : 'Disabled'}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Settings() {
  return (
    <div>
      <h1 className="text-3xl font-bold text-gray-900 mb-6">Settings</h1>

      <div className="space-y-6">
        <ProfileSection />
        <SourcesSection />
      </div>
    </div>
  )
}
