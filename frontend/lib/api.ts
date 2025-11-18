/**
 * API client for Nova Ledger
 */
import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: `${API_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add authentication token to requests
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// API endpoints
export const api = {
  // Authentication
  auth: {
    login: (credentials: { username: string; password: string }) =>
      apiClient.post('/token/', credentials),
    refresh: (refreshToken: string) =>
      apiClient.post('/token/refresh/', { refresh: refreshToken }),
  },

  // Dashboard
  dashboard: {
    getMetrics: (params: { date_range?: string }) =>
      apiClient.get('/reporting/dashboard-metrics/', { params }),
    getChannelProfitability: (params: { period_type?: string }) =>
      apiClient.get('/reporting/channel-profitability/', { params }),
  },

  // Transactions
  transactions: {
    list: (params?: any) =>
      apiClient.get('/transactions/', { params }),
    get: (id: string) =>
      apiClient.get(`/transactions/${id}/`),
    create: (data: any) =>
      apiClient.post('/transactions/', data),
  },

  // Inventory
  inventory: {
    list: (params?: any) =>
      apiClient.get('/inventory/items/', { params }),
    get: (id: string) =>
      apiClient.get(`/inventory/items/${id}/`),
    updateCost: (id: string, data: any) =>
      apiClient.patch(`/inventory/items/${id}/`, data),
  },

  // Integrations
  integrations: {
    list: () =>
      apiClient.get('/integrations/'),
    connect: (type: string, credentials: any) =>
      apiClient.post('/integrations/connect/', { type, credentials }),
    sync: (id: string) =>
      apiClient.post(`/integrations/${id}/sync/`),
    getSyncLogs: (id: string) =>
      apiClient.get(`/integrations/${id}/sync-logs/`),
  },

  // ML Anomalies
  ml: {
    getAnomalies: (params?: any) =>
      apiClient.get('/ml/anomalies/', { params }),
    reviewAnomaly: (id: string, resolution: any) =>
      apiClient.post(`/ml/anomalies/${id}/review/`, resolution),
  },

  // Reports
  reports: {
    generate: (type: string, params: any) =>
      apiClient.post('/reporting/generate/', { type, ...params }),
    getProfitLoss: (params: { start_date: string; end_date: string; channel_id?: string }) =>
      apiClient.get('/reporting/profit-loss/', { params }),
    getBalanceSheet: (params: { as_of_date: string }) =>
      apiClient.get('/reporting/balance-sheet/', { params }),
  },

  // Revenue Recognition
  revenue: {
    getContracts: (params?: any) =>
      apiClient.get('/revenue/contracts/', { params }),
    getSchedules: (contractId: string) =>
      apiClient.get(`/revenue/contracts/${contractId}/schedules/`),
    getSaaSMetrics: (params: { metric_type?: string; start_date?: string }) =>
      apiClient.get('/revenue/saas-metrics/', { params }),
  },
}

export default api
