import React, { useState } from 'react'
import { Heart, MessageCircle, Share2, Volume2, VolumeX, Play, Pause } from 'lucide-react'
import { EmotionBadge } from '../Common/Badges.jsx'
import clsx from 'clsx'

const MOCK_REELS = [
  {
    id: 1,
    thumbnail: 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400&q=80',
    author: { username: 'nature_vibes', display_name: 'Nature Vibes', avatar_url: 'https://api.dicebear.com/9.x/avataaars/svg?seed=nature' },
    caption: 'Morning meditation in the mountains 🏔️ Finding peace in stillness',
    likes: 12400, comments: 342,
    emotion: 'joy', emotion_score: 0.82, risk_score: 0.03,
    duration: '0:47',
  },
  {
    id: 2,
    thumbnail: 'https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=400&q=80',
    author: { username: 'forest_walk', display_name: 'Forest Walks', avatar_url: 'https://api.dicebear.com/9.x/avataaars/svg?seed=forest' },
    caption: 'Sometimes you just need to disappear into the trees 🌲',
    likes: 8900, comments: 156,
    emotion: 'neutral', emotion_score: 0.61, risk_score: 0.12,
    duration: '1:12',
  },
  {
    id: 3,
    thumbnail: 'https://images.unsplash.com/photo-1472214103451-9374bd1c798e?w=400&q=80',
    author: { username: 'sunset_chasers', display_name: 'Sunset Chasers', avatar_url: 'https://api.dicebear.com/9.x/avataaars/svg?seed=sunset' },
    caption: "Every sunset is a reminder that endings can be beautiful too 🌅",
    likes: 22100, comments: 891,
    emotion: 'surprise', emotion_score: 0.73, risk_score: 0.08,
    duration: '0:32',
  },
]

function ReelCard({ reel, isActive }) {
  const [liked, setLiked] = useState(false)
  const [likeCount, setLikeCount] = useState(reel.likes)
  const [playing, setPlaying] = useState(isActive)
  const [muted, setMuted] = useState(true)

  const handleLike = () => {
    setLiked(s => !s)
    setLikeCount(c => liked ? c - 1 : c + 1)
  }

  const fmtNum = n => n >= 1000 ? `${(n / 1000).toFixed(1)}k` : n

  return (
    <div className="relative h-[calc(100vh-120px)] min-h-[500px] rounded-2xl overflow-hidden bg-black flex-shrink-0 w-full max-w-sm mx-auto snap-start">
      {/* Background */}
      <img
        src={reel.thumbnail}
        alt=""
        className="absolute inset-0 w-full h-full object-cover"
      />
      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/10 to-black/20" />

      {/* Play overlay */}
      <button
        onClick={() => setPlaying(s => !s)}
        className="absolute inset-0 flex items-center justify-center"
      >
        {!playing && (
          <div className="w-16 h-16 rounded-full bg-black/50 backdrop-blur-sm flex items-center justify-center">
            <Play size={28} className="text-white ml-1" />
          </div>
        )}
      </button>

      {/* Duration badge */}
      <div className="absolute top-4 left-4">
        <span className="text-xs text-white/70 bg-black/40 backdrop-blur-sm px-2 py-1 rounded-lg font-mono">
          {reel.duration}
        </span>
      </div>

      {/* Mute button */}
      <button
        onClick={() => setMuted(s => !s)}
        className="absolute top-4 right-4 w-8 h-8 rounded-full bg-black/40 backdrop-blur-sm flex items-center justify-center"
      >
        {muted ? <VolumeX size={14} className="text-white" /> : <Volume2 size={14} className="text-white" />}
      </button>

      {/* Emotion badge */}
      <div className="absolute top-14 right-3">
        <EmotionBadge emotion={reel.emotion} />
      </div>

      {/* Right action buttons */}
      <div className="absolute right-3 bottom-24 flex flex-col gap-4 items-center">
        <button onClick={handleLike} className="flex flex-col items-center gap-1">
          <div className={clsx(
            'w-10 h-10 rounded-full bg-black/40 backdrop-blur-sm flex items-center justify-center transition-all',
            liked ? 'text-red-400' : 'text-white'
          )}>
            <Heart size={20} fill={liked ? 'currentColor' : 'none'} />
          </div>
          <span className="text-white text-xs">{fmtNum(likeCount)}</span>
        </button>
        <button className="flex flex-col items-center gap-1">
          <div className="w-10 h-10 rounded-full bg-black/40 backdrop-blur-sm flex items-center justify-center text-white">
            <MessageCircle size={20} />
          </div>
          <span className="text-white text-xs">{fmtNum(reel.comments)}</span>
        </button>
        <button className="flex flex-col items-center gap-1">
          <div className="w-10 h-10 rounded-full bg-black/40 backdrop-blur-sm flex items-center justify-center text-white">
            <Share2 size={20} />
          </div>
          <span className="text-white text-xs">Share</span>
        </button>
      </div>

      {/* Bottom info */}
      <div className="absolute bottom-0 left-0 right-0 p-4">
        <div className="flex items-center gap-2 mb-2">
          <img
            src={reel.author.avatar_url}
            alt=""
            className="w-8 h-8 rounded-full border border-white/30"
          />
          <span className="text-white font-medium text-sm">@{reel.author.username}</span>
          <button className="pill border border-white/30 text-white text-xs px-2 py-0.5">Follow</button>
        </div>
        <p className="text-white text-sm leading-relaxed line-clamp-2">{reel.caption}</p>

        {/* Progress bar */}
        <div className="mt-3 h-0.5 bg-white/20 rounded-full overflow-hidden">
          <div
            className="h-full bg-white/70 rounded-full transition-all duration-300"
            style={{ width: playing ? '65%' : '0%' }}
          />
        </div>
      </div>
    </div>
  )
}

export default function ReelsPage() {
  const [activeIndex, setActiveIndex] = useState(0)

  return (
    <div className="max-w-sm mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-display text-2xl text-white">Reels</h1>
        <span className="text-xs text-gray-500 font-mono">AI-filtered · wellness-safe</span>
      </div>

      <div className="space-y-4 snap-y snap-mandatory overflow-y-auto" style={{ maxHeight: 'calc(100vh - 140px)' }}>
        {MOCK_REELS.map((reel, i) => (
          <div key={reel.id} onClick={() => setActiveIndex(i)}>
            <ReelCard reel={reel} isActive={activeIndex === i} />
          </div>
        ))}
      </div>
    </div>
  )
}
