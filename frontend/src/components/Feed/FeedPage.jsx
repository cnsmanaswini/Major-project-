import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Heart, MessageCircle, Share2, Bookmark, Send, Image, Video, RefreshCw, MapPin, Smile, Search, X } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import clsx from 'clsx'
import { useAuth } from '../../context/AuthContext.jsx'
import { EmotionBadge, RiskBadge, SentimentBar, InterventionBanner } from '../Common/Badges.jsx'

// ── API calls ─────────────────────────────────────────────────
const useFeedApi = () => {
  const { api } = useAuth()
  return {
    getFeed:        (explore) => api.get(explore ? '/feed/explore' : '/feed'),
    getStories:     ()        => api.get('/feed/stories'),
    createPost:     (data)    => api.post('/posts', data),
    likePost:       (id)      => api.post(`/posts/${id}/like`),
    getComments:    (id)      => api.get(`/interactions/comments/${id}`),
    addComment:     (data)    => api.post('/interactions/comment', data),
    getAgentStatus: ()        => api.get(`/agents/status/me`),
  }
}

// ── Post Card ─────────────────────────────────────────────────
function PostCard({ post, onLike }) {
  const { user, api } = useAuth()
  const [liked, setLiked]           = useState(false)
  const [likeCount, setLikeCount]   = useState(post.likes_count || 0)
  const [showComments, setShowComments] = useState(false)
  const [comments, setComments]     = useState([])
  const [newComment, setNewComment] = useState('')
  const [showAI, setShowAI]         = useState(false)
  const [posting, setPosting]       = useState(false)

  const handleLike = async () => {
    const next = !liked
    setLiked(next)
    setLikeCount(c => next ? c + 1 : c - 1)
    try {
      await api.post(`/posts/${post.id}/like`)
    } catch {}
  }

  const loadComments = async () => {
    try {
      const res = await api.get(`/interactions/comments/${post.id}`)
      setComments(res.data)
    } catch {
      setComments([])
    }
  }

  const handleCommentToggle = () => {
    setShowComments(s => !s)
    if (!showComments) loadComments()
  }

  const submitComment = async (e) => {
    e.preventDefault()
    if (!newComment.trim() || posting) return
    setPosting(true)
    try {
      await api.post('/interactions/comment', {
        post_id: post.id,
        user_id: user.id,
        content: newComment,
      })
      setNewComment('')
      loadComments()
    } catch {}
    setPosting(false)
  }

  return (
    <article className="card animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between p-4 pb-3">
        <div className="flex items-center gap-3">
          <div className="story-ring">
            <img
              src={post.author?.avatar_url || `https://api.dicebear.com/9.x/avataaars/svg?seed=${post.author?.username}`}
              alt=""
              className="w-9 h-9 rounded-full bg-gray-800"
            />
          </div>
          <div>
            <p className="font-semibold text-sm text-white">{post.author?.display_name}</p>
            <div className="flex items-center gap-1.5 text-xs text-gray-500">
              <span>@{post.author?.username}</span>
              {post.location && (
                <>
                  <span>·</span>
                  <MapPin size={10} />
                  <span>{post.location}</span>
                </>
              )}
              <span>·</span>
              <span>{formatDistanceToNow(new Date(post.created_at), { addSuffix: true })}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {post.sarcasm && (
            <span className="pill bg-purple-500/15 text-purple-300 border border-purple-500/20 text-[10px]">
              🎭 sarcasm
            </span>
          )}
          <EmotionBadge emotion={post.emotion} score={post.emotion_score} />
        </div>
      </div>

      {/* Image — square like Instagram */}
      {post.image_url && (
        <div className="relative overflow-hidden bg-gray-900" style={{ aspectRatio: '1/1' }}>
          <img
            src={post.image_url}
            alt=""
            className="w-full h-full object-cover"
            loading="lazy"
          />
        </div>
      )}

      {/* Video */}
      {post.video_url && (
        <div className="relative bg-black" style={{ aspectRatio: '9/16', maxHeight: '500px' }}>
          <video
            src={post.video_url}
            className="w-full h-full object-cover"
            controls
            playsInline
          />
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-1 px-3 py-2">
        <button
          onClick={handleLike}
          className={clsx(
            'flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-sm transition-all',
            liked
              ? 'text-red-400 bg-red-400/10'
              : 'text-gray-400 hover:text-red-400 hover:bg-red-400/10'
          )}
        >
          <Heart size={16} fill={liked ? 'currentColor' : 'none'} />
          <span>{likeCount}</span>
        </button>

        <button
          onClick={handleCommentToggle}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-sm
                     text-gray-400 hover:text-brand-300 hover:bg-brand-500/10 transition-all"
        >
          <MessageCircle size={16} />
          <span>{post.comments_count || 0}</span>
        </button>

        <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-sm
                           text-gray-400 hover:text-green-400 hover:bg-green-400/10 transition-all">
          <Share2 size={16} />
        </button>

        <button className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-sm
                           text-gray-400 hover:text-yellow-400 hover:bg-yellow-400/10 transition-all">
          <Bookmark size={16} />
        </button>

        <button
          onClick={() => setShowAI(s => !s)}
          className={clsx(
            'flex items-center gap-1 px-2 py-1.5 rounded-xl text-xs font-mono transition-all',
            showAI ? 'bg-brand-500/20 text-brand-300' : 'text-gray-600 hover:text-brand-400'
          )}
        >
          AI
        </button>
      </div>

      {/* Caption — Instagram style: username + text */}
      {post.content && (
        <div className="px-4 pb-2">
          <p className="text-sm text-gray-200 leading-relaxed">
            <span className="font-semibold text-white mr-1.5">
              {post.author?.username}
            </span>
            {post.content}
          </p>
        </div>
      )}

      {/* AI Panel */}
      {showAI && (
        <div className="mx-4 mb-3 p-3 rounded-xl bg-black/30 border border-white/10
                        space-y-2 animate-fade-in">
          <p className="text-[10px] text-gray-500 uppercase tracking-widest font-mono">
            AI Analysis
          </p>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <p className="text-gray-500 mb-1">Sentiment</p>
              <SentimentBar score={post.sentiment_score || 0} />
            </div>
            <div>
              <p className="text-gray-500 mb-1">Risk Score</p>
              <div className="flex items-center gap-1.5">
                <div className="flex-1 h-1 bg-white/10 rounded-full overflow-hidden">
                  <div
                    className={clsx(
                      'h-full rounded-full',
                      (post.risk_score || 0) > 0.6 ? 'bg-red-400'
                      : (post.risk_score || 0) > 0.35 ? 'bg-yellow-400'
                      : 'bg-green-400'
                    )}
                    style={{ width: `${(post.risk_score || 0) * 100}%` }}
                  />
                </div>
                <span className="text-gray-400 w-8 text-right">
                  {Math.round((post.risk_score || 0) * 100)}%
                </span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1.5 text-[10px] text-gray-500">
            <span>Feed score:</span>
            <span className="text-brand-300 font-mono">
              {(post.feed_score || 0).toFixed(3)}
            </span>
          </div>
        </div>
      )}

      {/* Comments */}
      {showComments && (
        <div className="border-t border-white/10 animate-fade-in">
          <div className="max-h-48 overflow-y-auto p-4 space-y-3">
            {comments.length === 0 && (
              <p className="text-gray-500 text-xs text-center py-2">
                No comments yet. Be the first!
              </p>
            )}
            {comments.map(c => (
              <div key={c.id} className="flex gap-2">
                <img
                  src={c.user?.avatar_url || `https://api.dicebear.com/9.x/avataaars/svg?seed=${c.user_id}`}
                  alt=""
                  className="w-6 h-6 rounded-full bg-gray-800 flex-shrink-0 mt-0.5"
                />
                <div className="flex-1 bg-white/5 rounded-xl px-3 py-1.5">
                  <p className="text-xs text-brand-300 font-medium">
                    {c.user?.username || `user_${c.user_id}`}
                  </p>
                  <p className="text-xs text-gray-300">{c.content}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="px-4 pb-4">
            <form onSubmit={submitComment} className="flex gap-2">
              <input
                value={newComment}
                onChange={e => setNewComment(e.target.value)}
                placeholder="Add a comment..."
                className="input-field text-sm py-2 flex-1"
              />
              <button
                type="submit"
                disabled={!newComment.trim() || posting}
                className="btn-primary py-2 px-3 disabled:opacity-40"
              >
                <Send size={14} />
              </button>
            </form>
          </div>
        </div>
      )}
    </article>
  )
}

// ── Stories Bar ───────────────────────────────────────────────
function StoriesBar({ stories, onAddStory }) {
  return (
    <div className="flex gap-4 overflow-x-auto pb-1 mb-4 scrollbar-hide">
      {/* Add story */}
      <button
        onClick={onAddStory}
        className="flex flex-col items-center gap-1.5 flex-shrink-0"
      >
        <div className="w-14 h-14 rounded-full border-2 border-dashed border-brand-500/50
                        flex items-center justify-center bg-brand-500/10">
          <span className="text-xl text-brand-400">+</span>
        </div>
        <span className="text-[10px] text-gray-400">Your story</span>
      </button>

      {/* Other stories */}
      {stories.map(s => (
        <button key={s.user.id} className="flex flex-col items-center gap-1.5 flex-shrink-0">
          <div className="story-ring">
            <img
              src={s.user.avatar_url || `https://api.dicebear.com/9.x/avataaars/svg?seed=${s.user.username}`}
              alt=""
              className="w-12 h-12 rounded-full bg-gray-800"
            />
          </div>
          <span className="text-[10px] text-gray-400 max-w-12 truncate">
            {s.user.display_name}
          </span>
        </button>
      ))}
    </div>
  )
}

// ── Compose Post ──────────────────────────────────────────────
const MAX_IMAGE_MB = 10
const MAX_VIDEO_MB = 100

function ComposePost({ onPost }) {
  const { user, api } = useAuth()
  const [content, setContent]       = useState('')
  const [location, setLocation]     = useState('')
  const [mediaFile, setMediaFile]   = useState(null)   // the actual File
  const [mediaType, setMediaType]   = useState(null)   // 'image' | 'video'
  const [preview, setPreview]       = useState('')
  const [showExtras, setShowExtras] = useState(false)
  const [posting, setPosting]       = useState(false)
  const [analyzing, setAnalyzing]   = useState(false)
  const [progress, setProgress]     = useState(0)
  const [error, setError]           = useState('')
  const fileRef = useRef()

  const handleFile = (e) => {
    const file = e.target.files[0]
    if (!file) return
    setError('')

    const isVideo = file.type.startsWith('video/')
    const isImage = file.type.startsWith('image/')

    if (!isVideo && !isImage) {
      setError('Please choose an image or video file.')
      return
    }

    const sizeMb = file.size / (1024 * 1024)
    const maxMb = isVideo ? MAX_VIDEO_MB : MAX_IMAGE_MB
    if (sizeMb > maxMb) {
      setError(`File too large (${sizeMb.toFixed(1)}MB). Max is ${maxMb}MB for ${isVideo ? 'videos' : 'images'}.`)
      return
    }

    // Clean up any previous preview URL before creating a new one
    if (preview) URL.revokeObjectURL(preview)

    setMediaFile(file)
    setMediaType(isVideo ? 'video' : 'image')
    setPreview(URL.createObjectURL(file))
  }

  const clearMedia = () => {
    if (preview) URL.revokeObjectURL(preview)
    setMediaFile(null)
    setMediaType(null)
    setPreview('')
    if (fileRef.current) fileRef.current.value = ''
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!content.trim() && !mediaFile) return
    setPosting(true)
    setAnalyzing(true)
    setProgress(0)
    setError('')

    try {
      const formData = new FormData()
      formData.append('content', content)
      formData.append('location', location)

      // IMPORTANT: field name must match what the backend expects —
      // 'image' for images, 'video' for videos. Sending a video under
      // the 'image' key (or vice versa) means the backend silently
      // skips the upload.
      if (mediaFile && mediaType === 'image') {
        formData.append('image', mediaFile)
      } else if (mediaFile && mediaType === 'video') {
        formData.append('video', mediaFile)
        formData.append('is_reel', 'true')
      }

      const res = await api.post('/posts', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (evt) => {
          if (evt.total) setProgress(Math.round((evt.loaded / evt.total) * 100))
        },
      })
      onPost(res.data)
      setContent('')
      setLocation('')
      clearMedia()
      setShowExtras(false)
    } catch (err) {
      console.error(err)
      setError(err.response?.data?.detail || 'Post failed. Please try again.')
    } finally {
      setPosting(false)
      setAnalyzing(false)
      setProgress(0)
    }
  }

  return (
    <div className="card p-4 mb-4">
      <div className="flex gap-3">
        <img
          src={user?.avatar_url || `https://api.dicebear.com/9.x/avataaars/svg?seed=${user?.username}`}
          alt=""
          className="w-9 h-9 rounded-full bg-gray-800 flex-shrink-0 border-2 border-brand-500/30"
        />
        <div className="flex-1">
          <textarea
            value={content}
            onChange={e => setContent(e.target.value)}
            placeholder={mediaType === 'image' ? 'Write a caption...' : "What's on your mind?"}
            rows={mediaFile ? 2 : 2}
            className="input-field resize-none text-sm w-full"
          />

          {/* Media preview — square crop like Instagram */}
          {preview && mediaType === 'image' && (
            <div className="relative mt-2 rounded-xl overflow-hidden bg-gray-900" style={{ aspectRatio: '1/1' }}>
              <img src={preview} alt="" className="w-full h-full object-cover" />
              <button
                type="button"
                onClick={clearMedia}
                className="absolute top-2 right-2 w-6 h-6 rounded-full bg-black/60 text-white
                           flex items-center justify-center text-xs hover:bg-black/80"
              >
                <X size={12} />
              </button>
            </div>
          )}

          {preview && mediaType === 'video' && (
            <div className="relative mt-2 rounded-xl overflow-hidden bg-black">
              <video src={preview} className="w-full max-h-64 object-contain" controls playsInline />
              <button
                type="button"
                onClick={clearMedia}
                className="absolute top-2 right-2 w-6 h-6 rounded-full bg-black/60 text-white
                           flex items-center justify-center text-xs hover:bg-black/80"
              >
                <X size={12} />
              </button>
            </div>
          )}

          {/* Upload progress */}
          {posting && progress > 0 && progress < 100 && (
            <div className="mt-2 h-1 bg-white/10 rounded-full overflow-hidden">
              <div
                className="h-full bg-brand-500 transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
          )}

          {/* Error */}
          {error && (
            <p className="text-xs text-red-400 mt-2">{error}</p>
          )}

          {/* Location input */}
          {showExtras && (
            <input
              value={location}
              onChange={e => setLocation(e.target.value)}
              placeholder="Add location..."
              className="input-field text-sm mt-2 w-full"
            />
          )}

          <div className="flex items-center justify-between mt-2">
            <div className="flex gap-1">
              <input
                ref={fileRef}
                type="file"
                accept="image/*,video/*"
                onChange={handleFile}
                className="hidden"
              />
              <button
                type="button"
                onClick={() => fileRef.current.click()}
                className="btn-ghost py-1.5 px-2 text-xs flex items-center gap-1"
              >
                {mediaType === 'video' ? <Video size={14} /> : <Image size={14} />} Media
              </button>
              <button
                type="button"
                onClick={() => setShowExtras(s => !s)}
                className="btn-ghost py-1.5 px-2 text-xs flex items-center gap-1"
              >
                <MapPin size={14} /> Location
              </button>
            </div>

            <button
              onClick={handleSubmit}
              disabled={(!content.trim() && !mediaFile) || posting}
              className="btn-primary py-1.5 px-4 text-sm disabled:opacity-40
                         flex items-center gap-1.5"
            >
              {analyzing ? (
                <>
                  <RefreshCw size={12} className="animate-spin" />
                  {progress > 0 && progress < 100 ? `Uploading ${progress}%` : 'Analyzing...'}
                </>
              ) : (
                <>
                  <Send size={12} />
                  Post
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Feed Page ─────────────────────────────────────────────────
export default function FeedPage({ explore = false }) {
  const { api, user }   = useAuth()
  const navigate         = useNavigate()
  const [posts, setPosts]           = useState([])
  const [stories, setStories]       = useState([])
  const [agentStatus, setAgentStatus] = useState(null)
  const [loading, setLoading]       = useState(true)
  const [page, setPage]             = useState(0)
  const [hasMore, setHasMore]       = useState(true)
  const [search, setSearch]               = useState('')
  const [searchResults, setSearchResults] = useState([])

  // Search users (Explore page only)
  useEffect(() => {
    if (!explore || !search.trim()) { setSearchResults([]); return }
    const timer = setTimeout(() => {
      api.get(`/users/search?q=${search}`)
        .then(r => setSearchResults(r.data))
        .catch(() => {})
    }, 400)
    return () => clearTimeout(timer)
  }, [search, explore])

  const load = useCallback(async (reset = false) => {
    setLoading(true)
    try {
      const offset = reset ? 0 : page * 20
      const [feedRes, storiesRes, agentRes] = await Promise.all([
        api.get(explore ? '/feed/explore' : `/feed?limit=20&offset=${offset}`),
        api.get('/feed/stories').catch(() => ({ data: [] })),
        api.get(`/agents/status/${user?.id}`).catch(() => ({ data: null })),
      ])
      const newPosts = feedRes.data || []
      setPosts(prev => reset ? newPosts : [...prev, ...newPosts])
      setStories(storiesRes.data || [])
      setAgentStatus(agentRes.data)
      setHasMore(newPosts.length === 20)
      if (!reset) setPage(p => p + 1)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [page, explore, user])

  useEffect(() => {
    load(true)
  }, [explore])

  const handleNewPost = (post) => {
    setPosts(prev => [post, ...prev])
  }

  return (
    <div className="max-w-xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-display text-2xl text-white">
          {explore ? 'Explore' : 'Feed'}
        </h1>
        <button
          onClick={() => load(true)}
          className="btn-ghost py-1.5 px-3 text-sm flex items-center gap-1.5"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Search people (Explore only) */}
      {explore && (
        <div className="relative mb-6">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search people..."
            className="input-field pl-8 text-sm py-2.5 w-full"
          />
          {searchResults.length > 0 && (
            <div className="absolute z-30 mt-1 w-full card p-1 max-h-64 overflow-y-auto">
              {searchResults.map(u => (
                <button
                  key={u.id}
                  onClick={() => {
                    setSearch('')
                    setSearchResults([])
                    navigate(`/profile/${u.username}`)
                  }}
                  className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 transition-all text-left"
                >
                  <img
                    src={u.avatar_url || `https://api.dicebear.com/9.x/avataaars/svg?seed=${u.username}`}
                    alt=""
                    className="w-8 h-8 rounded-full bg-gray-800"
                  />
                  <div className="min-w-0">
                    <p className="text-sm text-white truncate">{u.display_name}</p>
                    <p className="text-xs text-gray-500 truncate">@{u.username}</p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}


      {/* Stories */}
      {!explore && (
        <StoriesBar stories={stories} onAddStory={() => {}} />
      )}

      {/* Compose */}
      {!explore && <ComposePost onPost={handleNewPost} />}

      {/* Intervention banner — shown silently when AI detects risk */}
      <InterventionBanner agentStatus={agentStatus} />

      {/* Posts */}
      {loading && posts.length === 0 ? (
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="card p-4 animate-pulse space-y-3">
              <div className="flex gap-3">
                <div className="w-10 h-10 rounded-full bg-white/10" />
                <div className="flex-1 space-y-2">
                  <div className="h-3 bg-white/10 rounded w-1/3" />
                  <div className="h-2 bg-white/10 rounded w-1/4" />
                </div>
              </div>
              <div className="h-40 bg-white/5 rounded-xl" />
            </div>
          ))}
        </div>
      ) : (
        <>
          <div className="space-y-4">
            {posts.map(post => (
              <PostCard key={post.id} post={post} />
            ))}
          </div>

          {/* Load more */}
          {hasMore && !loading && (
            <button
              onClick={() => load(false)}
              className="w-full mt-4 btn-ghost py-3 text-sm"
            >
              Load more
            </button>
          )}

          {posts.length === 0 && !loading && (
            <div className="text-center py-12">
              <p className="text-gray-400 text-sm">
                {explore
                  ? 'No posts yet. Be the first!'
                  : 'Follow people to see their posts here!'}
              </p>
            </div>
          )}
        </>
      )}
    </div>
  )
}