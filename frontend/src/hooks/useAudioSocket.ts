import { useCallback, useEffect, useRef, useState } from 'react';
import { buildWSUrl } from '@/lib/ws';

export type SttMode = 'browser' | 'deepgram';

interface SpeechRecognitionEvent {
  resultIndex: number;
  results: SpeechRecognitionResultList;
}

interface UseAudioSocketOptions {
  onResult?: (text: string) => void;
  lang?: string;
  mode?: SttMode;
}

export function useAudioSocket(sessionId: string | null, options: UseAudioSocketOptions = {}) {
  const { onResult, lang = 'en-US', mode = 'browser' } = options;

  const onResultRef = useRef(onResult);
  onResultRef.current = onResult;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognitionRef = useRef<any>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [dgConnecting, setDgConnecting] = useState(false);
  const transcriptRef = useRef('');

  // Deepgram raw WS refs
  const dgWsRef = useRef<WebSocket | null>(null);
  const dgTranscriptRef = useRef('');
  const dgReadyRef = useRef(false);
  const keepAliveRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pendingDeliveryRef = useRef(false);
  const deliverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Backend audio WS (kept for TTS only in deepgram mode) ──
  const awaitingTtsRef = useRef(false);

  useEffect(() => {
    if (mode !== 'deepgram' || !sessionId) return;

    const url = buildWSUrl(`/audio/${sessionId}`);
    const ws = new WebSocket(url);
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;

    ws.onmessage = (evt) => {
      if (evt.data instanceof ArrayBuffer) {
        try {
          const blob = new Blob([evt.data], { type: 'audio/mpeg' });
          const audioUrl = URL.createObjectURL(blob);
          const audio = new Audio(audioUrl);
          audio.onended = () => URL.revokeObjectURL(audioUrl);
          audio.play().catch(() => {});
        } catch { /* playback failed */ }
        return;
      }
      try {
        const msg = JSON.parse(evt.data);
        if (msg.event === 'audio.tts.start') awaitingTtsRef.current = true;
        else if (msg.event === 'audio.tts.end') awaitingTtsRef.current = false;
      } catch { /* bad JSON */ }
    };

    ws.onerror = (err) => console.error('[useAudioSocket] TTS WS error:', err);
    ws.onclose = () => { wsRef.current = null; };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [sessionId, mode]);

  // ── Pre-connect Deepgram raw WebSocket ─────────────────────
  useEffect(() => {
    if (mode !== 'deepgram') return;

    const dgApiKey = import.meta.env.VITE_DEEPGRAM_API_KEY;
    if (!dgApiKey) {
      console.error('[DG] VITE_DEEPGRAM_API_KEY not set');
      return;
    }

    const dgLanguage = lang.split('-')[0] || 'en';
    // Auth via query param — browser WebSocket cannot set custom headers,
    // and sub-protocol auth is unreliable across browsers.
    const params = new URLSearchParams({
      token: dgApiKey,
      model: 'nova-3',
      language: dgLanguage,
      smart_format: 'true',
      interim_results: 'true',
      utterance_end_ms: '1500',
      punctuate: 'true',
      vad_events: 'true',
    });

    const dgUrl = `wss://api.deepgram.com/v1/listen?${params}`;
    console.log('[DG] Connecting to Deepgram...');
    setDgConnecting(true);

    const dgWs = new WebSocket(dgUrl);
    dgWsRef.current = dgWs;

    dgWs.onopen = () => {
      dgReadyRef.current = true;
      setDgConnecting(false);
      console.log('[DG] ✅ WebSocket OPEN and ready');

      // Keep alive every 8s
      keepAliveRef.current = setInterval(() => {
        if (dgWs.readyState === WebSocket.OPEN) {
          dgWs.send(JSON.stringify({ type: 'KeepAlive' }));
        }
      }, 8000);
    };

    dgWs.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        console.log('[DG] msg:', msg.type, JSON.stringify(msg).slice(0, 200));

        if (msg.type === 'Results') {
          const alt = msg.channel?.alternatives?.[0];
          const transcript = alt?.transcript || '';
          console.log('[DG] transcript:', JSON.stringify(transcript), 'is_final:', msg.is_final, 'speech_final:', msg.speech_final);

          if (transcript && msg.is_final) {
            dgTranscriptRef.current += (dgTranscriptRef.current ? ' ' : '') + transcript;
            console.log('[DG] ✅ accumulated:', JSON.stringify(dgTranscriptRef.current));
          }
        } else if (msg.type === 'UtteranceEnd') {
          console.log('[DG] UtteranceEnd received');
          if (pendingDeliveryRef.current) {
            pendingDeliveryRef.current = false;
            if (deliverTimeoutRef.current) {
              clearTimeout(deliverTimeoutRef.current);
              deliverTimeoutRef.current = null;
            }
            const text = dgTranscriptRef.current.trim();
            console.log('[DG] delivering via UtteranceEnd:', JSON.stringify(text));
            if (text) onResultRef.current?.(text);
            else console.warn('[DG] ⚠️ no transcript at UtteranceEnd');
            dgTranscriptRef.current = '';
          }
        }
      } catch { /* bad JSON */ }
    };

    dgWs.onerror = (err) => {
      console.error('[DG] ❌ WebSocket error:', err);
    };

    dgWs.onclose = (evt) => {
      console.log('[DG] WebSocket CLOSED, code:', evt.code, 'reason:', evt.reason);
      dgReadyRef.current = false;
      setDgConnecting(false);
    };

    return () => {
      if (keepAliveRef.current) {
        clearInterval(keepAliveRef.current);
        keepAliveRef.current = null;
      }
      if (deliverTimeoutRef.current) {
        clearTimeout(deliverTimeoutRef.current);
        deliverTimeoutRef.current = null;
      }
      if (dgWsRef.current) {
        dgWsRef.current.close();
        dgWsRef.current = null;
      }
      dgReadyRef.current = false;
      pendingDeliveryRef.current = false;
      setDgConnecting(false);
    };
  }, [mode, lang]);

  // ── Start recording ───────────────────────────────────────
  const startRecording = useCallback(async () => {
    if (mode === 'deepgram') {
      if (!dgReadyRef.current || !dgWsRef.current) {
        console.warn('[DG] Socket not ready yet, cannot record');
        return;
      }

      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        streamRef.current = stream;
      } catch (err) {
        console.error('[DG] Mic access error:', err);
        return;
      }

      dgTranscriptRef.current = '';

      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
      mediaRef.current = recorder;

      // Tell Deepgram the stream has ended so it finalises the last utterance
      recorder.onstop = () => {
        if (dgWsRef.current?.readyState === WebSocket.OPEN) {
          dgWsRef.current.send(JSON.stringify({ type: 'CloseStream' }));
          console.log('[DG] Sent CloseStream');
        }
      };

      recorder.ondataavailable = (e) => {
        if (e.data.size === 0) return;
        console.log('[DG] sending audio chunk:', e.data.size, 'bytes');
        if (dgWsRef.current?.readyState === WebSocket.OPEN) {
          dgWsRef.current.send(e.data);
        }
      };

      recorder.start(250);
      setIsRecording(true);
      console.log('[DG] ✅ Recording started');

    } else {
      // Browser Web Speech API
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (!SR) {
        console.warn('SpeechRecognition API not supported in this browser');
        return;
      }

      if (recognitionRef.current) {
        try { recognitionRef.current.abort(); } catch { /* ignore */ }
      }

      const recognition = new SR();
      recognition.lang = lang;
      recognition.interimResults = true;
      recognition.continuous = true;
      recognition.maxAlternatives = 1;
      recognitionRef.current = recognition;
      transcriptRef.current = '';

      recognition.onresult = (event: SpeechRecognitionEvent) => {
        let finalTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          if (result.isFinal) {
            finalTranscript += result[0].transcript;
          }
        }
        if (finalTranscript) {
          transcriptRef.current += finalTranscript;
        }
      };

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      recognition.onerror = (e: any) => {
        if (e.error !== 'aborted') {
          console.warn('SpeechRecognition error:', e.error);
        }
      };

      recognition.onend = () => {
        setIsRecording(false);
        const text = transcriptRef.current.trim();
        if (text) onResultRef.current?.(text);
        transcriptRef.current = '';
      };

      try {
        recognition.start();
        setIsRecording(true);
      } catch { /* already started or not allowed */ }
    }
  }, [mode, lang]);

  // ── Stop recording ────────────────────────────────────────
  const stopRecording = useCallback(() => {
    if (mode === 'deepgram') {
      // Stop recorder
      if (mediaRef.current && mediaRef.current.state !== 'inactive') {
        mediaRef.current.stop();
      }
      mediaRef.current = null;

      // Stop mic
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }

      setIsRecording(false);

      // UtteranceEnd handler delivers the transcript when Deepgram confirms
      // silence. 2 s fallback fires if UtteranceEnd never arrives.
      pendingDeliveryRef.current = true;
      console.log('[DG] stopRecording — waiting for UtteranceEnd (2 s fallback)...');
      deliverTimeoutRef.current = setTimeout(() => {
        if (!pendingDeliveryRef.current) return;
        pendingDeliveryRef.current = false;
        const text = dgTranscriptRef.current.trim();
        console.log('[DG] delivering transcript (fallback timeout):', JSON.stringify(text));
        if (text) onResultRef.current?.(text);
        else console.warn('[DG] ⚠️ no transcript to deliver');
        dgTranscriptRef.current = '';
      }, 2000);

    } else {
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch { /* ignore */ }
        recognitionRef.current = null;
      }
    }
  }, [mode]);

  // ── TTS: use backend WS for deepgram mode, browser otherwise ─
  const requestTTS = useCallback((text: string) => {
    if (mode === 'deepgram' && wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ event: 'audio.tts.request', data: { text, voice: 'alloy' } }),
      );
    } else if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = lang;
      utterance.rate = 0.95;
      window.speechSynthesis.speak(utterance);
    }
  }, [mode, lang]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopRecording();
    };
  }, [stopRecording]);

  return { startRecording, stopRecording, isRecording, isConnecting: dgConnecting, requestTTS };
}
