import { useEffect, useRef, useState, useCallback } from "react";
import {
    WifiOff,
    ChevronLeft,
    Square,
    Maximize2,
    Minimize2,
    Volume2,
    VolumeX,
    Zap,
    Activity
} from "lucide-react";
import { cn } from "@/lib/utils";

interface DeviceInfo {
    width: number;
    height: number;
}

interface FrameMetadata {
    type: 'mjpeg_frame' | 'h264_frame';
    timestamp: number;
    size: number;
    processingTime?: number;
    isKeyframe?: boolean;
}

type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error';

export const DeviceMirror = () => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const imgRef = useRef<HTMLImageElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
    const [error, setError] = useState<string | null>(null);
    const [deviceInfo, setDeviceInfo] = useState<DeviceInfo | null>(null);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [latency, setLatency] = useState<number | null>(null);
    const [fps, setFps] = useState<number>(0);
    const [processingTime, setProcessingTime] = useState<number>(0);
    const [volume, setVolume] = useState<{ level: number; max: number }>({ level: 0, max: 100 });
    const [streamType, setStreamType] = useState<'mjpeg' | 'h264'>('mjpeg');

    const wsRef = useRef<WebSocket | null>(null);
    const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
    const pingStartRef = useRef<number>(0);
    const frameCountRef = useRef<number>(0);
    const lastFpsUpdateRef = useRef<number>(Date.now());
    const fpsHistoryRef = useRef<number[]>([]);
    const processingTimeHistoryRef = useRef<number[]>([]);

    // Frame metadata for binary data
    const pendingFrameRef = useRef<FrameMetadata | null>(null);

    // Touch state for gesture detection
    const touchStartRef = useRef<{ x: number; y: number; time: number } | null>(null);

    // ==========================================================================
    // Connection Management
    // ==========================================================================

    const cleanup = useCallback(() => {
        if (pingIntervalRef.current) {
            clearInterval(pingIntervalRef.current);
            pingIntervalRef.current = null;
        }
        // Revoke any blob URLs from img element
        if (imgRef.current?.src?.startsWith('blob:')) {
            URL.revokeObjectURL(imgRef.current.src);
        }
    }, []);

    const connect = useCallback(() => {
        setError(null);
        setConnectionState('connecting');
        frameCountRef.current = 0;
        lastFpsUpdateRef.current = Date.now();
        fpsHistoryRef.current = [];
        processingTimeHistoryRef.current = [];
        setFps(0);
        setProcessingTime(0);

        try {
            const ws = new WebSocket("ws://localhost:8080");
            wsRef.current = ws;
            ws.binaryType = "arraybuffer";

            ws.onopen = () => {
                setConnectionState('connected');
                console.log("Connected to mirror service");

                // Start ping/FPS interval
                pingIntervalRef.current = setInterval(() => {
                    if (ws.readyState === WebSocket.OPEN) {
                        pingStartRef.current = performance.now();
                        ws.send(JSON.stringify({ type: 'ping' }));
                    }

                    // Calculate FPS with smoothing
                    const now = Date.now();
                    const elapsed = (now - lastFpsUpdateRef.current) / 1000;
                    if (elapsed > 0) {
                        const currentFps = Math.round(frameCountRef.current / elapsed);

                        fpsHistoryRef.current.push(currentFps);
                        if (fpsHistoryRef.current.length > 5) {
                            fpsHistoryRef.current.shift();
                        }

                        const avgFps = Math.round(
                            fpsHistoryRef.current.reduce((a, b) => a + b, 0) / fpsHistoryRef.current.length
                        );

                        setFps(avgFps);
                        frameCountRef.current = 0;
                        lastFpsUpdateRef.current = now;

                        // Average processing time
                        if (processingTimeHistoryRef.current.length > 0) {
                            const avgPt = Math.round(
                                processingTimeHistoryRef.current.reduce((a, b) => a + b, 0) / processingTimeHistoryRef.current.length
                            );
                            setProcessingTime(avgPt);
                            processingTimeHistoryRef.current = [];
                        }
                    }
                }, 1000);
            };

            ws.onmessage = async (event) => {
                if (typeof event.data === 'string') {
                    try {
                        const data = JSON.parse(event.data);

                        if (data.type === 'device_info') {
                            setDeviceInfo({ width: data.width, height: data.height });
                        } else if (data.type === 'volume_info') {
                            setVolume({ level: data.level, max: data.max });
                        } else if (data.type === 'pong') {
                            setLatency(Math.round(performance.now() - pingStartRef.current));
                        } else if (data.type === 'error') {
                            setError(data.message);
                            setConnectionState('error');
                        } else if (data.type === 'disconnected') {
                            setConnectionState('disconnected');
                        } else if (data.type === 'mjpeg_frame' || data.type === 'h264_frame') {
                            // Store frame metadata, wait for binary data
                            pendingFrameRef.current = data as FrameMetadata;
                            if (data.type === 'h264_frame') {
                                setStreamType('h264');
                            } else {
                                setStreamType('mjpeg');
                            }
                        }
                    } catch {
                        // ignore
                    }
                    return;
                }

                // Binary data = frame
                if (event.data instanceof ArrayBuffer && pendingFrameRef.current) {
                    const metadata = pendingFrameRef.current;
                    pendingFrameRef.current = null;

                    // Track processing time
                    if (metadata.processingTime) {
                        processingTimeHistoryRef.current.push(metadata.processingTime);
                        if (processingTimeHistoryRef.current.length > 10) {
                            processingTimeHistoryRef.current.shift();
                        }
                    }

                    // Handle MJPEG frame
                    if (metadata.type === 'mjpeg_frame' && imgRef.current) {
                        const blob = new Blob([event.data], { type: 'image/jpeg' });
                        const url = URL.createObjectURL(blob);

                        // Revoke previous blob URL to prevent memory leak
                        if (imgRef.current.src?.startsWith('blob:')) {
                            URL.revokeObjectURL(imgRef.current.src);
                        }

                        imgRef.current.src = url;
                        frameCountRef.current++;
                    }

                    // TODO: Handle H.264 frame with WebCodecs when server supports it
                    // if (metadata.type === 'h264_frame') { ... }
                }
            };

            ws.onclose = () => {
                setConnectionState('disconnected');
                cleanup();
            };

            ws.onerror = () => {
                setError("Failed to connect to mirror service.");
                setConnectionState('error');
            };
        } catch {
            setError("Failed to initialize connection.");
            setConnectionState('error');
        }
    }, [cleanup]);

    const disconnect = useCallback(() => {
        cleanup();
        wsRef.current?.close();
        setConnectionState('disconnected');
    }, [cleanup]);

    useEffect(() => {
        connect();
        return () => disconnect();
    }, [connect, disconnect]);

    // ==========================================================================
    // Input Handling
    // ==========================================================================

    const sendCommand = useCallback((command: object) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(command));
        }
    }, []);

    const getNormalizedCoords = useCallback((clientX: number, clientY: number) => {
        const element = imgRef.current || canvasRef.current;
        if (!element || !deviceInfo) return null;

        const rect = element.getBoundingClientRect();
        const naturalWidth = 'naturalWidth' in element ? element.naturalWidth : element.width;
        const naturalHeight = 'naturalHeight' in element ? element.naturalHeight : element.height;
        const imgAspect = (naturalWidth || deviceInfo.width) / (naturalHeight || deviceInfo.height);
        const containerAspect = rect.width / rect.height;

        let renderedWidth, renderedHeight, offsetX, offsetY;

        if (containerAspect > imgAspect) {
            renderedHeight = rect.height;
            renderedWidth = renderedHeight * imgAspect;
            offsetX = (rect.width - renderedWidth) / 2;
            offsetY = 0;
        } else {
            renderedWidth = rect.width;
            renderedHeight = renderedWidth / imgAspect;
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

    const connectionText = {
        disconnected: 'Disconnected',
        connecting: 'Connecting...',
        connected: `${streamType === 'h264' ? 'H.264' : 'MJPEG'} Stream`,
        error: 'System Link Failed'
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
                            Neural Interface
                            {connectionState === 'connected' && <Activity className="h-3 w-3 text-emerald-400 animate-pulse" />}
                        </h2>
                        <p className="text-[8px] font-bold text-white/20 uppercase tracking-widest mt-1">{connectionText}</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {fps > 0 && (
                        <div className="px-2 py-0.5 rounded-md bg-white/[0.03] border border-white/5">
                            <span className="text-[8px] font-black text-emerald-400/60 uppercase tracking-tighter">{fps} FPS</span>
                        </div>
                    )}
                    {/* {latency !== null && latency > 0 && (
                        <div className="px-2 py-0.5 rounded-md bg-white/[0.03] border border-white/5">
                            <span className="text-[8px] font-black text-blue-400/60 uppercase tracking-tighter">{latency}ms</span>
                        </div>
                    )} */}
                    {processingTime > 0 && (
                        <div className="px-2 py-0.5 rounded-md bg-white/[0.03] border border-white/5">
                            <span className="text-[8px] font-black text-purple-400/60 uppercase tracking-tighter">{processingTime}ms PT</span>
                        </div>
                    )}
                    <button onClick={toggleFullscreen} className="p-2 rounded-lg text-white/20 hover:text-white transition-colors">
                        {isFullscreen ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
                    </button>
                </div>
            </div>

            {/* Device Stream Area */}
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
                                    <>
                                        {/* MJPEG mode: use img element */}
                                        {streamType === 'mjpeg' && (
                                            <img
                                                ref={imgRef}
                                                className="w-full h-full object-contain cursor-crosshair relative z-10"
                                                alt="Live Stream"
                                                onMouseDown={handleMouseDown}
                                                onMouseUp={handleMouseUp}
                                                onTouchStart={handleTouchStart}
                                                onTouchEnd={handleTouchEnd}
                                                draggable={false}
                                            />
                                        )}
                                        {/* H.264 mode: use canvas for WebCodecs */}
                                        {streamType === 'h264' && (
                                            <canvas
                                                ref={canvasRef}
                                                className="w-full h-full object-contain cursor-crosshair relative z-10"
                                                onMouseDown={handleMouseDown}
                                                onMouseUp={handleMouseUp}
                                                onTouchStart={handleTouchStart}
                                                onTouchEnd={handleTouchEnd}
                                            />
                                        )}
                                    </>
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
                                                {connectionState === 'connecting' ? 'Establishing Link' : 'Core Offline'}
                                            </h3>
                                            <p className="text-[10px] text-white/30 uppercase font-black tracking-tighter leading-relaxed">
                                                {error || "Authorize ADB and check Neural status"}
                                            </p>
                                        </div>
                                        <button
                                            onClick={connect}
                                            disabled={connectionState === 'connecting'}
                                            className="w-full py-3 rounded-xl bg-white text-black text-[9px] font-black uppercase tracking-widest hover:bg-zinc-200 transition-all disabled:opacity-50"
                                        >
                                            {connectionState === 'connecting' ? "Connecting..." : "Initialize Link"}
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
