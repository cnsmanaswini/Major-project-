import React, { useState, useEffect } from 'react'
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, RadialBarChart, RadialBar, Legend
} from 'recharts'
import { format } from 'date-fns'
import { Brain, TrendingUp, TrendingDown, AlertTriangle, Heart, Zap, MessageSquare } from 'lucide-react'
import { getAnalytics, getAgentStatus, getSuggestions } from '../../api/index.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { EmotionBadge, RiskBadge } from '../Common/Badges.jsx'
import clsx from 'clsx'

// ── Mock analytics for offline demo ─────────────────────────
const generateMockTimeline = () => {
  const now = Date.now()
  const emotions = ['joy', 'neutral', 'sadness', 'neutral', 'joy', 'fear', 'sadness', 'anger', 'neutral', 'joy', 'surprise', 'joy', 'sadness', 'neutral', 'joy']
  return emotions.map((emotion, i) => {
    const riskMap = { joy: 0.05, neutral: 0.12, sadness: 0.65, fear: 0.58, anger: 0.52, surprise: 0.1, disgust: 0.45 }
    const sentMap = { joy: 0.75, neutral: 0.02, sadness: -0.68, fear: -0.55, anger: -0.61, surprise: 0.3, disgust: -0.4 }
    return {
      timestamp: new Date(now - (14 - i) * 4 * 3600000).toISOString(),
      emotion,
      sentiment_score: sentMap[emotion] + (Math.random() - 0.5) * 0.1,
      risk_score: riskMap[emotion] + (Math.random() - 0.5) * 0.05,
      agent_action: riskMap[emotion] > 0.5 ? 'gentle_prompt' : 'monitor',
    }
  })
}

const MOCK_ANALYTICS = {
  user_id: 1,
  emotion_timeline: generateMockTimeline(),
  current_risk: 0.28,
  dominant_emotion: 'joy',
  average_sentiment: 0.14,
  intervention_count: 3,
}

const MOCK_SUGGESTIONS = [
  "Take a moment today to write down 3 things you're grateful for — even small ones. Research shows this practice rewires the brain toward positivity over time.",
  "When you feel overwhelmed, try the 5-4-3-2-1 grounding technique. It pulls attention to the present and interrupts the anxiety spiral.",
  "Remember: rest is productive. Scheduling deliberate downtime isn't laziness — it's what allows sustained output and creativity.",
]

const EMOTION_COLORS = {
  joy: '#f9c74f', sadness: '#577590', anger: '#f94144',
  fear: '#9b5de5', disgust: '#43aa8b', surprise: '#f8961e', neutral: '#6b7280',
}

// ── Metric Card ───────────────────────────────────────────────
function MetricCard({ icon: Icon, label, value, sub, color = 'text-brand-400' }) {
  return (
    <div className="card p-4 flex items-start gap-4">
      <div className={clsx('w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 bg-white/5', color)}>
        <Icon size={20} />
      </div>
      <div>
        <p className="text-xs text-gray-500 mb-0.5">{label}</p>
        <p className="text-xl font-bold text-white font-display">{value}</p>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

// ── Custom Tooltip ────────────────────────────────────────────
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload
  return (
    <div className="glass-dark rounded-xl px-3 py-2 text-xs space-y-1">
      <p className="text-gray-400">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(3) : p.value}
        </p>
      ))}
      {d?.emotion && <EmotionBadge emotion={d.emotion} size="sm" />}
    </div>
  )
}

