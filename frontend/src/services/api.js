/**
 * API service for communicating with the Canopy backend.
 */

const API_BASE = '/api'

/**
 * Make an API request.
 * @param {string} endpoint - API endpoint path
 * @param {object} options - Fetch options
 * @returns {Promise<any>} - Response data
 */
async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  }

  const response = await fetch(url, config)

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Request failed' }))
    throw new Error(error.detail || error.message || `HTTP ${response.status}`)
  }

  return response.json()
}

// Health check
export const checkHealth = () => request('/health')

// Jobs API
export const getJobs = (params = {}) => {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined) {
      searchParams.append(key, value)
    }
  })
  const query = searchParams.toString()
  return request(`/jobs${query ? `?${query}` : ''}`)
}

export const getJob = (id) => request(`/jobs/${id}`)

export const updateJob = (id, data) =>
  request(`/jobs/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })

export const deleteJob = (id) =>
  request(`/jobs/${id}`, {
    method: 'DELETE',
  })

export const searchJobs = (query, params = {}) => {
  const searchParams = new URLSearchParams({ q: query, ...params })
  return request(`/jobs/search?${searchParams.toString()}`)
}

// Search API
export const runSearch = () =>
  request('/search/run', {
    method: 'POST',
  })

export const getSearchRuns = (limit = 20) =>
  request(`/search/runs?limit=${limit}`)

export const getSources = () => request('/search/sources')

export const addSource = (data) =>
  request('/search/sources', {
    method: 'POST',
    body: JSON.stringify(data),
  })

// Applications API
export const getApplications = (jobId = null) => {
  const params = jobId ? `?job_id=${jobId}` : ''
  return request(`/applications${params}`)
}

export const createApplication = (data) =>
  request('/applications', {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const updateApplication = (id, data) =>
  request(`/applications/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })

export const tailorResume = (jobId) =>
  request(`/applications/${jobId}/tailor`, {
    method: 'POST',
  })

export const generateCoverLetter = (jobId) =>
  request(`/applications/${jobId}/cover`, {
    method: 'POST',
  })

// Profile API
export const getProfile = () => request('/profile')

export const updateProfile = (data) =>
  request('/profile', {
    method: 'PUT',
    body: JSON.stringify(data),
  })
