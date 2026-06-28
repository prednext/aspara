/**
 * Delete API utility functions
 * Pure API calls without UI logic
 */

import { isDev } from '../dev-mode.js';

/**
 * Parse an error response, returning a meaningful message.
 * In dev mode, includes the raw response body for debugging.
 * @param {Response} response - The failed fetch response
 * @returns {Promise<string>} Error message
 */
async function parseErrorResponse(response) {
  let detail = 'Unknown error';
  let rawBody = null;
  try {
    const errorData = await response.json();
    detail = errorData.detail || detail;
  } catch {
    detail = `Server error: ${response.status}`;
    if (isDev()) {
      try {
        rawBody = await response.text();
      } catch {
        // ignore
      }
    }
  }
  if (isDev() && rawBody) {
    return `${detail} (raw: ${rawBody.slice(0, 200)})`;
  }
  return detail;
}

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
    throw new Error(await parseErrorResponse(response));
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
    throw new Error(await parseErrorResponse(response));
  }

  // Handle 204 No Content responses
  if (response.status === 204) {
    return { message: 'Run deleted successfully' };
  }

  return response.json();
}
