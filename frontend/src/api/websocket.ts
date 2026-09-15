/**
 * AI Interview Coach — WebSocket Client
 * Handles real-time interview session communication.
 */

import type { WSMessage } from '../types';

type MessageHandler = (message: WSMessage) => void;

export class InterviewWebSocket {
  private ws: WebSocket | null = null;
  private handlers: Map<string, MessageHandler[]> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private sessionId: string = '';
  private shouldReconnect = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private lastAudioConfig: Record<string, unknown> | null = null;
  private sessionRequested = false;

  connect(sessionId: string): Promise<void> {
    if (
      this.sessionId === sessionId
      && this.ws
      && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)
    ) {
      return this.ws.readyState === WebSocket.OPEN
        ? Promise.resolve()
        : new Promise((resolve, reject) => {
            this.ws!.addEventListener('open', () => resolve(), { once: true });
            this.ws!.addEventListener('error', reject, { once: true });
          });
    }

    this.shouldReconnect = true;
    this.sessionId = sessionId;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    return new Promise((resolve, reject) => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const url = `${protocol}//${window.location.host}/ws/interview/${sessionId}`;
      const socket = new WebSocket(url);
      this.ws = socket;

      socket.onopen = () => {
        const isReconnect = this.reconnectAttempts > 0;
        this.reconnectAttempts = 0;
        // Always (re)apply audio config + start when the socket opens if the
        // UI has requested a live session. This recovers from Strict Mode
        // remounts and mid-handshake drops where start never arrived.
        if (this.lastAudioConfig) {
          this.send({ type: 'config', data: this.lastAudioConfig });
        }
        if (this.sessionRequested) {
          this.send({ type: 'start' });
        }
        resolve();
        if (isReconnect) {
          // already handled above
        }
      };

      socket.onmessage = (event) => {
        try {
          const rawMessage = JSON.parse(event.data);
          let message: WSMessage;
          
          if (rawMessage.version === 1 && rawMessage.payload) {
            message = {
              ...rawMessage.payload,
              type: rawMessage.type, // Ensure type is at the top level for handlers
              _metadata: {
                event_id: rawMessage.event_id,
                session_id: rawMessage.session_id,
                utterance_id: rawMessage.utterance_id,
                question_id: rawMessage.question_id,
                timestamp: rawMessage.timestamp,
              }
            };
          } else {
            message = rawMessage;
          }
          
          this.dispatch(message);
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };

      socket.onerror = (error) => {
        console.error('WebSocket error:', error);
        reject(error);
      };

      socket.onclose = () => {
        if (this.ws !== socket) return;
        this.ws = null;
        this.dispatch({ type: 'disconnected' });
        if (this.shouldReconnect) this.attemptReconnect();
      };
    });
  }

  on(type: string, handler: MessageHandler): () => void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, []);
    }
    this.handlers.get(type)!.push(handler);

    // Return unsubscribe function
    return () => {
      const handlers = this.handlers.get(type);
      if (handlers) {
        const index = handlers.indexOf(handler);
        if (index > -1) handlers.splice(index, 1);
      }
    };
  }

  private dispatch(message: WSMessage) {
    const typeHandlers = this.handlers.get(message.type) || [];
    const wildcardHandlers = this.handlers.get('*') || [];

    for (const handler of [...typeHandlers, ...wildcardHandlers]) {
      try {
        handler(message);
      } catch (e) {
        console.error('Handler error:', e);
      }
    }
  }

  // ── Control Messages ─────────────────────────────────────────

  configureAudio(
    micDeviceIndex: number | null,
    loopbackDeviceIndex: number | null,
    lengthMode = 'STANDARD',
    languageMode = 'ANSWER_IN_QUESTION_LANGUAGE',
  ) {
    this.lastAudioConfig = {
      mic_device_index: micDeviceIndex,
      loopback_device_index: loopbackDeviceIndex,
      length_mode: lengthMode,
      language_mode: languageMode,
    };
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.send({ type: 'config', data: this.lastAudioConfig });
    }
  }

  startSession() {
    this.sessionRequested = true;
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.send({ type: 'start' });
    }
  }

  pauseSession() {
    this.sessionRequested = false;
    this.send({ type: 'pause' });
  }

  resumeSession() {
    this.sessionRequested = true;
    this.send({ type: 'resume' });
  }

  endSession() {
    this.sessionRequested = false;
    this.send({ type: 'end' });
  }

  sendUtterance(text: string, lengthMode = 'STANDARD', languageMode = 'ANSWER_IN_QUESTION_LANGUAGE') {
    this.send({
      type: 'utterance',
      data: { text, length_mode: lengthMode, language_mode: languageMode },
    });
  }

  sendCandidateAnswer(text: string, question?: string) {
    this.send({
      type: 'candidate_answer',
      data: { text, question },
    });
  }

  requestAudioDevices() {
    this.send({ type: 'audio_config' });
  }

  getState() {
    this.send({ type: 'get_state' });
  }

  // ── Internal ─────────────────────────────────────────────────

  private send(data: unknown) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      console.warn('WebSocket not connected');
    }
  }

  private attemptReconnect() {
    if (!this.shouldReconnect || this.reconnectTimer) return;
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.dispatch({ type: 'reconnect_failed' });
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000);

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (this.shouldReconnect && this.sessionId) {
        this.connect(this.sessionId).catch(() => {
          this.attemptReconnect();
        });
      }
    }, delay);
  }

  disconnect() {
    this.shouldReconnect = false;
    // Keep sessionRequested/lastAudioConfig so a remount can resume cleanly.
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    const socket = this.ws;
    this.ws = null;
    if (socket) socket.close();
    // Do not clear handlers here — React Strict Mode remounts register new
    // handlers after disconnect; clearing races and drops live events.
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

// Singleton
export const interviewWS = new InterviewWebSocket();
