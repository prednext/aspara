/**
 * Delete API utility functions
 * Pure API calls without UI logic
 */

/**
 * Delete a project via API
 * @param {string} projectName - The project name to delete
 * @returns {Promise<object>} - Response data
 * @throws {Error} - API error
 */
export async function deleteProjectApi(projectName) {
  const response = await fetch(`/api/projects/${encodeURIComponent(projectName)}`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
    },
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Unknown error');
  }

  // Handle 204 No Content responses
  if (response.status === 204) {
    return { message: 'Project deleted successfully' };
  }

  return response.json();
}

/**
 * Delete a run via API
 * @param {string} projectName - The project name
 * @param {string} runName - The run name to delete
 * @returns {Promise<object>} - Response data
 * @throws {Error} - API error
 */
export async function deleteRunApi(projectName, runName) {
  const response = await fetch(`/api/projects/${encodeURIComponent(projectName)}/runs/${encodeURIComponent(runName)}`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
    },
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Unknown error');
  }

  // Handle 204 No Content responses
  if (response.status === 204) {
    return { message: 'Run deleted successfully' };
  }

  return response.json();
}
