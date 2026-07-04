import React, { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { Grid, List, Settings, Camera, UserPlus, UserMinus, MessageCircle, LogOut } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import clsx from 'clsx'
import { useAuth } from '../../context/AuthContext.jsx'
import { EmotionBadge, SentimentBar, RiskBadge } from '../Common/Badges.jsx'

export default function ProfilePage() {
  const { username }            = useParams()
  const { user, api, logout }           = useAuth()
  const [profile, setProfile]   = useState(null)
  const [posts, setPosts]       = useState([])
  const [analytics, setAnalytics] = useState(null)
  const [agentStatus, setAgentStatus] = useState(null)
  const [viewMode, setViewMode] = useState('grid')
  const [selected, setSelected] = useState(null)
  const [loading, setLoading]   = useState(true)
  const [editing, setEditing]   = useState(false)
  const [editForm, setEditForm] = useState({ display_name: '', bio: '' })
  const fileRef = useRef()

  const isOwn = !username || username === user?.username

  useEffect(() => {
    const target = username || user?.username
    if (!target) return

    setLoading(true)
    Promise.all([
      isOwn
        ? api.get('/users/me')
        : api.get(`/users/${target}`),
      api.get(`/posts/user/${isOwn ? user?.id : 0}`).catch(() => ({ data: [] })),
      isOwn ? api.get(`/analytics/${user?.id}`).catch(() => ({ data: null })) : Promise.resolve({ data: null }),
      isOwn ? api.get(`/agents/status/${user?.id}`).catch(() => ({ data: null })) : Promise.resolve({ data: null }),
    ]).then(([profileRes, postsRes, analyticsRes, agentRes]) => {
      setProfile(profileRes.data)
      setPosts(postsRes.data || [])
      setAnalytics(analyticsRes.data)
      setAgentStatus(agentRes.data)
      setEditForm({
        display_name: profileRes.data.display_name || '',
        bio: profileRes.data.bio || '',
      })
    }).finally(() => setLoading(false))
  }, [username, user])

  const handleFollow = async () => {
    if (!profile) return
    try {
      const res = await api.post(`/users/${profile.id}/follow`)
      setProfile(prev => ({
        ...prev,
        is_following: !prev.is_following,
        followers_count: res.data.followers_count,
      }))
    } catch {}
  }

  const handleAvatarUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await api.post('/users/me/avatar', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setProfile(prev => ({ ...prev, avatar_url: res.data.avatar_url }))
    } catch {}
  }

  const handleEditSave = async () => {
    try {
      const formData = new FormData()
      formData.append('display_name', editForm.display_name)
      formData.append('bio', editForm.bio)
      const res = await api.put('/users/me', formData)
      setProfile(prev => ({ ...prev, ...res.data }))
      setEditing(false)
    } catch {}
  }

  if (loading) return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="w-8 h-8 border-2 border-brand-500/30 border-t-brand-500 rounded-full animate-spin" />
    </div>
  )

  if (!profile) return (
    <div className="flex items-center justify-center min-h-screen">
      <p className="text-gray-500">User not found</p>
    </div>
  )

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      {/* Profile Header */}
      <div className="card p-6 mb-6">
        <div className="flex items-start gap-5">
          {/* Avatar */}
          <div className="relative flex-shrink-0">
            <div className="story-ring">
              <img
                src={profile.avatar_url || `https://api.dicebear.com/9.x/avataaars/svg?seed=${profile.username}`}
                alt={profile.display_name}
                className="w-20 h-20 rounded-full bg-gray-800 object-cover"
              />
            </div>
            {isOwn && (
              <>
                <button
                  onClick={() => fileRef.current.click()}
                  className="absolute bottom-0 right-0 w-7 h-7 rounded-full bg-brand-500
                             flex items-center justify-center border-2 border-black
                             hover:bg-brand-400 transition-all"
                >
                  <Camera size={12} className="text-white" />
                </button>
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/*"
                  onChange={handleAvatarUpload}
                  className="hidden"
                />
              </>
            )}
          </div>

          {/* Info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div>
                {editing ? (
                  <input
                    value={editForm.display_name}
                    onChange={e => setEditForm(f => ({ ...f, display_name: e.target.value }))}
                    className="input-field text-lg font-display mb-1"
                  />
                ) : (
                  <h2 className="font-display text-2xl text-white">{profile.display_name}</h2>
                )}
                <p className="text-gray-500 text-sm">@{profile.username}</p>
              </div>

              {isOwn ? (
                <div className="flex gap-2">
                  {editing ? (
                    <>
                      <button onClick={handleEditSave} className="btn-primary text-xs py-1.5 px-3">Save</button>
                      <button onClick={() => setEditing(false)} className="btn-ghost text-xs py-1.5 px-3">Cancel</button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => setEditing(true)}
                        className="btn-ghost text-sm flex items-center gap-1.5"
                      >
                        <Settings size={14} /> Edit
                      </button>
                      <button
                        onClick={logout}
                        className="btn-ghost text-sm flex items-center gap-1.5 text-red-400 hover:text-red-300"
                      >
                        <LogOut size={14} /> Logout
                      </button>
                    </>
                  )}
                </div>
              ) : (
                <div className="flex gap-2">
                  <button
                    onClick={handleFollow}
                    className={clsx(
                      'flex items-center gap-1.5 text-sm px-4 py-2 rounded-xl transition-all',
                      profile.is_following
                        ? 'bg-white/10 text-gray-300 hover:bg-red-500/20 hover:text-red-400'
                        : 'btn-primary'
                    )}
                  >
                    {profile.is_following
                      ? <><UserMinus size={14} /> Unfollow</>
                      : <><UserPlus size={14} /> Follow</>
                    }
                  </button>
                  <button className="btn-ghost text-sm flex items-center gap-1.5 px-3">
                    <MessageCircle size={14} />
                  </button>
                </div>
              )}
            </div>

            {/* Bio */}
            {editing ? (
              <textarea
                value={editForm.bio}
                onChange={e => setEditForm(f => ({ ...f, bio: e.target.value }))}
                placeholder="Write a bio..."
                rows={2}
                className="input-field text-sm mt-2 resize-none w-full"
              />
            ) : (
              profile.bio && (
                <p className="text-gray-300 text-sm mt-2 leading-relaxed">{profile.bio}</p>
              )
            )}

            {/* Stats */}
            <div className="flex gap-6 mt-4">
              {[
                { label: 'Posts',     value: profile.posts_count || posts.length },
                { label: 'Followers', value: profile.followers_count || 0 },
                { label: 'Following', value: profile.following_count || 0 },
              ].map(({ label, value }) => (
                <div key={label} className="text-center">
                  <p className="font-bold text-white font-display text-lg">{value}</p>
                  <p className="text-xs text-gray-500">{label}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Wellness strip — only shown to profile owner */}
        {isOwn && agentStatus && (
          <div className="mt-5 pt-4 border-t border-white/10 flex items-center gap-4 flex-wrap">
            <RiskBadge level={agentStatus.risk_level} />
            {analytics && (
              <div className="flex-1 min-w-32">
                <div className="text-xs text-gray-500 mb-1">Avg sentiment</div>
                <SentimentBar score={analytics.average_sentiment || 0} />
              </div>
            )}
            {analytics?.dominant_emotion && (
              <EmotionBadge emotion={analytics.dominant_emotion} />
            )}
          </div>
        )}
      </div>

      {/* View Toggle */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-widest">Posts</h3>
        <div className="flex gap-1 p-1 bg-white/5 rounded-xl">
          <button
            onClick={() => setViewMode('grid')}
            className={clsx('p-1.5 rounded-lg transition-all',
              viewMode === 'grid' ? 'bg-brand-500/30 text-brand-300' : 'text-gray-500')}
          >
            <Grid size={16} />
          </button>
          <button
            onClick={() => setViewMode('list')}
            className={clsx('p-1.5 rounded-lg transition-all',
              viewMode === 'list' ? 'bg-brand-500/30 text-brand-300' : 'text-gray-500')}
          >
            <List size={16} />
          </button>
        </div>
      </div>

      {/* Posts Grid */}
      {viewMode === 'grid' ? (
        <>
          <div className="grid grid-cols-3 gap-1">
            {posts.map(post => (
              <button
                key={post.id}
                onClick={() => setSelected(post)}
                className="relative aspect-square overflow-hidden rounded-lg bg-white/5 group"
              >
                {post.image_url ? (
                  <img
                    src={post.image_url}
                    alt=""
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    loading="lazy"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center p-2 bg-white/3">
                    <p className="text-[10px] text-gray-400 text-center line-clamp-4 leading-relaxed">
                      {post.content}
                    </p>
                  </div>
                )}
                <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100
                                transition-opacity flex items-center justify-center gap-3">
                  <span className="flex items-center gap-1 text-white text-xs font-medium">
                    ❤️ {post.likes_count}
                  </span>
                  <span className="flex items-center gap-1 text-white text-xs font-medium">
                    💬 {post.comments_count}
                  </span>
                </div>
                {/* Risk dot */}
                <div className={clsx(
                  'absolute top-1 right-1 w-2 h-2 rounded-full',
                  post.risk_score > 0.5 ? 'bg-red-400'
                  : post.risk_score > 0.3 ? 'bg-yellow-400'
                  : 'bg-green-400'
                )} />
              </button>
            ))}
          </div>

          {posts.length === 0 && (
            <div className="text-center py-12">
              <p className="text-gray-500 text-sm">No posts yet</p>
            </div>
          )}
        </>
      ) : (
        <div className="space-y-3">
          {posts.map(post => (
            <div key={post.id} className="card p-4 flex gap-4">
              {post.image_url && (
                <img
                  src={post.image_url}
                  alt=""
                  className="w-16 h-16 rounded-xl object-cover flex-shrink-0"
                />
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-200 leading-relaxed line-clamp-2 mb-2">
                  {post.content}
                </p>
                <div className="flex items-center gap-2 flex-wrap">
                  <EmotionBadge emotion={post.emotion} size="sm" />
                  {post.sarcasm && (
                    <span className="text-[10px] text-purple-300">🎭 sarcasm</span>
                  )}
                  <span className="ml-auto flex items-center gap-2 text-xs text-gray-500">
                    <span>❤️ {post.likes_count}</span>
                    <span>💬 {post.comments_count}</span>
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Post detail modal */}
      {selected && (
        <div
          className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center
                     justify-center z-50 p-4 animate-fade-in"
          onClick={() => setSelected(null)}
        >
          <div
            className="card max-w-md w-full p-5 space-y-4 animate-slide-up"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <EmotionBadge emotion={selected.emotion} score={selected.emotion_score} />
              {selected.sarcasm && (
                <span className="text-xs text-purple-300 bg-purple-500/15 px-2 py-1 rounded-lg">
                  🎭 sarcasm detected
                </span>
              )}
            </div>
            {selected.image_url && (
              <img
                src={selected.image_url}
                alt=""
                className="w-full rounded-xl object-cover max-h-48"
              />
            )}
            <p className="text-sm text-gray-200 leading-relaxed">{selected.content}</p>
            <div className="space-y-2 pt-2 border-t border-white/10">
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-500">Sentiment</span>
                <div className="w-40">
                  <SentimentBar score={selected.sentiment_score || 0} />
                </div>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-500">Risk Score</span>
                <span className={clsx(
                  'font-mono',
                  selected.risk_score > 0.6 ? 'text-red-400'
                  : selected.risk_score > 0.35 ? 'text-yellow-400'
                  : 'text-green-400'
                )}>
                  {((selected.risk_score || 0) * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-500">Posted</span>
                <span className="text-gray-400">
                  {formatDistanceToNow(new Date(selected.created_at), { addSuffix: true })}
                </span>
              </div>
            </div>
            <button
              onClick={() => setSelected(null)}
              className="btn-ghost w-full text-sm"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  )
}