'use client'

import { useState } from 'use Query
import { useQuery } from '@tanstack/react-query'
import {
  DollarSign,
  TrendingUp,
  ShoppingCart,
  AlertCircle,
  ArrowUp,
  ArrowDown
} from 'lucide-react'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts'

export default function DashboardPage() {
  const [dateRange, setDateRange] = useState('30d')

  // Fetch dashboard metrics
  const { data: metrics, isLoading } = useQuery({
    queryKey: ['dashboard-metrics', dateRange],
    queryFn: async () => {
      // This would call the API: /api/dashboard/metrics
      return mockMetrics
    }
  })

  if (isLoading) {
    return <div className="p-8">Loading...</div>
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="px-8 py-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
              <p className="text-gray-600 mt-1">Financial Intelligence Overview</p>
            </div>
            <div className="flex space-x-4">
              <select
                value={dateRange}
                onChange={(e) => setDateRange(e.target.value)}
                className="px-4 py-2 border rounded-lg"
              >
                <option value="7d">Last 7 Days</option>
                <option value="30d">Last 30 Days</option>
                <option value="90d">Last 90 Days</option>
                <option value="12m">Last 12 Months</option>
              </select>
            </div>
          </div>
        </div>
      </header>

      <main className="p-8">
        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <MetricCard
            title="Total Revenue"
            value="$284,567"
            change={12.5}
            icon={<DollarSign className="w-8 h-8" />}
            positive={true}
          />
          <MetricCard
            title="Gross Profit"
            value="$142,890"
            change={8.2}
            icon={<TrendingUp className="w-8 h-8" />}
            positive={true}
          />
          <MetricCard
            title="Orders"
            value="1,247"
            change={-3.1}
            icon={<ShoppingCart className="w-8 h-8" />}
            positive={false}
          />
          <MetricCard
            title="Anomalies"
            value="5"
            change={null}
            icon={<AlertCircle className="w-8 h-8" />}
            positive={null}
          />
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Revenue Trend */}
          <div className="card">
            <h3 className="text-lg font-semibold mb-4">Revenue Trend</h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={mockRevenueData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="revenue" stroke="#0ea5e9" strokeWidth={2} />
                <Line type="monotone" dataKey="profit" stroke="#10b981" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Channel Profitability */}
          <div className="card">
            <h3 className="text-lg font-semibold mb-4">Channel Profitability</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={mockChannelData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="channel" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="revenue" fill="#0ea5e9" />
                <Bar dataKey="profit" fill="#10b981" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Channel Details Table */}
        <div className="card">
          <h3 className="text-lg font-semibold mb-4">Channel Performance</h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Channel
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Revenue
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    COGS
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Fees
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Net Profit
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Margin %
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {mockChannelDetails.map((channel) => (
                  <tr key={channel.name} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap font-medium">{channel.name}</td>
                    <td className="px-6 py-4 whitespace-nowrap">${channel.revenue.toLocaleString()}</td>
                    <td className="px-6 py-4 whitespace-nowrap">${channel.cogs.toLocaleString()}</td>
                    <td className="px-6 py-4 whitespace-nowrap">${channel.fees.toLocaleString()}</td>
                    <td className="px-6 py-4 whitespace-nowrap font-semibold text-green-600">
                      ${channel.profit.toLocaleString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 rounded ${channel.margin >= 20 ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}`}>
                        {channel.margin}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* AI Anomalies */}
        <div className="card mt-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center">
            <AlertCircle className="w-5 h-5 mr-2 text-red-500" />
            AI-Detected Anomalies
          </h3>
          <div className="space-y-4">
            {mockAnomalies.map((anomaly) => (
              <div key={anomaly.id} className="border-l-4 border-red-500 bg-red-50 p-4">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="font-semibold text-red-800">{anomaly.title}</p>
                    <p className="text-sm text-red-600 mt-1">{anomaly.description}</p>
                    <p className="text-xs text-gray-500 mt-2">
                      Detected: {anomaly.detectedAt} • Confidence: {anomaly.confidence}%
                    </p>
                  </div>
                  <button className="text-sm px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700">
                    Review
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  )
}

function MetricCard({
  title,
  value,
  change,
  icon,
  positive
}: {
  title: string
  value: string
  change: number | null
  icon: React.ReactNode
  positive: boolean | null
}) {
  return (
    <div className="metric-card">
      <div className="flex justify-between items-start mb-2">
        <div className="text-gray-600 text-sm font-medium">{title}</div>
        <div className="text-primary-600">{icon}</div>
      </div>
      <div className="text-3xl font-bold text-gray-900 mb-2">{value}</div>
      {change !== null && (
        <div className={`flex items-center text-sm ${positive ? 'text-green-600' : 'text-red-600'}`}>
          {positive ? <ArrowUp className="w-4 h-4 mr-1" /> : <ArrowDown className="w-4 h-4 mr-1" />}
          <span>{Math.abs(change)}% vs last period</span>
        </div>
      )}
    </div>
  )
}

// Mock data
const mockMetrics = {
  revenue: 284567,
  profit: 142890,
  orders: 1247,
  anomalies: 5
}

const mockRevenueData = [
  { date: 'Jan', revenue: 45000, profit: 22000 },
  { date: 'Feb', revenue: 52000, profit: 26000 },
  { date: 'Mar', revenue: 48000, profit: 24000 },
  { date: 'Apr', revenue: 61000, profit: 30000 },
  { date: 'May', revenue: 55000, profit: 27500 },
  { date: 'Jun', revenue: 67000, profit: 33500 },
]

const mockChannelData = [
  { channel: 'Shopify', revenue: 95000, profit: 47500 },
  { channel: 'Amazon', revenue: 82000, profit: 32800 },
  { channel: 'eBay', revenue: 43000, profit: 21500 },
  { channel: 'Direct', revenue: 64567, profit: 40890 },
]

const mockChannelDetails = [
  { name: 'Shopify', revenue: 95000, cogs: 38000, fees: 9500, profit: 47500, margin: 50.0 },
  { name: 'Amazon', revenue: 82000, cogs: 41000, fees: 8200, profit: 32800, margin: 40.0 },
  { name: 'eBay', revenue: 43000, cogs: 17200, fees: 4300, profit: 21500, margin: 50.0 },
  { name: 'Direct Sales', revenue: 64567, cogs: 19370, fees: 4207, profit: 40890, margin: 63.3 },
]

const mockAnomalies = [
  {
    id: 1,
    title: 'Unusual Fee Amount Detected',
    description: 'Stripe processing fee for transaction #12345 is 4.2% vs expected 2.9%',
    detectedAt: '2 hours ago',
    confidence: 95
  },
  {
    id: 2,
    title: 'Potential Duplicate Transaction',
    description: 'Transaction #12348 matches #12342 (same amount, customer, timestamp)',
    detectedAt: '5 hours ago',
    confidence: 87
  },
  {
    id: 3,
    title: 'Tax Calculation Mismatch',
    description: 'Order #9876 calculated tax is $12.50 but expected $15.75 for CA',
    detectedAt: '1 day ago',
    confidence: 92
  },
]
