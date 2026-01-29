/**
 * DeviceMirrorMSE - Low-Latency Android Screen Streaming via MSE
 * 
 * This component receives fragmented MP4 (fMP4) over WebSocket and plays it
 * using Media Source Extensions (MSE) for minimal latency.
 * 
 * Data Flow:
 *   WebSocket (binary) → ArrayBuffer queue → SourceBuffer → <video>
 * 
 * Key Design Decisions:
 * 1. Queue-based append to handle SourceBuffer.updating state
 * 2. Aggressive buffer trimming to minimize latency
 * 3. playbackRate adjustment to catch up when behind
 * 4. Proper error recovery for QuotaExceededError
 * 
 * @author Generated for production use
 */

import { useEffect, useRef, useState, useCallback } from "react";
import {
    WifiOff,
    ChevronLeft,
    Square,
    Maximize2,
    Minimize2,
    Volume2,
    VolumeX,
    Activity,
    Play,
    Pause
} from "lucide-react";
import { cn } from "@/lib/utils";

// =============================================================================
// Types
// =============================================================================

interface DeviceInfo {
    width: number;
    height: number;
    codec?: string;
    mode?: string;
}

type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error';

// MSE state for debugging
interface MSEState {
    readyState: string;
    buffered: string;
    currentTime: number;
    paused: boolean;
}

// =============================================================================
// Configuration
// =============================================================================

const CONFIG = {
    WS_URL: 'ws://localhost:8080',

    // MSE codec string for H.264 Baseline Profile, Level 3.0
    // This matches what adb screenrecord typically outputs
    CODEC: 'video/mp4; codecs="avc1.42E01E"',

    // Buffer management
    // Keep only ~1 second of buffer to minimize latency
    MAX_BUFFER_SECONDS: 1.0,

    // How far behind live edge before we start catching up
    LATENCY_THRESHOLD_SECONDS: 0.5,

    // Playback rate when catching up
    CATCHUP_RATE: 1.05,

    // Queue size limits
    MAX_QUEUE_SIZE: 100,     // Max pending chunks in queue

    // Stats update interval
    STATS_INTERVAL_MS: 1000
};

// =============================================================================
// Component
// =============================================================================

