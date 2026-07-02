import React, { createContext, useContext, useEffect, useRef, useState } from 'react'
import { useAuth } from './AuthContext'

const SocketContext = createContext(null)

export function SocketProvider({ children }) {
  const { user } = useAuth()
  const ws = useRef(null)
  const [isConnected, setIsConnected] = useState(false)
  const [messages, setMessages] = useState([])
  const listeners = useRef({})

  useEffect(() => {
    if (!user) return

    // Connect WebSocket
    const connect = () => {
      ws.current = new WebSocket(`ws://localhost:8000/api/messages/ws/${user.id}`)

      ws.current.onopen = () => {
        setIsConnected(true)
        console.log('WebSocket connected')
      }

      ws.current.onmessage = (event) => {
        const data = JSON.parse(event.data)

        // Add to messages
        setMessages(prev => [...prev, data])

        // Notify listeners
        if (listeners.current[data.type]) {
          listeners.current[data.type].forEach(cb => cb(data))
        }
      }

      ws.current.onclose = () => {
        setIsConnected(false)
        // Reconnect after 3 seconds
        setTimeout(connect, 3000)
      }

      ws.current.onerror = () => {
        ws.current.close()
      }
    }

    connect()

    return () => {
      if (ws.current) ws.current.close()
    }
  }, [user])

  const sendMessage = (receiverId, content) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({
        receiver_id: receiverId,
        content,
      }))
    }
  }

  const on = (event, callback) => {
    if (!listeners.current[event]) {
      listeners.current[event] = []
    }
    listeners.current[event].push(callback)
    // Return cleanup function
    return () => {
      listeners.current[event] = listeners.current[event].filter(cb => cb !== callback)
    }
  }

  return (
    <SocketContext.Provider value={{
      isConnected,
      messages,
      sendMessage,
      on,
    }}>
      {children}
    </SocketContext.Provider>
  )
}

export const useSocket = () => {
  const ctx = useContext(SocketContext)
  if (!ctx) throw new Error('useSocket must be used within SocketProvider')
  return ctx
}