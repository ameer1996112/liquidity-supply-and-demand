/**
 * API Configuration
 *
 * Centralized configuration for API endpoints with environment-aware URL selection.
 * Falls back to the frontend-hosted /backend proxy when no public backend URL
 * was injected at build time.
 */

const rawApiUrl = process.env.NEXT_PUBLIC_API_URL || '/backend';

// Remove trailing slash to prevent double slashes in URLs
export const API_BASE_URL = rawApiUrl.endsWith('/')
  ? rawApiUrl.slice(0, -1)
  : rawApiUrl;

/**
 * Get the current environment
 */
export const getEnvironment = (): 'development' | 'production' => {
  return process.env.NODE_ENV === 'production' ? 'production' : 'development';
};

/**
 * Check if we're running on Railway
 */
export const isRailwayDeployment = (): boolean => {
  return API_BASE_URL.includes('railway.app') || API_BASE_URL.startsWith('/backend');
};

/**
 * Get API URL with optional path
 */
export const getApiUrl = (path: string = ''): string => {
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${cleanPath}`;
};

/**
 * Configuration object for easy access
 */
export const config = {
  apiBaseUrl: API_BASE_URL,
  environment: getEnvironment(),
  isRailway: isRailwayDeployment(),
  isDevelopment: getEnvironment() === 'development',
  isProduction: getEnvironment() === 'production',
} as const;

// Log configuration in development
if (config.isDevelopment) {
  console.log('🔧 API Configuration:', {
    baseUrl: config.apiBaseUrl,
    environment: config.environment,
    isRailway: config.isRailway,
  });
}
