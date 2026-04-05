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
  audioRoute?: string;
  useBackendTTS?: boolean;
}

export function useAudioSocket(sessionId: string | null, options: UseAudioSocketOptions = {}) {
  const {
    onResult,
    lang = 'en-US',
    mode = 'browser',
    audioRoute = 'audio',
    useBackendTTS = true,
  } = options;

  const onResultRef = useRef(onResult);

  useEffect(() => {
    onResultRef.current = onResult;
  }, [onResult]);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognitionRef = useRef<any>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const gainNodeRef = useRef<GainNode | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const processorNodeRef = useRef<ScriptProcessorNode | null>(null);
  const isRecordingRef = useRef(false);
  const isStoppingRef = useRef(false);
  const dgTranscriptRef = useRef('');
  const dgReadyRef = useRef(false);
  const keepAliveRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pendingDeliveryRef = useRef(false);
  const deliverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [dgConnecting, setDgConnecting] = useState(false);
  const transcriptRef = useRef('');

  // ── Backend audio WS (used for STT + TTS in deepgram mode) ──
  const awaitingTtsRef = useRef(false);

  useEffect(() => {
    if (mode !== 'deepgram' || !sessionId) return;

    const language = encodeURIComponent(lang.split('-')[0] || 'en');
    const url = buildWSUrl(`/${audioRoute}/${sessionId}?language=${language}`);
    setDgConnecting(true);
    const ws = new WebSocket(url);
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;

    ws.onopen = () => {
      setDgConnecting(false);
    };

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
        if (msg.event === 'audio.tts.start') {
          awaitingTtsRef.current = true;
        } else if (msg.event === 'audio.tts.end') {
          awaitingTtsRef.current = false;
        } else if (msg.event === 'transcription.result') {
          const text = String(msg.data?.text ?? '').trim();
          const isFinal = Boolean(msg.data?.is_final);
          if (isFinal && text) {
            onResultRef.current?.(text);
          }
        }
      } catch { /* bad JSON */ }
    };

    ws.onerror = (err) => {
      console.error('[useAudioSocket] Audio WS error:', err);
    };
    ws.onclose = () => {
      wsRef.current = null;
      setDgConnecting(false);
    };

    return () => {
      ws.close();
      wsRef.current = null;
      setDgConnecting(false);
    };
  }, [mode, lang, sessionId, audioRoute]);

  useEffect(() => {
    if (mode !== 'deepgram' || sessionId) return;

    const dgApiKey = import.meta.env.VITE_DEEPGRAM_API_KEY;
    if (!dgApiKey) {
      console.error('[DG] VITE_DEEPGRAM_API_KEY not set');
      return;
    }

    const dgLanguage = lang.split('-')[0] || 'en';
    const params = new URLSearchParams({
      token: dgApiKey,
      model: 'nova-3',
      language: dgLanguage,
      smart_format: 'true',
      interim_results: 'true',
      utterance_end_ms: '900',
      punctuate: 'true',
      vad_events: 'true',
    });

    const dgUrl = `wss://api.deepgram.com/v1/listen?${params}`;
    const dgWs = new WebSocket(dgUrl);
    dgWs.binaryType = 'arraybuffer';
    wsRef.current = dgWs;
    setDgConnecting(true);

    dgWs.onopen = () => {
      dgReadyRef.current = true;
      setDgConnecting(false);
      if (keepAliveRef.current) clearInterval(keepAliveRef.current);
      keepAliveRef.current = setInterval(() => {
        if (dgWs.readyState === WebSocket.OPEN) {
          dgWs.send(JSON.stringify({ type: 'KeepAlive' }));
        }
      }, 8000);
    };

    dgWs.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === 'Results') {
          const alt = msg.channel?.alternatives?.[0];
          const transcript = String(alt?.transcript ?? '').trim();
          if (transcript && msg.is_final) {
            dgTranscriptRef.current += (dgTranscriptRef.current ? ' ' : '') + transcript;
          }
        } else if (msg.type === 'UtteranceEnd') {
          if (pendingDeliveryRef.current) {
            pendingDeliveryRef.current = false;
            if (deliverTimeoutRef.current) {
              clearTimeout(deliverTimeoutRef.current);
              deliverTimeoutRef.current = null;
            }
            const text = dgTranscriptRef.current.trim();
            if (text) onResultRef.current?.(text);
            dgTranscriptRef.current = '';
          }
        }
      } catch {
        // ignore non-JSON
      }
    };

    dgWs.onerror = (err) => {
      console.error('[DG] WebSocket error:', err);
    };

    dgWs.onclose = () => {
      dgReadyRef.current = false;
      setDgConnecting(false);
      if (keepAliveRef.current) {
        clearInterval(keepAliveRef.current);
        keepAliveRef.current = null;
      }
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
      pendingDeliveryRef.current = false;
      dgReadyRef.current = false;
      dgTranscriptRef.current = '';
      dgWs.close();
      wsRef.current = null;
      setDgConnecting(false);
    };
  }, [mode, lang, sessionId]);

  // ── Start recording ───────────────────────────────────────
  const startRecording = useCallback(async () => {
    if (mode === 'deepgram') {
      if (isRecordingRef.current || isStoppingRef.current) {
        return;
      }
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        console.warn('[Audio] Socket not ready yet, cannot record');
        return;
      }

      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        streamRef.current = stream;
      } catch (err) {
        console.error('[Audio] Mic access error:', err);
        return;
      }

      const AudioContextCtor = window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AudioContextCtor) {
        console.error('[Audio] AudioContext not supported in this browser');
        stream.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        return;
      }

      const audioCtx = new AudioContextCtor({ sampleRate: 16000 });
      audioContextRef.current = audioCtx;

      const source = audioCtx.createMediaStreamSource(stream);
      sourceNodeRef.current = source;

      // Keep graph active but muted so we don't echo mic audio locally.
      const gainNode = audioCtx.createGain();
      gainNode.gain.value = 0;
      gainNodeRef.current = gainNode;

      if (audioCtx.audioWorklet) {
        try {
          const workletCode = `
            class PCM16Processor extends AudioWorkletProcessor {
              process(inputs) {
                const input = inputs[0];
                if (!input || !input[0]) return true;
                const channel = input[0];
                const pcm16 = new Int16Array(channel.length);
                for (let i = 0; i < channel.length; i++) {
                  const s = Math.max(-1, Math.min(1, channel[i]));
                  pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
                }
                this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
                return true;
              }
            }
            registerProcessor('pcm16-processor', PCM16Processor);
          `;
          const blob = new Blob([workletCode], { type: 'application/javascript' });
          const moduleUrl = URL.createObjectURL(blob);
          await audioCtx.audioWorklet.addModule(moduleUrl);
          URL.revokeObjectURL(moduleUrl);

          const workletNode = new AudioWorkletNode(audioCtx, 'pcm16-processor', {
            numberOfInputs: 1,
            numberOfOutputs: 1,
            channelCount: 1,
          });
          workletNodeRef.current = workletNode;

          workletNode.port.onmessage = (evt) => {
            if (wsRef.current?.readyState === WebSocket.OPEN && evt.data instanceof ArrayBuffer) {
              wsRef.current.send(evt.data);
            }
          };

          source.connect(workletNode);
          workletNode.connect(gainNode);
          gainNode.connect(audioCtx.destination);
        } catch (err) {
          console.warn('[Audio] AudioWorklet unavailable, falling back to ScriptProcessorNode', err);
        }
      }

      if (!workletNodeRef.current) {
        const processor = audioCtx.createScriptProcessor(4096, 1, 1);
        processorNodeRef.current = processor;

        processor.onaudioprocess = (e) => {
          const input = e.inputBuffer.getChannelData(0);
          const pcm16 = new Int16Array(input.length);
          for (let i = 0; i < input.length; i++) {
            const s = Math.max(-1, Math.min(1, input[i]));
            pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
          }
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(pcm16.slice().buffer);
          }
        };

        source.connect(processor);
        processor.connect(gainNode);
        gainNode.connect(audioCtx.destination);
      }

      isRecordingRef.current = true;
      dgTranscriptRef.current = '';
      setIsRecording(true);

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
        isRecordingRef.current = true;
        setIsRecording(true);
      } catch { /* already started or not allowed */ }
    }
  }, [mode, lang]);

  // ── Stop recording ────────────────────────────────────────
  const stopRecording = useCallback(() => {
    if (mode === 'deepgram') {
      if (!isRecordingRef.current || isStoppingRef.current) {
        return;
      }
      isStoppingRef.current = true;

      if (processorNodeRef.current) {
        processorNodeRef.current.disconnect();
        processorNodeRef.current.onaudioprocess = null;
        processorNodeRef.current = null;
      }

      if (workletNodeRef.current) {
        workletNodeRef.current.port.onmessage = null;
        workletNodeRef.current.disconnect();
        workletNodeRef.current = null;
      }

      if (gainNodeRef.current) {
        gainNodeRef.current.disconnect();
        gainNodeRef.current = null;
      }

      if (sourceNodeRef.current) {
        sourceNodeRef.current.disconnect();
        sourceNodeRef.current = null;
      }

      if (audioContextRef.current) {
        audioContextRef.current.close().catch(() => {});
        audioContextRef.current = null;
      }

      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }

      if (wsRef.current?.readyState === WebSocket.OPEN) {
        if (sessionId) {
          wsRef.current.send(JSON.stringify({ event: 'audio.stt.flush', data: {} }));
        } else {
          wsRef.current.send(JSON.stringify({ type: 'CloseStream' }));
          pendingDeliveryRef.current = true;
          deliverTimeoutRef.current = setTimeout(() => {
            if (!pendingDeliveryRef.current) return;
            pendingDeliveryRef.current = false;
            const text = dgTranscriptRef.current.trim();
            if (text) onResultRef.current?.(text);
            dgTranscriptRef.current = '';
          }, 1200);
        }
      }

      isRecordingRef.current = false;
      isStoppingRef.current = false;
      setIsRecording(false);

    } else {
      if (!isRecordingRef.current) {
        return;
      }
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch { /* ignore */ }
        recognitionRef.current = null;
      }
      isRecordingRef.current = false;
    }
  }, [mode, sessionId]);

  // ── TTS: use backend WS for deepgram mode, browser otherwise ─
  const requestTTS = useCallback((text: string) => {
    const ws = wsRef.current;
    const canUseBackendTTS = Boolean(sessionId) && useBackendTTS && mode === 'deepgram' && ws?.readyState === WebSocket.OPEN;
    if (canUseBackendTTS) {
      ws.send(
        JSON.stringify({ event: 'audio.tts.request', data: { text, voice: 'alloy' } }),
      );
    } else if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = lang;
      utterance.rate = 0.99;
      window.speechSynthesis.speak(utterance);
    }
  }, [mode, lang, sessionId, useBackendTTS]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopRecording();
    };
  }, [stopRecording]);

  return { startRecording, stopRecording, isRecording, isConnecting: dgConnecting, requestTTS };
}
