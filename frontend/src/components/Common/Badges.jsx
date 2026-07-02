import React from 'react'
import clsx from 'clsx'

const EMOTION_EMOJI = {
  joy: '😊', sadness: '😢', anger: '😠',
  fear: '😨', disgust: '🤢', surprise: '😲', neutral: '😐',
}

export function EmotionBadge({ emotion, score, size = 'sm' }) {
  const emoji = EMOTION_EMOJI[emotion] || '😐'
  return (
    <span className={clsx(
      `emotion-${emotion} pill border`,
      size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-sm px-3 py-1'
    )}>
      {emoji} {emotion}
      {score !== undefined && (
        <span className="ml-1 opacity-60">{Math.round(score * 100)}%</span>
      )}
    </span>
  )
}

const RISK_CONFIG = {
  low:      { label: 'Low Risk',      dot: 'bg-green-400',  text: 'text-green-400' },
  moderate: { label: 'Moderate',      dot: 'bg-yellow-400', text: 'text-yellow-400' },
  high:     { label: 'High Risk',     dot: 'bg-orange-400', text: 'text-orange-400' },
  critical: { label: 'Critical',      dot: 'bg-red-400',    text: 'text-red-400' },
}

export function RiskBadge({ level }) {
  const cfg = RISK_CONFIG[level] || RISK_CONFIG.low
  return (
    <span className={clsx('flex items-center gap-1.5 text-xs font-medium', cfg.text)}>
      <span className={clsx('w-1.5 h-1.5 rounded-full animate-pulse', cfg.dot)} />
      {cfg.label}
    </span>
  )
}

export function SentimentBar({ score }) {
  // score: –1 to +1
  const pct = Math.round(((score + 1) / 2) * 100)
  const color = score > 0.2 ? 'bg-green-400' : score < -0.2 ? 'bg-red-400' : 'bg-gray-400'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1 bg-white/10 rounded-full overflow-hidden">
        <div
          className={clsx('h-full rounded-full transition-all duration-500', color)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-gray-500 w-8 text-right">{score > 0 ? '+' : ''}{score.toFixed(2)}</span>
    </div>
  )
}

export function Avatar({ src, name, size = 40 }) {
  return (
    <div className="story-ring flex-shrink-0" style={{ width: size + 4, height: size + 4 }}>
      <img
        src={src || `https://api.dicebear.com/9.x/avataaars/svg?seed=${name}`}
        alt={name}
        className="rounded-full bg-gray-800 object-cover"
        style={{ width: size, height: size }}
      />
    </div>
  )
}

export function InterventionBanner({ agentStatus }) {
  if (!agentStatus || agentStatus.risk_level === 'low') return null

  const configs = {
    moderate: { bg: 'bg-yellow-500/10 border-yellow-500/20', icon: '💛', title: 'Wellness Check' },
    high:     { bg: 'bg-orange-500/10 border-orange-500/20', icon: '🧡', title: 'Support Available' },
    critical: { bg: 'bg-red-500/10 border-red-500/20',       icon: '🆘', title: 'You\'re Not Alone' },
  }

  const cfg = configs[agentStatus.risk_level] || configs.moderate

  return (
    <div className={`rounded-2xl border p-4 mb-4 animate-slide-up ${cfg.bg}`}>
      <div className="flex items-start gap-3">
        <span className="text-2xl">{cfg.icon}</span>
        <div className="flex-1">
          <p className="font-semibold text-white text-sm mb-1">{cfg.title}</p>
          <p className="text-xs text-gray-300 leading-relaxed">{agentStatus.rag_suggestion}</p>
        </div>
      </div>
    </div>
  )
}
