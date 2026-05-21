// src/App.tsx
import React, { useState, useEffect, useRef } from 'react';
import './App.css';

// Define message types based on API specification
interface ChatMessage {
  type: 'message' | 'system';
  callsign: string;
  text?: string;
  event?: 'user_joined' | 'user_left';
  timestamp: string;
}

const WS_ENDPOINT = import.meta.env.VITE_WS_ENDPOINT || "";

function App() {
  const [screen, setScreen] = useState<'join' | 'chat'>('join');
  const [callsign, setCallsign] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [status, setStatus] = useState<'Disconnected' | 'Connecting' | 'Connected'>('Disconnected');
  
  const ws = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleJoin = (e: React.FormEvent) => {
    e.preventDefault();
    if (!callsign.trim() || callsign.length > 20) {
      alert('Callsign must be 1-20 characters.');
      return;
    }

    setStatus('Connecting');
    
    // Initialize WebSocket connection
    const wsUrl = `${WS_ENDPOINT}?callsign=${encodeURIComponent(callsign)}`;
    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = () => {
      setStatus('Connected');
      setScreen('chat');
    };

    ws.current.onmessage = (event) => {
      try {
        const data: ChatMessage = JSON.parse(event.data);
        setMessages((prev) => [...prev, data]);
      } catch (err) {
        console.error('Failed to parse message', err);
      }
    };

    ws.current.onclose = () => {
      setStatus('Disconnected');
    };

    ws.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      setStatus('Disconnected');
    };
  };

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || !ws.current || ws.current.readyState !== WebSocket.OPEN) return;

    const payload = {
      action: 'sendMessage',
      text: inputText.trim(),
    };

    ws.current.send(JSON.stringify(payload));
    setInputText('');
  };

  const handleDisconnect = () => {
    if (ws.current) {
      ws.current.close();
    }
    setScreen('join');
    setMessages([]);
    setCallsign('');
  };

  const getStatusClass = () => {
    if (status === 'Connected') return 'status-connected';
    if (status === 'Connecting') return 'status-connecting';
    return 'status-disconnected';
  };

  // --- View: Join Screen (Mirrors LIMS Auth Screen) ---
  if (screen === 'join') {
    return (
      <div className="auth-overlay">
        <div className="auth-card">
          <div className="auth-header">
            <div className="auth-header-icon">
              <span className="material-symbols-outlined" style={{ fontSize: '32px' }}>forum</span>
            </div>
            <h2 style={{ margin: '0 0 4px 0', fontSize: '1.25rem', color: 'var(--text-slate-900)' }}>Portal Access</h2>
            <p style={{ margin: 0, fontSize: '10px', color: 'var(--text-slate-400)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 700 }}>
              Anonymous Chat System
            </p>
          </div>

          <form onSubmit={handleJoin} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-slate-400)', textTransform: 'uppercase', paddingLeft: '4px' }}>
                Your Callsign
              </label>
              <input
                className="input-field"
                type="text"
                placeholder="e.g. Jasper"
                value={callsign}
                onChange={(e) => setCallsign(e.target.value)}
                maxLength={20}
                required
              />
            </div>
            
            <button className="btn-primary" type="submit" disabled={status === 'Connecting'} style={{ marginTop: '8px' }}>
              {status === 'Connecting' ? 'Connecting...' : 'Enter Chat'}
            </button>
          </form>

          <div style={{ textAlign: 'center', marginTop: '24px' }}>
            <span className={`status-badge ${getStatusClass()}`}>{status}</span>
          </div>
        </div>
      </div>
    );
  }

  // --- View: Chat Screen ---
  return (
    <div className="app-layout">
      {/* Header */}
      <header className="header">
        <div className="header-title">
          <div className="header-icon">
            <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>science</span>
          </div>
          <span style={{ color: 'var(--text-slate-900)' }}>Anonymous <span style={{ color: 'var(--corporate-blue)', fontWeight: 400 }}>Chat</span></span>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span className={`status-badge ${getStatusClass()}`}>{status}</span>
          <button className="btn-secondary" onClick={handleDisconnect} title="Leave Chat">
            <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>logout</span>
            <span className="hide-on-mobile">Leave</span>
          </button>
        </div>
      </header>
      
      {/* Scrollable Message List */}
      <div className="chat-container custom-scrollbar">
        {messages.map((msg, idx) => {
          if (msg.type === 'system') {
            return (
              <div key={idx} className="system-msg">
                {msg.callsign} {msg.event === 'user_joined' ? 'joined the channel' : 'left the channel'}
              </div>
            );
          }

          const isOwnMessage = msg.callsign === callsign;
          return (
            <div key={idx} className={`message-wrapper ${isOwnMessage ? 'own' : 'other'}`}>
              <div className="message-sender">
                {isOwnMessage ? 'You' : msg.callsign}
              </div>
              <div className="message-bubble">
                {msg.text}
              </div>
            </div>
          );
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area (Fixed to bottom) */}
      <footer className="input-area">
        <form className="input-form" onSubmit={handleSendMessage}>
          <input
            className="input-field"
            type="text"
            placeholder="Type your message..."
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            maxLength={1000}
            required
            autoComplete="off"
          />
          <button className="btn-primary" type="submit" disabled={!inputText.trim()}>
            <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>send</span>
            <span style={{ display: 'none' /* hidden text for screen readers if needed */ }}>Send</span>
          </button>
        </form>
      </footer>
    </div>
  );
}

export default App;