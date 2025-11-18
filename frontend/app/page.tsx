'use client'

import Link from 'next/link'
import { ArrowRight, BarChart3, TrendingUp, Shield, Zap } from 'lucide-react'

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Navigation */}
      <nav className="bg-white shadow-sm">
        <div className="container mx-auto px-6 py-4">
          <div className="flex justify-between items-center">
            <div className="text-2xl font-bold text-primary-600">Nova Ledger</div>
            <div className="space-x-4">
              <Link href="/login" className="text-gray-600 hover:text-primary-600">
                Login
              </Link>
              <Link href="/signup" className="btn-primary">
                Get Started
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="container mx-auto px-6 py-20">
        <div className="text-center">
          <h1 className="text-5xl md:text-6xl font-bold text-gray-900 mb-6">
            Intelligent Accounting
            <span className="text-primary-600"> Automation</span>
          </h1>
          <p className="text-xl text-gray-600 mb-8 max-w-3xl mx-auto">
            The most accurate, compliant, and intelligent accounting automation layer
            for high-growth, multi-channel e-commerce and SaaS businesses.
          </p>
          <div className="flex justify-center space-x-4">
            <Link href="/dashboard" className="btn-primary inline-flex items-center text-lg px-8 py-3">
              View Dashboard
              <ArrowRight className="ml-2 w-5 h-5" />
            </Link>
            <Link href="/demo" className="btn-secondary inline-flex items-center text-lg px-8 py-3">
              Watch Demo
            </Link>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="container mx-auto px-6 py-20">
        <h2 className="text-3xl font-bold text-center mb-12">Why Nova Ledger?</h2>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
          <FeatureCard
            icon={<BarChart3 className="w-10 h-10 text-primary-600" />}
            title="Channel Profitability"
            description="Automatic P&L by sales channel with accurate fee allocation"
          />
          <FeatureCard
            icon={<TrendingUp className="w-10 h-10 text-primary-600" />}
            title="Advanced COGS"
            description="Perpetual inventory with landed cost tracking"
          />
          <FeatureCard
            icon={<Shield className="w-10 h-10 text-primary-600" />}
            title="AI Error Detection"
            description="Machine learning spots anomalies before reconciliation"
          />
          <FeatureCard
            icon={<Zap className="w-10 h-10 text-primary-600" />}
            title="Real-Time Sync"
            description="Multi-platform integration with 20+ systems"
          />
        </div>
      </section>

      {/* CTA Section */}
      <section className="bg-primary-600 py-16">
        <div className="container mx-auto px-6 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Ready to transform your accounting?
          </h2>
          <p className="text-xl text-primary-100 mb-8">
            Join hundreds of high-growth businesses using Nova Ledger
          </p>
          <Link href="/signup" className="bg-white text-primary-600 px-8 py-3 rounded-lg font-semibold hover:bg-gray-100 transition-colors inline-block">
            Start Free Trial
          </Link>
        </div>
      </section>
    </div>
  )
}

function FeatureCard({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <div className="card text-center hover:shadow-xl transition-shadow">
      <div className="flex justify-center mb-4">{icon}</div>
      <h3 className="text-xl font-semibold mb-2">{title}</h3>
      <p className="text-gray-600">{description}</p>
    </div>
  )
}