// ── Emotion Distribution ──────────────────────────────────────
function EmotionDistribution({ timeline }) {
  const counts = {}
  timeline.forEach(p => { counts[p.emotion] = (counts[p.emotion] || 0) + 1 })
  const data = Object.entries(counts).map(([emotion, count]) => ({
    emotion, count, fill: EMOTION_COLORS[emotion] || '#6b7280'
  }))
  return (
    <div className="card p-5">
      <h3 className="text-sm font-semibold text-gray-300 mb-4">Emotion Distribution</h3>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis dataKey="emotion" tick={{ fill: '#6b7280', fontSize: 10 }} />
          <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
            {data.map((entry, index) => (
              <rect key={index} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function DashboardPage() {
  const { user } = useAuth()
  const [analytics, setAnalytics] = useState(null)
  const [agentStatus, setAgentStatus] = useState(null)
  const [suggestions, setSuggestions] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user) return
    Promise.all([
      getAnalytics(user.id).catch(() => ({ data: MOCK_ANALYTICS })),
      getAgentStatus(user.id).catch(() => ({ data: { risk_level: 'low', decision: 'monitor' } })),
      getSuggestions(user.id).catch(() => ({ data: { suggestions: MOCK_SUGGESTIONS } })),
    ]).then(([a, g, s]) => {
      const an = a.data
      if (!an.emotion_timeline?.length) an.emotion_timeline = MOCK_ANALYTICS.emotion_timeline
      setAnalytics(an)
      setAgentStatus(g.data)
      setSuggestions(s.data?.suggestions || MOCK_SUGGESTIONS)
    }).finally(() => setLoading(false))
  }, [user])

  if (loading || !analytics) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-8 space-y-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="card h-32 animate-pulse" />
        ))}
      </div>
    )
  }

  const timeline = analytics.emotion_timeline.map(p => ({
    ...p,
    time: format(new Date(p.timestamp), 'MMM d HH:mm'),
    sentiment_score: parseFloat(p.sentiment_score?.toFixed(3) || 0),
    risk_score: parseFloat(p.risk_score?.toFixed(3) || 0),
  }))

  const riskPct = Math.round(analytics.current_risk * 100)

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-display text-3xl text-white">Emotional Insights</h1>
          <p className="text-gray-500 text-sm mt-1">AI-powered mental health analytics dashboard</p>
        </div>
        <div className="flex items-center gap-2">
          <Brain size={18} className="text-brand-400 animate-float" />
          {agentStatus && <RiskBadge level={agentStatus.risk_level} />}
        </div>
      </div>

      {/* Metrics row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <MetricCard
          icon={Brain}
          label="Current Risk"
          value={`${riskPct}%`}
          sub={agentStatus?.risk_level}
          color={riskPct > 60 ? 'text-red-400' : riskPct > 35 ? 'text-yellow-400' : 'text-green-400'}
        />
        <MetricCard
          icon={Heart}
          label="Dominant Emotion"
          value={analytics.dominant_emotion}
          sub="Most frequent"
          color="text-pink-400"
        />
        <MetricCard
          icon={analytics.average_sentiment >= 0 ? TrendingUp : TrendingDown}
          label="Avg. Sentiment"
          value={analytics.average_sentiment >= 0 ? `+${analytics.average_sentiment.toFixed(2)}` : analytics.average_sentiment.toFixed(2)}
          sub="Last 50 posts"
          color={analytics.average_sentiment >= 0 ? 'text-green-400' : 'text-red-400'}
        />
        <MetricCard
          icon={AlertTriangle}
          label="Interventions"
          value={analytics.intervention_count}
          sub="AI actions taken"
          color="text-orange-400"
        />
      </div>

      {/* Sentiment trend */}
      <div className="card p-5 mb-4">
        <h3 className="text-sm font-semibold text-gray-300 mb-1">Sentiment Trend</h3>
        <p className="text-xs text-gray-500 mb-4">Emotional polarity over time (–1 = negative, +1 = positive)</p>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={timeline} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
            <defs>
              <linearGradient id="sentGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#c044eb" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#c044eb" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis dataKey="time" tick={{ fill: '#6b7280', fontSize: 9 }} interval="preserveStartEnd" />
            <YAxis domain={[-1, 1]} tick={{ fill: '#6b7280', fontSize: 9 }} />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="sentiment_score"
              stroke="#c044eb"
              strokeWidth={2}
              fill="url(#sentGrad)"
              dot={{ fill: '#c044eb', strokeWidth: 0, r: 3 }}
              name="Sentiment"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Risk progression */}
      <div className="card p-5 mb-4">
        <h3 className="text-sm font-semibold text-gray-300 mb-1">Risk Score Progression</h3>
        <p className="text-xs text-gray-500 mb-4">LSTM-predicted mental health risk (0 = low, 1 = critical)</p>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={timeline} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis dataKey="time" tick={{ fill: '#6b7280', fontSize: 9 }} interval="preserveStartEnd" />
            <YAxis domain={[0, 1]} tick={{ fill: '#6b7280', fontSize: 9 }} />
            <Tooltip content={<CustomTooltip />} />
            {/* Danger zone reference */}
            <Line type="monotone" dataKey={() => 0.6} stroke="rgba(249,65,68,0.2)" strokeDasharray="4 4" dot={false} name="High threshold" />
            <Line type="monotone" dataKey={() => 0.35} stroke="rgba(249,193,79,0.2)" strokeDasharray="4 4" dot={false} name="Moderate threshold" />
            <Line
              type="monotone"
              dataKey="risk_score"
              stroke="#f8961e"
              strokeWidth={2.5}
              dot={(props) => {
                const { cx, cy, payload } = props
                if (payload.risk_score > 0.6) return <circle key={cx} cx={cx} cy={cy} r={5} fill="#f94144" stroke="none" />
                return <circle key={cx} cx={cx} cy={cy} r={3} fill="#f8961e" stroke="none" />
              }}
              name="Risk Score"
            />
          </LineChart>
        </ResponsiveContainer>
        <div className="flex gap-4 mt-3 text-[10px] text-gray-500">
          <span className="flex items-center gap-1"><span className="w-3 h-px bg-red-400/50 inline-block" /> High risk (&gt;0.6)</span>
          <span className="flex items-center gap-1"><span className="w-3 h-px bg-yellow-400/50 inline-block" /> Moderate (&gt;0.35)</span>
        </div>
      </div>

      {/* Bottom row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <EmotionDistribution timeline={timeline} />

        {/* Agent decisions */}
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">Agentic AI Status</h3>
          {agentStatus && (
            <div className="space-y-3">
              {[
                { label: 'Risk Level', value: agentStatus.risk_level, icon: '⚡' },
                { label: 'Decision', value: agentStatus.decision, icon: '🤖' },
                { label: 'Intervention', value: agentStatus.intervention?.split('.')[0], icon: '💬' },
              ].map(({ label, value, icon }) => (
                <div key={label} className="flex items-start gap-2">
                  <span className="text-base">{icon}</span>
                  <div>
                    <p className="text-[10px] text-gray-500 uppercase tracking-widest">{label}</p>
                    <p className="text-xs text-gray-200">{value}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* RAG Suggestions */}
      <div className="card p-5">
        <div className="flex items-center gap-2 mb-4">
          <Zap size={16} className="text-brand-400" />
          <h3 className="text-sm font-semibold text-gray-300">Personalised Wellness Suggestions</h3>
          <span className="text-[10px] font-mono text-gray-600 ml-auto">RAG · FAISS · MiniLM</span>
        </div>
        <div className="space-y-3">
          {(suggestions.length ? suggestions : MOCK_SUGGESTIONS).map((s, i) => (
            <div key={i} className="flex gap-3 p-3 rounded-xl bg-white/5 border border-white/10">
              <span className="text-lg flex-shrink-0">{['💡', '🌱', '🧘'][i % 3]}</span>
              <p className="text-sm text-gray-300 leading-relaxed">{s}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}