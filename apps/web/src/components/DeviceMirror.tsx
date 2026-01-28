import { useEffect, useRef, useState, useCallback } from "react";
import JMuxer from "jmuxer";
import { 
    Smartphone, 
    RefreshCw, 
    AlertCircle, 
    Wifi, 
    WifiOff,
    Home,
    ChevronLeft,
    Square,
    Maximize2,
    Minimize2,
    Volume2,
    VolumeX,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface DeviceInfo {
    width: number;
    height: number;
}

type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error';

export const DeviceMirror = () => {
    const videoRef = useRef<HTMLVideoElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
    const [error, setError] = useState<string | null>(null);
    const [deviceInfo, setDeviceInfo] = useState<DeviceInfo | null>(null);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [latency, setLatency] = useState<number | null>(null);
    const wsRef = useRef<WebSocket | null>(null);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const jmuxerRef = useRef<any>(null);
    const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
    const pingStartRef = useRef<number>(0);

    // Touch state for gesture detection
    const touchStartRef = useRef<{ x: number; y: number; time: number } | null>(null);

    const connect = useCallback(() => {
        setError(null);
        setConnectionState('connecting');

        try {
            const ws = new WebSocket("ws://localhost:8080");
            wsRef.current = ws;
            ws.binaryType = "arraybuffer";

            ws.onopen = () => {
                setConnectionState('connected');
                console.log("Connected to screen mirror service");

                if (videoRef.current && !jmuxerRef.current) {
                    jmuxerRef.current = new JMuxer({
                        node: videoRef.current,
                        mode: "video",
                        flushingTime: 0,
                        fps: 60,
                        debug: false,
                    });
                }

                // Start ping interval for latency measurement
                pingIntervalRef.current = setInterval(() => {
                    if (ws.readyState === WebSocket.OPEN) {
                        pingStartRef.current = performance.now();
                        ws.send(JSON.stringify({ type: 'ping' }));
                    }
                }, 2000);
            };

            ws.onmessage = (event) => {
                // Handle JSON messages (control responses)
                if (typeof event.data === 'string') {
                    try {
                        const data = JSON.parse(event.data);
                        if (data.type === 'device_info') {
                            setDeviceInfo({ width: data.width, height: data.height });
                        } else if (data.type === 'pong') {
                            setLatency(Math.round(performance.now() - pingStartRef.current));
                        } else if (data.type === 'error') {
                            setError(data.message);
                            setConnectionState('error');
                        } else if (data.type === 'disconnected') {
                            setConnectionState('disconnected');
                        }
                    } catch {
                        // Not JSON, ignore
                    }
                    return;
                }

                // Handle binary video data
                if (jmuxerRef.current && event.data instanceof ArrayBuffer) {
                    jmuxerRef.current.feed({
                        video: new Uint8Array(event.data),
                    });
                }
            };

            ws.onclose = () => {
                setConnectionState('disconnected');
                console.log("Disconnected from screen mirror service");
                cleanup();
            };

            ws.onerror = () => {
                console.error("WebSocket error");
                setError("Failed to connect to mirror service. Is it running?");
                setConnectionState('error');
            };
        } catch (e) {
            setError("Failed to initialize connection.");
            setConnectionState('error');
        }
    }, []);

    const cleanup = useCallback(() => {
        if (pingIntervalRef.current) {
            clearInterval(pingIntervalRef.current);
            pingIntervalRef.current = null;
        }
        if (jmuxerRef.current) {
            jmuxerRef.current.destroy();
            jmuxerRef.current = null;
        }
    }, []);

    const disconnect = useCallback(() => {
        cleanup();
        wsRef.current?.close();
        setConnectionState('disconnected');
    }, [cleanup]);

    useEffect(() => {
        connect();
        return () => {
            cleanup();
            wsRef.current?.close();
        };
    }, [connect, cleanup]);

    // Send control command
    const sendCommand = useCallback((command: object) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(command));
        }
    }, []);

    // Handle tap on video canvas
    const handleVideoClick = useCallback((e: React.MouseEvent<HTMLVideoElement>) => {
        if (!videoRef.current || connectionState !== 'connected') return;

        const rect = videoRef.current.getBoundingClientRect();
        const x = (e.clientX - rect.left) / rect.width;
        const y = (e.clientY - rect.top) / rect.height;

        sendCommand({ type: 'tap', x, y });
    }, [connectionState, sendCommand]);

    // Handle touch start for swipe detection
    const handleTouchStart = useCallback((e: React.TouchEvent<HTMLVideoElement>) => {
        if (!videoRef.current) return;
        const touch = e.touches[0];
        const rect = videoRef.current.getBoundingClientRect();
        touchStartRef.current = {
            x: (touch.clientX - rect.left) / rect.width,
            y: (touch.clientY - rect.top) / rect.height,
            time: Date.now()
        };
    }, []);

    // Handle touch end for swipe detection
    const handleTouchEnd = useCallback((e: React.TouchEvent<HTMLVideoElement>) => {
        if (!videoRef.current || !touchStartRef.current) return;

        const touch = e.changedTouches[0];
        const rect = videoRef.current.getBoundingClientRect();
        const endX = (touch.clientX - rect.left) / rect.width;
        const endY = (touch.clientY - rect.top) / rect.height;
        const duration = Date.now() - touchStartRef.current.time;

        const dx = endX - touchStartRef.current.x;
        const dy = endY - touchStartRef.current.y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        if (distance > 0.05) {
            // It's a swipe
            sendCommand({
                type: 'swipe',
                startX: touchStartRef.current.x,
                startY: touchStartRef.current.y,
                endX,
                endY,
                duration: Math.min(duration, 500)
            });
        } else {
            // It's a tap
            sendCommand({ type: 'tap', x: endX, y: endY });
        }

        touchStartRef.current = null;
    }, [sendCommand]);

    // Navigation buttons
    const handleBack = () => sendCommand({ type: 'key', keycode: 'back' });
    const handleHome = () => sendCommand({ type: 'key', keycode: 'home' });
    const handleRecent = () => sendCommand({ type: 'key', keycode: 'recent' });
    const handleVolumeUp = () => sendCommand({ type: 'key', keycode: 'volume_up' });
    const handleVolumeDown = () => sendCommand({ type: 'key', keycode: 'volume_down' });

    // Toggle fullscreen
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
        const handleFullscreenChange = () => {
            setIsFullscreen(!!document.fullscreenElement);
        };
        document.addEventListener('fullscreenchange', handleFullscreenChange);
        return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
    }, []);

    const connectionColor = {
        disconnected: 'bg-gray-500',
        connecting: 'bg-yellow-500 animate-pulse',
        connected: 'bg-emerald-500',
        error: 'bg-red-500'
    }[connectionState];

    const connectionText = {
        disconnected: 'Disconnected',
        connecting: 'Connecting...',
        connected: 'Live',
        error: 'Error'
    }[connectionState];

    return (
        <div 
            ref={containerRef}
            className="flex flex-col h-full rounded-xl overflow-hidden relative group"
            style={{
                background: 'linear-gradient(180deg, hsl(240 10% 8%) 0%, hsl(280 15% 6%) 100%)',
                boxShadow: '0 0 0 1px hsl(340 40% 20% / 0.3), 0 8px 32px hsl(0 0% 0% / 0.4), inset 0 1px 0 hsl(340 40% 30% / 0.1)'
            }}
        >
            {/* Header */}
            <div className="px-3 py-2.5 flex items-center justify-between border-b border-white/5 bg-black/20 backdrop-blur-sm">
                <div className="flex items-center gap-2">
                    <div className="relative">
                        <Smartphone className="h-4 w-4 text-pink-400" />
                        <span className={cn(
                            "absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full ring-2 ring-gray-900",
                            connectionColor
                        )} />
                    </div>
                    <span className="text-sm font-medium text-gray-200 tracking-tight">
                        Android Mirror
                    </span>
                </div>
                <div className="flex items-center gap-3">
                    {latency !== null && connectionState === 'connected' && (
                        <span className="text-[10px] font-mono text-gray-500">
                            {latency}ms
                        </span>
                    )}
                    <div className="flex items-center gap-1.5">
                        {connectionState === 'connected' ? (
                            <Wifi className="h-3 w-3 text-emerald-400" />
                        ) : (
                            <WifiOff className="h-3 w-3 text-gray-500" />
                        )}
                        <span className="text-[11px] text-gray-400 font-medium">
                            {connectionText}
                        </span>
                    </div>
                </div>
            </div>

            {/* Video Area */}
            <div className="flex-1 relative flex items-center justify-center bg-black/60 overflow-hidden">
                {connectionState === 'error' ? (
                    <div className="p-6 max-w-xs text-center">
                        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-red-500/10 flex items-center justify-center">
                            <AlertCircle className="h-8 w-8 text-red-400" />
                        </div>
                        <h3 className="text-sm font-semibold text-gray-200 mb-2">Connection Error</h3>
                        <p className="text-xs text-gray-500 mb-4 leading-relaxed">
                            {error || "Unable to connect to the mirror service."}
                        </p>
                        <Button
                            variant="outline"
                            size="sm"
                            className="border-pink-500/30 hover:bg-pink-500/10 text-pink-400 hover:text-pink-300"
                            onClick={connect}
                        >
                            <RefreshCw className="mr-2 h-3 w-3" />
                            Retry Connection
                        </Button>
                    </div>
                ) : connectionState === 'connecting' ? (
                    <div className="text-center">
                        <div className="w-12 h-12 mx-auto mb-3 rounded-full border-2 border-pink-500/30 border-t-pink-500 animate-spin" />
                        <p className="text-sm text-gray-400">Connecting to device...</p>
                    </div>
                ) : connectionState === 'disconnected' ? (
                    <div className="p-6 max-w-xs text-center">
                        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gray-800/50 flex items-center justify-center border border-gray-700/50">
                            <Smartphone className="h-8 w-8 text-gray-500" />
                        </div>
                        <h3 className="text-sm font-semibold text-gray-300 mb-2">Device Disconnected</h3>
                        <p className="text-xs text-gray-500 mb-4">
                            Connect your Android device via USB or WiFi ADB.
                        </p>
                        <Button
                            size="sm"
                            className="bg-pink-600 hover:bg-pink-500 text-white"
                            onClick={connect}
                        >
                            <RefreshCw className="mr-2 h-3 w-3" />
                            Connect
                        </Button>
                    </div>
                ) : (
                    <video
                        ref={videoRef}
                        className="w-full h-full object-contain cursor-crosshair"
                        autoPlay
                        muted
                        playsInline
                        onClick={handleVideoClick}
                        onTouchStart={handleTouchStart}
                        onTouchEnd={handleTouchEnd}
                        style={{
                            aspectRatio: deviceInfo ? `${deviceInfo.width}/${deviceInfo.height}` : 'auto',
                        }}
                    />
                )}

                {/* Fullscreen toggle - appears on hover */}
                {connectionState === 'connected' && (
                    <button
                        onClick={toggleFullscreen}
                        className="absolute top-2 right-2 p-1.5 rounded-lg bg-black/60 hover:bg-black/80 text-gray-400 hover:text-white transition-all opacity-0 group-hover:opacity-100"
                    >
                        {isFullscreen ? (
                            <Minimize2 className="h-4 w-4" />
                        ) : (
                            <Maximize2 className="h-4 w-4" />
                        )}
                    </button>
                )}
            </div>

            {/* Navigation Controls */}
            {connectionState === 'connected' && (
                <div className="px-3 py-2.5 border-t border-white/5 bg-black/30">
                    <div className="flex items-center justify-between">
                        {/* Android Nav Buttons */}
                        <div className="flex items-center gap-1">
                            <button
                                onClick={handleBack}
                                className="p-2 rounded-lg hover:bg-white/5 text-gray-400 hover:text-white transition-colors"
                                title="Back"
                            >
                                <ChevronLeft className="h-5 w-5" />
                            </button>
                            <button
                                onClick={handleHome}
                                className="p-2 rounded-lg hover:bg-white/5 text-gray-400 hover:text-white transition-colors"
                                title="Home"
                            >
                                <Home className="h-5 w-5" />
                            </button>
                            <button
                                onClick={handleRecent}
                                className="p-2 rounded-lg hover:bg-white/5 text-gray-400 hover:text-white transition-colors"
                                title="Recent Apps"
                            >
                                <Square className="h-4 w-4" />
                            </button>
                        </div>

                        {/* Volume Controls */}
                        <div className="flex items-center gap-1">
                            <button
                                onClick={handleVolumeDown}
                                className="p-2 rounded-lg hover:bg-white/5 text-gray-400 hover:text-white transition-colors"
                                title="Volume Down"
                            >
                                <VolumeX className="h-4 w-4" />
                            </button>
                            <button
                                onClick={handleVolumeUp}
                                className="p-2 rounded-lg hover:bg-white/5 text-gray-400 hover:text-white transition-colors"
                                title="Volume Up"
                            >
                                <Volume2 className="h-4 w-4" />
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Decorative gradient overlay at bottom */}
            <div 
                className="absolute bottom-0 left-0 right-0 h-24 pointer-events-none"
                style={{
                    background: 'linear-gradient(to top, hsl(340 70% 45% / 0.05), transparent)'
                }}
            />
        </div>
    );
};