export const DeviceMirrorMSE = () => {
    // Refs
    const videoRef = useRef<HTMLVideoElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const wsRef = useRef<WebSocket | null>(null);
    const mediaSourceRef = useRef<MediaSource | null>(null);
    const sourceBufferRef = useRef<SourceBuffer | null>(null);

    // Queue of chunks waiting to be appended
    const chunkQueueRef = useRef<ArrayBuffer[]>([]);
    const isAppendingRef = useRef(false);

    // Ping/latency measurement
    const pingStartRef = useRef<number>(0);
    const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);

    // Touch handling
    const touchStartRef = useRef<{ x: number; y: number; time: number } | null>(null);

    // State
    const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
    const [error, setError] = useState<string | null>(null);
    const [deviceInfo, setDeviceInfo] = useState<DeviceInfo | null>(null);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [latency, setLatency] = useState<number | null>(null);
    const [volume, setVolume] = useState<{ level: number; max: number }>({ level: 0, max: 100 });
    const [isPaused, setIsPaused] = useState(false);

    // Stats
    const [stats, setStats] = useState({
        bytesReceived: 0,
        chunksReceived: 0,
        chunksAppended: 0,
        queueSize: 0,
        bufferLength: 0,
        videoTime: 0,
        droppedFrames: 0
    });

    // ==========================================================================
    // MSE Setup and Buffer Management
    // ==========================================================================

    /**
     * Initialize MediaSource and attach to video element
     */
    const initMediaSource = useCallback(() => {
        if (!videoRef.current) return;

        console.log('[MSE] Initializing MediaSource...');

        const mediaSource = new MediaSource();
        mediaSourceRef.current = mediaSource;

        // Attach MediaSource to video element via object URL
        videoRef.current.src = URL.createObjectURL(mediaSource);

        mediaSource.addEventListener('sourceopen', () => {
            console.log('[MSE] MediaSource opened');

            // Check if codec is supported
            if (!MediaSource.isTypeSupported(CONFIG.CODEC)) {
                console.error('[MSE] Codec not supported:', CONFIG.CODEC);
                setError(`Codec not supported: ${CONFIG.CODEC}`);
                setConnectionState('error');
                return;
            }

            try {
                // Create SourceBuffer for video
                const sourceBuffer = mediaSource.addSourceBuffer(CONFIG.CODEC);
                sourceBufferRef.current = sourceBuffer;

                // Set append mode for live streaming
                // 'sequence' mode is better for live as it handles timing automatically
                sourceBuffer.mode = 'segments';

                console.log('[MSE] SourceBuffer created with codec:', CONFIG.CODEC);

                // Handle updateend to process queue
                sourceBuffer.addEventListener('updateend', () => {
                    isAppendingRef.current = false;
                    processQueue();
                    trimBuffer();
                });

                sourceBuffer.addEventListener('error', (e) => {
                    console.error('[MSE] SourceBuffer error:', e);
                });

            } catch (e) {
                console.error('[MSE] Failed to create SourceBuffer:', e);
                setError('Failed to create SourceBuffer');
                setConnectionState('error');
            }
        });

        mediaSource.addEventListener('sourceended', () => {
            console.log('[MSE] MediaSource ended');
        });

        mediaSource.addEventListener('sourceclose', () => {
            console.log('[MSE] MediaSource closed');
        });
    }, []);

    /**
     * Append a chunk to the SourceBuffer
     * Uses a queue to handle the async nature of SourceBuffer.appendBuffer
     */
    const appendChunk = useCallback((data: ArrayBuffer) => {
        if (!sourceBufferRef.current) {
            console.warn('[MSE] No SourceBuffer available');
            return;
        }

        // Add to queue
        chunkQueueRef.current.push(data);

        // Update stats
        setStats(prev => ({
            ...prev,
            bytesReceived: prev.bytesReceived + data.byteLength,
            chunksReceived: prev.chunksReceived + 1,
            queueSize: chunkQueueRef.current.length
        }));

        // Prevent queue from growing too large (memory protection)
        if (chunkQueueRef.current.length > CONFIG.MAX_QUEUE_SIZE) {
            console.warn('[MSE] Queue overflow, dropping old chunks');
            chunkQueueRef.current = chunkQueueRef.current.slice(-CONFIG.MAX_QUEUE_SIZE / 2);
        }

        // Start processing if not already
        processQueue();
    }, []);

    /**
     * Process the chunk queue
     * Only appends when SourceBuffer is not updating
     */
    const processQueue = useCallback(() => {
        const sourceBuffer = sourceBufferRef.current;
        const mediaSource = mediaSourceRef.current;

        if (!sourceBuffer || !mediaSource) return;
        if (isAppendingRef.current) return;
        if (mediaSource.readyState !== 'open') return;
        if (sourceBuffer.updating) return;
        if (chunkQueueRef.current.length === 0) return;

        const chunk = chunkQueueRef.current.shift();
        if (!chunk) return;

        isAppendingRef.current = true;

        try {
            sourceBuffer.appendBuffer(chunk);

            setStats(prev => ({
                ...prev,
                chunksAppended: prev.chunksAppended + 1,
                queueSize: chunkQueueRef.current.length
            }));

        } catch (e: unknown) {
            isAppendingRef.current = false;

            if (e instanceof DOMException && e.name === 'QuotaExceededError') {
                console.warn('[MSE] QuotaExceededError - buffer full, trimming...');

                // Emergency buffer trim
                if (!sourceBuffer.updating) {
                    try {
                        const buffered = sourceBuffer.buffered;
                        if (buffered.length > 0) {
                            const removeEnd = buffered.start(0) + 1; // Remove first second
                            sourceBuffer.remove(buffered.start(0), removeEnd);
                        }
                    } catch {
                        console.error('[MSE] Failed to trim buffer');
                    }
                }

                // Re-queue the chunk
                chunkQueueRef.current.unshift(chunk);

            } else {
                console.error('[MSE] appendBuffer error:', e);
            }
        }
    }, []);

    /**
     * Trim old data from the buffer to minimize latency
     * Keep only the last MAX_BUFFER_SECONDS of data
     */
    const trimBuffer = useCallback(() => {
        const sourceBuffer = sourceBufferRef.current;
        const video = videoRef.current;

        if (!sourceBuffer || !video || sourceBuffer.updating) return;

        try {
            const buffered = sourceBuffer.buffered;
            if (buffered.length === 0) return;

            const bufferEnd = buffered.end(buffered.length - 1);
            const bufferStart = buffered.start(0);
            const currentTime = video.currentTime;

            // Calculate how much buffer we have ahead
            const bufferAhead = bufferEnd - currentTime;

            // Remove old data (before currentTime - small safety margin)
            const removeEnd = currentTime - 0.5; // Keep 0.5s behind playhead
            if (removeEnd > bufferStart) {
                sourceBuffer.remove(bufferStart, removeEnd);
            }

            // Update buffer stats
            setStats(prev => ({
                ...prev,
                bufferLength: bufferAhead,
                videoTime: currentTime
            }));

        } catch (e) {
            // Ignore trim errors
        }
    }, []);

    /**
     * Manage playback to minimize latency
     * - Seek to live edge if too far behind
     * - Speed up playback slightly to catch up
     */
    const managePlayback = useCallback(() => {
        const video = videoRef.current;
        const sourceBuffer = sourceBufferRef.current;

        if (!video || !sourceBuffer || video.paused) return;

        try {
            const buffered = sourceBuffer.buffered;
            if (buffered.length === 0) return;

            const bufferEnd = buffered.end(buffered.length - 1);
            const currentTime = video.currentTime;
            const latency = bufferEnd - currentTime;

            // If we're too far behind, seek to near-live
            if (latency > CONFIG.MAX_BUFFER_SECONDS) {
                console.log(`[PLAYBACK] Too far behind (${latency.toFixed(2)}s), seeking to live...`);
                video.currentTime = bufferEnd - 0.1;
                video.playbackRate = 1.0;
            }
            // If we're a bit behind, speed up slightly
            else if (latency > CONFIG.LATENCY_THRESHOLD_SECONDS) {
                video.playbackRate = CONFIG.CATCHUP_RATE;
            }
            // If we're at live edge, normal speed
            else {
                video.playbackRate = 1.0;
            }

        } catch {
            // Ignore
        }
    }, []);

    // ==========================================================================
    // WebSocket Connection
    // ==========================================================================

    const connect = useCallback(() => {
        setError(null);
        setConnectionState('connecting');

        // Reset stats
        setStats({
            bytesReceived: 0,
            chunksReceived: 0,
            chunksAppended: 0,
            queueSize: 0,
            bufferLength: 0,
            videoTime: 0,
            droppedFrames: 0
        });

        // Clear queue
        chunkQueueRef.current = [];
        isAppendingRef.current = false;

        // Initialize MSE
        initMediaSource();

        try {
            const ws = new WebSocket(CONFIG.WS_URL);
            wsRef.current = ws;
            ws.binaryType = 'arraybuffer';

            ws.onopen = () => {
                console.log('[WS] Connected');
                setConnectionState('connected');

                // Start ping interval
                pingIntervalRef.current = setInterval(() => {
                    if (ws.readyState === WebSocket.OPEN) {
                        pingStartRef.current = performance.now();
                        ws.send(JSON.stringify({ type: 'ping' }));
                    }

                    // Manage playback
                    managePlayback();

                }, CONFIG.STATS_INTERVAL_MS);
            };

            ws.onmessage = (event) => {
                // JSON message
                if (typeof event.data === 'string') {
                    try {
                        const data = JSON.parse(event.data);

                        switch (data.type) {
                            case 'device_info':
                                console.log('[WS] Device info:', data);
                                setDeviceInfo({
                                    width: data.width,
                                    height: data.height,
                                    codec: data.codec,
                                    mode: data.mode
                                });
                                break;

                            case 'volume_info':
                                setVolume({ level: data.level, max: data.max });
                                break;

                            case 'pong':
                                setLatency(Math.round(performance.now() - pingStartRef.current));
                                break;

                            case 'error':
                                setError(data.message);
                                setConnectionState('error');
                                break;

                            case 'stats':
                                console.log('[WS] Server stats:', data);
                                break;
                        }
                    } catch {
                        // Ignore parse errors
                    }
                    return;
                }

                // Binary message = fMP4 chunk
                if (event.data instanceof ArrayBuffer) {
                    appendChunk(event.data);

                    // Try to start playing once we have data
                    const video = videoRef.current;
                    if (video && video.paused && !isPaused) {
                        video.play().catch((e) => {
                            console.warn('[VIDEO] Autoplay blocked:', e.message);
                        });
                    }
                }
            };

            ws.onclose = () => {
                console.log('[WS] Disconnected');
                setConnectionState('disconnected');
                cleanup();
            };

            ws.onerror = () => {
                setError('WebSocket connection failed');
                setConnectionState('error');
            };

        } catch (e) {
            setError('Failed to connect');
            setConnectionState('error');
        }
    }, [initMediaSource, appendChunk, managePlayback, isPaused]);

    const disconnect = useCallback(() => {
        cleanup();
        wsRef.current?.close();
        setConnectionState('disconnected');
    }, []);

    const cleanup = useCallback(() => {
        if (pingIntervalRef.current) {
            clearInterval(pingIntervalRef.current);
            pingIntervalRef.current = null;
        }

        // Clean up MSE
        if (sourceBufferRef.current && mediaSourceRef.current?.readyState === 'open') {
            try {
                mediaSourceRef.current.removeSourceBuffer(sourceBufferRef.current);
            } catch {
                // Ignore
            }
        }
        sourceBufferRef.current = null;
        mediaSourceRef.current = null;

        // Revoke object URL
        if (videoRef.current?.src) {
            URL.revokeObjectURL(videoRef.current.src);
        }

        // Clear queue
        chunkQueueRef.current = [];
    }, []);

    // Auto-connect on mount
    useEffect(() => {
        connect();
        return () => disconnect();
    }, []);

    // Track dropped frames
    useEffect(() => {
        const video = videoRef.current;
        if (!video) return;

        const updateDroppedFrames = () => {
            // @ts-ignore - webkitDecodedFrameCount is non-standard
            const quality = video.getVideoPlaybackQuality?.();
            if (quality) {
                setStats(prev => ({
                    ...prev,
                    droppedFrames: quality.droppedVideoFrames
                }));
            }
        };

        const interval = setInterval(updateDroppedFrames, 1000);
        return () => clearInterval(interval);
    }, []);

    // ==========================================================================
    // Input Handling
    // ==========================================================================

    const sendCommand = useCallback((command: object) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(command));
        }
    }, []);

    const getNormalizedCoords = useCallback((clientX: number, clientY: number) => {
        const video = videoRef.current;
        if (!video || !deviceInfo) return null;

        const rect = video.getBoundingClientRect();
        const videoAspect = deviceInfo.width / deviceInfo.height;
        const containerAspect = rect.width / rect.height;

        let renderedWidth, renderedHeight, offsetX, offsetY;

        if (containerAspect > videoAspect) {
            renderedHeight = rect.height;
            renderedWidth = renderedHeight * videoAspect;
            offsetX = (rect.width - renderedWidth) / 2;
            offsetY = 0;
        } else {
            renderedWidth = rect.width;
            renderedHeight = renderedWidth / videoAspect;
            offsetX = 0;
            offsetY = (rect.height - renderedHeight) / 2;
        }

        const posX = clientX - rect.left - offsetX;
        const posY = clientY - rect.top - offsetY;

        if (posX < 0 || posX > renderedWidth || posY < 0 || posY > renderedHeight) {
            return null;
        }

        return {
            x: Math.max(0, Math.min(1, posX / renderedWidth)),
            y: Math.max(0, Math.min(1, posY / renderedHeight))
        };
    }, [deviceInfo]);

    const handleStart = useCallback((clientX: number, clientY: number) => {
        const coords = getNormalizedCoords(clientX, clientY);
        if (coords) {
            touchStartRef.current = { x: coords.x, y: coords.y, time: Date.now() };
        }
    }, [getNormalizedCoords]);

    const handleEnd = useCallback((clientX: number, clientY: number) => {
        if (!touchStartRef.current) return;
        const coords = getNormalizedCoords(clientX, clientY);
        if (!coords) return;

        const duration = Date.now() - touchStartRef.current.time;
        const dx = coords.x - touchStartRef.current.x;
        const dy = coords.y - touchStartRef.current.y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        if (distance > 0.03) {
            sendCommand({
                type: 'swipe',
                startX: touchStartRef.current.x,
                startY: touchStartRef.current.y,
                endX: coords.x,
                endY: coords.y,
                duration: Math.min(duration, 500)
            });
        } else {
            sendCommand({ type: 'tap', x: coords.x, y: coords.y });
        }
        touchStartRef.current = null;
    }, [sendCommand, getNormalizedCoords]);

    const handleMouseDown = (e: React.MouseEvent) => { e.preventDefault(); handleStart(e.clientX, e.clientY); };
    const handleMouseUp = (e: React.MouseEvent) => { e.preventDefault(); handleEnd(e.clientX, e.clientY); };
    const handleTouchStart = (e: React.TouchEvent) => handleStart(e.touches[0].clientX, e.touches[0].clientY);
    const handleTouchEnd = (e: React.TouchEvent) => handleEnd(e.changedTouches[0].clientX, e.changedTouches[0].clientY);

    const handleBack = () => sendCommand({ type: 'key', keycode: 'back' });
    const handleHome = () => sendCommand({ type: 'key', keycode: 'home' });
    const handleRecent = () => sendCommand({ type: 'key', keycode: 'recent' });
    const handleVolumeUp = () => sendCommand({ type: 'key', keycode: 'volume_up' });
    const handleVolumeDown = () => sendCommand({ type: 'key', keycode: 'volume_down' });

    const togglePlayPause = () => {
        const video = videoRef.current;
        if (!video) return;

        if (video.paused) {
            video.play();
            setIsPaused(false);
        } else {
            video.pause();
            setIsPaused(true);
        }
    };

    const toggleFullscreen = () => {
        if (!containerRef.current) return;
        if (!document.fullscreenElement) {
            containerRef.current.requestFullscreen();
            setIsFullscreen(true);
        } else {
            document.exitFullscreen();
            setIsFullscreen(false);
        }
    };

    useEffect(() => {
        const h = () => setIsFullscreen(!!document.fullscreenElement);
        document.addEventListener('fullscreenchange', h);
        return () => document.removeEventListener('fullscreenchange', h);
    }, []);

    // ==========================================================================
    // Render
    // ==========================================================================

    const connectionText = {
        disconnected: 'Disconnected',
        connecting: 'Initializing MSE...',
        connected: 'H.264/fMP4 Stream',
        error: 'Stream Failed'
    }[connectionState];

    return (
        <div ref={containerRef} className="flex flex-col h-full relative bg-[#0a0a0c] border-l border-white/5 overflow-hidden">
            <div className="absolute inset-0 mesh-gradient opacity-10 z-0" />

            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 relative z-10 border-b border-white/[0.03]">
                <div className="flex items-center gap-3">
                    <div className={cn(
                        "w-2 h-2 rounded-full transition-all duration-500",
                        connectionState === 'connected' ? "bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)] animate-pulse" :
                            connectionState === 'error' ? "bg-brand-pink shadow-[0_0_10px_rgba(255,46,144,0.5)]" : "bg-white/10"
                    )} />
                    <div>
                        <h2 className="text-[10px] font-black text-white uppercase tracking-[0.4em] leading-none flex items-center gap-2">
                            MSE Stream
                            {connectionState === 'connected' && <Activity className="h-3 w-3 text-emerald-400 animate-pulse" />}
                        </h2>
                        <p className="text-[8px] font-bold text-white/20 uppercase tracking-widest mt-1">{connectionText}</p>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {/* Queue size */}
                    {stats.queueSize > 0 && (
                        <div className="px-2 py-0.5 rounded-md bg-yellow-900/20 border border-yellow-500/20">
                            <span className="text-[8px] font-black text-yellow-400/60 uppercase tracking-tighter">
                                Q: {stats.queueSize}
                            </span>
                        </div>
                    )}

                    {/* Buffer length */}
                    <div className="px-2 py-0.5 rounded-md bg-white/[0.03] border border-white/5">
                        <span className="text-[8px] font-black text-emerald-400/60 uppercase tracking-tighter">
                            BUF: {stats.bufferLength.toFixed(2)}s
                        </span>
                    </div>

                    {/* Latency */}
                    {latency !== null && latency > 0 && (
                        <div className="px-2 py-0.5 rounded-md bg-white/[0.03] border border-white/5">
                            <span className="text-[8px] font-black text-blue-400/60 uppercase tracking-tighter">
                                {latency}ms
                            </span>
                        </div>
                    )}

                    {/* Data received */}
                    <div className="px-2 py-0.5 rounded-md bg-white/[0.03] border border-white/5">
                        <span className="text-[8px] font-black text-purple-400/60 uppercase tracking-tighter">
                            {(stats.bytesReceived / 1024 / 1024).toFixed(1)}MB
                        </span>
                    </div>

                    {/* Play/Pause */}
                    <button onClick={togglePlayPause} className="p-2 rounded-lg text-white/20 hover:text-white transition-colors">
                        {isPaused ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
                    </button>

                    {/* Fullscreen */}
                    <button onClick={toggleFullscreen} className="p-2 rounded-lg text-white/20 hover:text-white transition-colors">
                        {isFullscreen ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
                    </button>
                </div>
            </div>

            {/* Video Stream Area */}
            <div className="flex-1 flex items-center justify-center p-6 relative z-10 overflow-hidden">
                <div
                    className="relative w-full max-w-[380px] group/frame transition-all duration-700 ease-in-out"
                    style={{
                        aspectRatio: deviceInfo && deviceInfo.width > 0
                            ? `${deviceInfo.width} / ${deviceInfo.height - 100}`
                            : '9/19'
                    }}
                >
                    {/* External Glow */}
                    <div className="absolute inset-0 bg-brand-pink/5 blur-[100px] rounded-[3rem] opacity-0 group-hover/frame:opacity-100 transition-opacity duration-1000" />

                    {/* Phone Frame */}
                    <div className="relative w-full h-full rounded-[3rem] bg-black p-[2px] shadow-2xl ring-1 ring-white/10 transition-transform duration-500 hover:scale-[1.01]">
                        {/* Inner Shell */}
                        <div className="w-full h-full rounded-[2.9rem] bg-zinc-900/50 backdrop-blur-3xl p-2 relative overflow-hidden border border-white/10">
                            {/* Screen Container */}
                            <div className="w-full h-full rounded-[2rem] bg-black overflow-hidden relative border border-white/5">
                                {connectionState === 'connected' ? (
                                    <video
                                        ref={videoRef}
                                        className="w-full h-full object-contain cursor-crosshair relative z-10"
                                        autoPlay
                                        muted
                                        playsInline
                                        onMouseDown={handleMouseDown}
                                        onMouseUp={handleMouseUp}
                                        onTouchStart={handleTouchStart}
                                        onTouchEnd={handleTouchEnd}
                                    />
                                ) : (
                                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-zinc-950 z-30 p-8 text-center">
                                        <div className="relative mb-8">
                                            <div className="w-16 h-16 rounded-3xl bg-white/[0.03] border border-white/5 flex items-center justify-center relative overflow-hidden">
                                                <div className="absolute inset-0 bg-gradient-to-t from-brand-pink/10 to-transparent animate-pulse" />
                                                <WifiOff className="h-6 w-6 text-white/20" />
                                            </div>
                                            {connectionState === 'connecting' && (
                                                <div className="absolute -inset-4 border border-brand-pink/30 rounded-full animate-ping opacity-20" />
                                            )}
                                        </div>
                                        <div className="space-y-2 mb-8">
                                            <h3 className="text-sm font-black text-white uppercase tracking-widest">
                                                {connectionState === 'connecting' ? 'Initializing MSE Pipeline' : 'Stream Offline'}
                                            </h3>
                                            <p className="text-[10px] text-white/30 uppercase font-black tracking-tighter leading-relaxed">
                                                {error || "Connect device via USB debugging"}
                                            </p>
                                        </div>
                                        <button
                                            onClick={connect}
                                            disabled={connectionState === 'connecting'}
                                            className="w-full py-3 rounded-xl bg-white text-black text-[9px] font-black uppercase tracking-widest hover:bg-zinc-200 transition-all disabled:opacity-50"
                                        >
                                            {connectionState === 'connecting' ? "Connecting..." : "Initialize Stream"}
                                        </button>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Physical Buttons Simulation */}
                        <div className="absolute -left-[3px] top-24 w-[3px] h-8 bg-zinc-800 rounded-l-sm border-l border-white/10" />
                        <div className="absolute -left-[3px] top-36 w-[3px] h-12 bg-zinc-800 rounded-l-sm border-l border-white/10" />
                        <div className="absolute -left-[3px] top-52 w-[3px] h-12 bg-zinc-800 rounded-l-sm border-l border-white/10" />
                        <div className="absolute -right-[3px] top-40 w-[3px] h-16 bg-zinc-800 rounded-r-sm border-r border-white/10" />
                    </div>
                </div>
            </div>

            {/* Navigation & Controls */}
            <div className="px-6 pb-8 space-y-6 relative z-10">
                <div className="bg-black/40 backdrop-blur-xl border border-white/5 rounded-2xl flex items-center h-14 overflow-hidden shadow-2xl">
                    <button onClick={handleBack} className="flex-1 h-full flex items-center justify-center hover:bg-white/5 transition-all group border-r border-white/5">
                        <ChevronLeft className="h-5 w-5 text-white/20 group-hover:text-white transition-colors" />
                    </button>
                    <button onClick={handleHome} className="flex-1 h-full flex items-center justify-center hover:bg-white/5 transition-all group border-r border-white/5">
                        <div className="w-5 h-5 rounded-full border-2 border-white/20 group-hover:border-white transition-colors" />
                    </button>
                    <button onClick={handleRecent} className="flex-1 h-full flex items-center justify-center hover:bg-white/5 transition-all group">
                        <Square className="h-4.5 w-4.5 text-white/20 group-hover:text-white transition-colors" />
                    </button>
                </div>

                <div className="px-2">
                    <div className="flex items-center gap-4 group/vol">
                        <button onClick={handleVolumeDown} className="text-white/20 hover:text-white transition-colors">
                            <VolumeX className="h-4 w-4" />
                        </button>
                        <div className="flex-1 h-1.5 bg-white/5 rounded-full relative overflow-hidden group-hover/vol:bg-white/10 transition-colors">
                            <div
                                className="absolute inset-y-0 left-0 bg-white/20 rounded-full transition-all duration-300"
                                style={{ width: `${(volume.level / volume.max) * 100}%` }}
                            />
                            <div
                                className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow-lg opacity-0 group-hover/vol:opacity-100 transition-all duration-300"
                                style={{ left: `${(volume.level / volume.max) * 100}%`, transform: 'translate(-50%, -50%)' }}
                            />
                        </div>
                        <button onClick={handleVolumeUp} className="text-white/20 hover:text-white transition-colors">
                            <Volume2 className="h-4 w-4" />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default DeviceMirrorMSE;
