import { useCallback, useRef, useState } from "react";

interface UseSpeechToTextOptions {
    /**
     * Language code for speech recognition (e.g., "en-US", "hi-IN", "bn-BD")
     */
    language?: string;
    /**
     * Called with interim transcription results as the user speaks
     */
    onInterimResult?: (transcript: string) => void;
    /**
     * Called with final transcription results
     */
    onFinalResult?: (transcript: string) => void;
    /**
     * Called when an error occurs
     */
    onError?: (error: string) => void;
    /**
     * WebSocket URL for the speech-to-text service
     */
    wsUrl?: string;
}

interface UseSpeechToTextReturn {
    /**
     * Whether speech recognition is currently active
     */
    isListening: boolean;
    /**
     * Current interim transcript
     */
    interimTranscript: string;
    /**
     * Start listening for speech
     */
    startListening: () => Promise<void>;
    /**
     * Stop listening for speech
     */
    stopListening: () => void;
    /**
     * Any error that occurred
     */
    error: string | null;
}

/**
 * Hook for real-time speech-to-text using Google Cloud Speech-to-Text API
 * via WebSocket connection to the backend.
 */
export function useSpeechToText(options: UseSpeechToTextOptions = {}): UseSpeechToTextReturn {
    const {
        language = "en-US",
        onInterimResult,
        onFinalResult,
        onError,
        wsUrl = "ws://localhost:8000/api/v1/speech/ws/speech-to-text",
    } = options;

    const [isListening, setIsListening] = useState(false);
    const [interimTranscript, setInterimTranscript] = useState("");
    const [error, setError] = useState<string | null>(null);

    const wsRef = useRef<WebSocket | null>(null);
    const mediaStreamRef = useRef<MediaStream | null>(null);
    const audioContextRef = useRef<AudioContext | null>(null);
    const workletNodeRef = useRef<AudioWorkletNode | null>(null);
    const processorRef = useRef<ScriptProcessorNode | null>(null);

    const cleanup = useCallback(() => {
        // Stop media stream
        if (mediaStreamRef.current) {
            mediaStreamRef.current.getTracks().forEach((track) => track.stop());
            mediaStreamRef.current = null;
        }

        // Close audio context
        if (audioContextRef.current) {
            audioContextRef.current.close();
            audioContextRef.current = null;
        }

        // Disconnect processor
        if (processorRef.current) {
            processorRef.current.disconnect();
            processorRef.current = null;
        }

        // Close WebSocket
        if (wsRef.current) {
            try {
                wsRef.current.send(JSON.stringify({ type: "stop" }));
            } catch {
                // Ignore errors when sending stop message
            }
            wsRef.current.close();
            wsRef.current = null;
        }

        setIsListening(false);
        setInterimTranscript("");
    }, []);

    const startListening = useCallback(async () => {
        try {
            setError(null);
            setInterimTranscript("");

            // Request microphone access
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    sampleRate: 16000,
                    echoCancellation: true,
                    noiseSuppression: true,
                },
            });
            mediaStreamRef.current = stream;

            // Create WebSocket connection
            const ws = new WebSocket(wsUrl);
            wsRef.current = ws;

            // Handle WebSocket messages
            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);

                    switch (data.type) {
                        case "ready":
                            console.log("Speech-to-text session ready");
                            break;

                        case "interim":
                            setInterimTranscript(data.transcript);
                            onInterimResult?.(data.transcript);
                            break;

                        case "final":
                            setInterimTranscript("");
                            onFinalResult?.(data.transcript);
                            break;

                        case "error":
                            console.error("Speech-to-text error:", data.message);
                            setError(data.message);
                            onError?.(data.message);
                            break;

                        case "stopped":
                            console.log("Speech-to-text session stopped");
                            break;
                    }
                } catch (e) {
                    console.error("Error parsing WebSocket message:", e);
                }
            };

            ws.onerror = (event) => {
                console.error("WebSocket error:", event);
                setError("WebSocket connection error");
                onError?.("WebSocket connection error");
                cleanup();
            };

            ws.onclose = () => {
                console.log("WebSocket closed");
                cleanup();
            };

            // Wait for WebSocket to open
            await new Promise<void>((resolve, reject) => {
                ws.onopen = () => {
                    console.log("WebSocket connected");
                    resolve();
                };
                ws.onerror = () => reject(new Error("WebSocket connection failed"));
            });

            // Send start message
            ws.send(JSON.stringify({ type: "start", language }));

            // Set up audio processing
            const audioContext = new AudioContext({ sampleRate: 16000 });
            audioContextRef.current = audioContext;

            const source = audioContext.createMediaStreamSource(stream);

            // Use ScriptProcessorNode (deprecated but more widely supported)
            // In the future, we should use AudioWorklet for better performance
            const bufferSize = 4096;
            const processor = audioContext.createScriptProcessor(bufferSize, 1, 1);
            processorRef.current = processor;

            processor.onaudioprocess = (e) => {
                if (wsRef.current?.readyState !== WebSocket.OPEN) return;

                const inputData = e.inputBuffer.getChannelData(0);

                // Convert Float32Array to Int16Array (LINEAR16 format)
                const int16Data = new Int16Array(inputData.length);
                for (let i = 0; i < inputData.length; i++) {
                    // Clamp and convert to 16-bit integer
                    const s = Math.max(-1, Math.min(1, inputData[i]));
                    int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
                }

                // Send audio data as binary
                wsRef.current.send(int16Data.buffer);
            };

            source.connect(processor);
            processor.connect(audioContext.destination);

            setIsListening(true);
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : "Failed to start speech recognition";
            console.error("Error starting speech recognition:", err);
            setError(errorMessage);
            onError?.(errorMessage);
            cleanup();
        }
    }, [wsUrl, language, onInterimResult, onFinalResult, onError, cleanup]);

    const stopListening = useCallback(() => {
        cleanup();
    }, [cleanup]);

    return {
        isListening,
        interimTranscript,
        startListening,
        stopListening,
        error,
    };
}
