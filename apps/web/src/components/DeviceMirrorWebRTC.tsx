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
    Zap
} from "lucide-react";
import { cn } from "@/lib/utils";

interface DeviceInfo {
    width: number;
    height: number;
}

type ConnectionState = 'disconnected' | 'connecting' | 'signaling' | 'connected' | 'error';

const SIGNALING_URL = "ws://localhost:8082/browser";

export const DeviceMirrorWebRTC = () => {
    const videoRef = useRef<HTMLVideoElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
    const [error, setError] = useState<string | null>(null);
    const [deviceInfo, setDeviceInfo] = useState<DeviceInfo | null>(null);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [latency, setLatency] = useState<number | null>(null);
    const [fps, setFps] = useState<number>(0);
    const [bitrate, setBitrate] = useState<number>(0);
    const [volume, setVolume] = useState<{ level: number; max: number }>({ level: 50, max: 100 });
    const [deviceConnected, setDeviceConnected] = useState(false);

    const wsRef = useRef<WebSocket | null>(null);
    const pcRef = useRef<RTCPeerConnection | null>(null);
    const statsIntervalRef = useRef<NodeJS.Timeout | null>(null);
    const lastBytesRef = useRef<number>(0);
    const lastTimeRef = useRef<number>(0);

    // Touch state for gesture detection
    const touchStartRef = useRef<{ x: number; y: number; time: number } | null>(null);

    // ==========================================================================
    // WebRTC Stats
    // ==========================================================================

    const startStatsCollection = useCallback(() => {
        if (statsIntervalRef.current) {
            clearInterval(statsIntervalRef.current);
        }

        statsIntervalRef.current = setInterval(async () => {
            const pc = pcRef.current;
            if (!pc) return;

            try {
                const stats = await pc.getStats();
                stats.forEach((report) => {
                    if (report.type === 'inbound-rtp' && report.kind === 'video') {
                        const now = Date.now();
                        const bytes = report.bytesReceived || 0;

                        if (lastTimeRef.current > 0) {
                            const deltaTime = (now - lastTimeRef.current) / 1000;
                            const deltaBytes = bytes - lastBytesRef.current;
                            const kbps = Math.round((deltaBytes * 8) / deltaTime / 1000);
                            setBitrate(kbps);
                        }

                        lastBytesRef.current = bytes;
                        lastTimeRef.current = now;

                        // FPS from framesPerSecond or calculated
                        if (report.framesPerSecond) {
                            setFps(Math.round(report.framesPerSecond));
                        } else if (report.framesDecoded) {
                            // Calculate from frames decoded delta
                            setFps(Math.round(report.framesDecoded / ((now - (report.timestamp || now)) / 1000) || 0));
                        }
                    }

                    // Get RTT from candidate-pair
                    if (report.type === 'candidate-pair' && report.state === 'succeeded') {
                        if (report.currentRoundTripTime) {
                            setLatency(Math.round(report.currentRoundTripTime * 1000));
                        }
                    }
                });
            } catch (e) {
                console.error('Stats collection error:', e);
            }
        }, 1000);
    }, []);

    const stopStatsCollection = useCallback(() => {
        if (statsIntervalRef.current) {
            clearInterval(statsIntervalRef.current);
            statsIntervalRef.current = null;
        }
    }, []);

    // ==========================================================================
    // WebRTC Connection
    // ==========================================================================

    const createPeerConnection = useCallback(() => {
        const config: RTCConfiguration = {
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun.relay.metered.ca:80' },
                {
                    urls: 'turn:global.relay.metered.ca:80',
                    username: 'e8dd65c92f6d2a466146ce6e',
                    credential: 'rQq9Hfqk/XqCzJg8'
                },
                {
                    urls: 'turn:global.relay.metered.ca:443',
                    username: 'e8dd65c92f6d2a466146ce6e',
                    credential: 'rQq9Hfqk/XqCzJg8'
                },
                {
                    urls: 'turns:global.relay.metered.ca:443?transport=tcp',
                    username: 'e8dd65c92f6d2a466146ce6e',
                    credential: 'rQq9Hfqk/XqCzJg8'
                }
            ],
            bundlePolicy: 'max-bundle',
            rtcpMuxPolicy: 'require',
            // Use 'relay' to force TURN, 'all' to try both direct and relay
            iceTransportPolicy: 'all'
        };

        const pc = new RTCPeerConnection(config);

        pc.ontrack = (event) => {
            console.log('🎥 Received track:', event.track.kind, 'readyState:', event.track.readyState);
            console.log('🎥 Stream tracks:', event.streams[0]?.getTracks().map(t => ({ kind: t.kind, readyState: t.readyState })));

            if (event.track.kind === 'video' && videoRef.current) {
                console.log('🎥 Setting video srcObject...');
                const stream = event.streams[0];
                videoRef.current.srcObject = stream;

                // Also listen for track enable/disable
                event.track.onended = () => console.log('🎥 Track ended');
                event.track.onmute = () => console.log('🎥 Track muted');
                event.track.onunmute = () => console.log('🎥 Track unmuted');

                // Try to play the video
                videoRef.current.play()
                    .then(() => console.log('🎥 Video playback started!'))
                    .catch(e => console.error('🎥 Video play error:', e));

                // Get video dimensions once metadata is loaded
                videoRef.current.onloadedmetadata = () => {
                    console.log('🎥 Video metadata loaded:', videoRef.current?.videoWidth, 'x', videoRef.current?.videoHeight);
                    if (videoRef.current) {
                        setDeviceInfo({
                            width: videoRef.current.videoWidth,
                            height: videoRef.current.videoHeight
                        });
                    }
                };

                // Also check for loadeddata
                videoRef.current.onloadeddata = () => {
                    console.log('🎥 Video data loaded, dimensions:', videoRef.current?.videoWidth, 'x', videoRef.current?.videoHeight);
                };
            }
        };

        pc.onicecandidate = (event) => {
            if (event.candidate && wsRef.current?.readyState === WebSocket.OPEN) {
                wsRef.current.send(JSON.stringify({
                    type: 'ice_candidate',
                    candidate: event.candidate.candidate,
                    sdpMid: event.candidate.sdpMid,
                    sdpMLineIndex: event.candidate.sdpMLineIndex
                }));
            }
        };

        pc.oniceconnectionstatechange = () => {
            console.log('🧊 ICE connection state:', pc.iceConnectionState);
            console.log('🧊 ICE gathering state:', pc.iceGatheringState);
            switch (pc.iceConnectionState) {
                case 'checking':
                    console.log('🧊 ICE is checking candidates...');
                    break;
                case 'connected':
                case 'completed':
                    console.log('🧊 ICE connected! WebRTC should be streaming now.');
                    setConnectionState('connected');
                    startStatsCollection();
                    break;
                case 'disconnected':
                    console.log('🧊 ICE disconnected - may recover');
                    setConnectionState('disconnected');
                    stopStatsCollection();
                    break;
                case 'failed':
                    console.log('🧊 ICE FAILED - connection could not be established');
                    setConnectionState('disconnected');
                    stopStatsCollection();
                    break;
                case 'closed':
                    setConnectionState('disconnected');
                    stopStatsCollection();
                    break;
            }
        };

        pc.onconnectionstatechange = () => {
            console.log('🔗 Connection state:', pc.connectionState);
        };

        pc.onicegatheringstatechange = () => {
            console.log('🧊 ICE gathering state changed:', pc.iceGatheringState);
        };

        pcRef.current = pc;
        return pc;
    }, [startStatsCollection, stopStatsCollection]);

    const handleOffer = useCallback(async (sdp: string) => {
        console.log('Received offer, creating answer...');

        let pc = pcRef.current;
        if (!pc) {
            pc = createPeerConnection();
        }

        try {
            // Prefer H.264 in the answer
            const offer = new RTCSessionDescription({ type: 'offer', sdp });
            await pc.setRemoteDescription(offer);

            const answer = await pc.createAnswer();

            // Prefer H.264 codec
            const modifiedSdp = preferH264(answer.sdp || '');
            const modifiedAnswer = new RTCSessionDescription({
                type: 'answer',
                sdp: modifiedSdp
            });

            await pc.setLocalDescription(modifiedAnswer);

            if (wsRef.current?.readyState === WebSocket.OPEN) {
                wsRef.current.send(JSON.stringify({
                    type: 'answer',
                    sdp: modifiedAnswer.sdp
                }));
            }

            setConnectionState('signaling');
        } catch (e) {
            console.error('Failed to handle offer:', e);
            setError('Failed to establish WebRTC connection');
            setConnectionState('error');
        }
    }, [createPeerConnection]);

    const handleIceCandidate = useCallback((candidate: string, sdpMid: string, sdpMLineIndex: number) => {
        const pc = pcRef.current;
        if (!pc) return;

        try {
            pc.addIceCandidate(new RTCIceCandidate({
                candidate,
                sdpMid,
                sdpMLineIndex
            }));
        } catch (e) {
            console.error('Failed to add ICE candidate:', e);
        }
    }, []);

    // ==========================================================================
    // Signaling Connection
    // ==========================================================================

    const cleanup = useCallback(() => {
        stopStatsCollection();

        if (pcRef.current) {
            pcRef.current.close();
            pcRef.current = null;
        }

        if (videoRef.current) {
            videoRef.current.srcObject = null;
        }

        lastBytesRef.current = 0;
        lastTimeRef.current = 0;
    }, [stopStatsCollection]);

    const connect = useCallback(() => {
        setError(null);
        setConnectionState('connecting');
        cleanup();

        try {
            const ws = new WebSocket(SIGNALING_URL);
            wsRef.current = ws;

            ws.onopen = () => {
                console.log("Connected to signaling server");
                setConnectionState('signaling');
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    console.log('Signaling message:', data.type);

                    switch (data.type) {
                        case 'connection_status':
                            setDeviceConnected(data.deviceConnected);
                            if (!data.deviceConnected) {
                                setError(null); // Let the UI show translated "Waiting for Device" message
                            } else {
                                // Auto-start if already connected
                                startStream();
                            }
                            break;

                        case 'device_connected':
                            setDeviceConnected(true);
                            setError(null);
                            // Auto-start stream when device connects
                            startStream();
                            break;

                        case 'device_disconnected':
                            setDeviceConnected(false);
                            setConnectionState('disconnected');
                            setError('Device disconnected');
                            cleanup();
                            break;

                        case 'offer':
                            handleOffer(data.sdp);
                            break;

                        case 'answer':
                            // Handle answer if we sent an offer (waitForOffer mode)
                            if (pcRef.current) {
                                pcRef.current.setRemoteDescription(
                                    new RTCSessionDescription({ type: 'answer', sdp: data.sdp })
                                );
                            }
                            break;

                        case 'ice_candidate':
                            handleIceCandidate(data.candidate, data.sdpMid, data.sdpMLineIndex);
                            break;

                        case 'stream_starting':
                            console.log('Stream starting:', data.result);
                            break;

                        case 'stream_ready':
                            console.log('Stream ready, waiting for offer...');
                            break;

                        case 'stream_error':
                            setError(data.message || data.error);
                            setConnectionState('error');
                            break;

                        case 'stream_stopped':
                            setConnectionState('disconnected');
                            cleanup();
                            break;

                        case 'error':
                            setError(data.message || data.error);
                            break;

                        case 'pong':
                            // Handle ping response if needed
                            break;
                    }
                } catch (e) {
                    console.error('Failed to parse signaling message:', e);
                }
            };

            ws.onclose = () => {
                console.log('Signaling connection closed');
                setConnectionState('disconnected');
                cleanup();
            };

            ws.onerror = () => {
                setError("Failed to connect to signaling server. Is the WebRTC server running?");
                setConnectionState('error');
            };
        } catch (e) {
            setError("Failed to initialize connection.");
            setConnectionState('error');
        }
    }, [cleanup, handleOffer, handleIceCandidate]);

    const startStream = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            // Create peer connection before requesting stream
            createPeerConnection();

            wsRef.current.send(JSON.stringify({
                action: 'start_stream',
                width: 720,
                height: 1280,
                fps: 30,
                waitForOffer: false // Device generates offer
            }));
        }
    }, [createPeerConnection]);

    const stopStream = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
                action: 'stop_stream'
            }));
        }
        cleanup();
        setConnectionState('disconnected');
    }, [cleanup]);

    const disconnect = useCallback(() => {
        stopStream();
        wsRef.current?.close();
        setConnectionState('disconnected');
    }, [stopStream]);

    useEffect(() => {
        connect();
        return () => disconnect();
    }, [connect, disconnect]);

    // ==========================================================================
    // Input Handling (Touch/Click → ADB commands via data channel or signaling)
    // ==========================================================================

    const sendCommand = useCallback((command: object) => {
        // For now, send commands through signaling server
        // In future, use WebRTC data channel for lower latency
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
                action: 'device_command',
                ...command
            }));
        }
    }, []);

    const getNormalizedCoords = useCallback((clientX: number, clientY: number) => {
        const element = videoRef.current;
        if (!element || !deviceInfo) return null;

        const rect = element.getBoundingClientRect();
        const videoAspect = element.videoWidth / element.videoHeight;
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

    // Use conditional rendering for translatable connection text
    const renderConnectionText = () => {
        switch (connectionState) {
            case 'disconnected': return <span>Disconnected</span>;
            case 'connecting': return <span>Connecting...</span>;
            case 'signaling': return <span>Establishing WebRTC...</span>;
            case 'connected': return <span>WebRTC H.264 Stream</span>;
            case 'error': return <span>Connection Failed</span>;
            default: return null;
        }
    };

    return (
        <div ref={containerRef} className="flex flex-col h-full relative bg-[#0a0a0c] border-l border-white/5 overflow-hidden">
            <div className="absolute inset-0 mesh-gradient opacity-10 z-0" />

            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 relative z-10 border-b border-white/[0.03]">
                <div className="flex items-center gap-3">
                    <div className={cn(
                        "w-2 h-2 rounded-full transition-all duration-500",
                        connectionState === 'connected' ? "bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)] animate-pulse" :
                            connectionState === 'error' ? "bg-brand-pink shadow-[0_0_10px_rgba(255,46,144,0.5)]" :
                                connectionState === 'signaling' ? "bg-yellow-500 shadow-[0_0_10px_rgba(234,179,8,0.5)] animate-pulse" : "bg-white/10"
                    )} />
                    <div>
                        <h2 className="text-[10px] font-black text-white uppercase tracking-[0.4em] leading-none flex items-center gap-2">
                            WebRTC Stream
                            {connectionState === 'connected' && <Zap className="h-3 w-3 text-emerald-400" />}
                        </h2>
                        <p className="text-[8px] font-bold text-white/20 uppercase tracking-widest mt-1">{renderConnectionText()}</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {fps > 0 && (
                        <div className="px-2 py-0.5 rounded-md bg-white/[0.03] border border-white/5">
                            <span className="text-[8px] font-black text-emerald-400/60 uppercase tracking-tighter">{fps} FPS</span>
                        </div>
                    )}
                    {latency !== null && latency > 0 && (
                        <div className="px-2 py-0.5 rounded-md bg-white/[0.03] border border-white/5">
                            <span className="text-[8px] font-black text-blue-400/60 uppercase tracking-tighter">{latency}ms</span>
                        </div>
                    )}
                    {bitrate > 0 && (
                        <div className="px-2 py-0.5 rounded-md bg-white/[0.03] border border-white/5">
                            <span className="text-[8px] font-black text-purple-400/60 uppercase tracking-tighter">{bitrate} kbps</span>
                        </div>
                    )}
                    <button onClick={toggleFullscreen} className="p-2 rounded-lg text-white/20 hover:text-white transition-colors">
                        {isFullscreen ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
                    </button>
                </div>
            </div>

            {/* Device Stream Area */}
            <div className="flex-1 flex items-center justify-center p-4 relative z-10 overflow-hidden min-h-0">
                <div
                    className="relative h-full group/frame transition-all duration-700 ease-in-out"
                    style={{
                        aspectRatio: deviceInfo && deviceInfo.width > 0
                            ? `${deviceInfo.width - 100} / ${deviceInfo.height}`
                            : '9/19.5'
                    }}
                >
                    {/* External Glow */}
                    <div className="absolute inset-0 bg-brand-pink/5 blur-[100px] rounded-[3rem] opacity-0 group-hover/frame:opacity-100 transition-opacity duration-1000" />

                    {/* Phone Frame */}
                    <div className="relative w-full h-full rounded-[3rem] bg-black p-[2px] shadow-2xl ring-1 ring-white/10 transition-transform duration-500 hover:scale-[1.01]">
                        {/* Inner Shell */}
                        <div className="w-full h-full rounded-[2.9rem] bg-zinc-900/50 backdrop-blur-3xl p-1.5 relative overflow-hidden border border-white/10">
                            {/* Screen Container */}
                            <div className="w-full h-full rounded-[2.5rem] bg-black overflow-hidden relative border border-white/5">
                                {/* Video element is ALWAYS rendered to ensure ref is available for ontrack */}
                                <video
                                    ref={videoRef}
                                    className={cn(
                                        "w-full h-full object-cover cursor-crosshair relative z-10",
                                        connectionState !== 'connected' && "opacity-0"
                                    )}
                                    autoPlay
                                    playsInline
                                    muted
                                    onMouseDown={handleMouseDown}
                                    onMouseUp={handleMouseUp}
                                    onTouchStart={handleTouchStart}
                                    onTouchEnd={handleTouchEnd}
                                />

                                {/* Overlay when not connected */}
                                {connectionState !== 'connected' && (
                                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-zinc-950 z-30 p-8 text-center">
                                        <div className="relative mb-8">
                                            <div className="w-16 h-16 rounded-3xl bg-white/[0.03] border border-white/5 flex items-center justify-center relative overflow-hidden">
                                                <div className="absolute inset-0 bg-gradient-to-t from-brand-pink/10 to-transparent animate-pulse" />
                                                <WifiOff className="h-6 w-6 text-white/20" />
                                            </div>
                                            {(connectionState === 'connecting' || connectionState === 'signaling') && (
                                                <div className="absolute -inset-4 border border-brand-pink/30 rounded-full animate-ping opacity-20" />
                                            )}
                                        </div>
                                        <div className="space-y-2 mb-8">
                                            <h3 className="text-sm font-black text-white uppercase tracking-widest">
                                                {connectionState === 'connecting' && <span>Connecting to Server</span>}
                                                {connectionState === 'signaling' && <span>Establishing WebRTC</span>}
                                                {connectionState !== 'connecting' && connectionState !== 'signaling' && !deviceConnected && <span>Waiting for Device</span>}
                                                {connectionState !== 'connecting' && connectionState !== 'signaling' && deviceConnected && <span>Stream Offline</span>}
                                            </h3>
                                            <p className="text-[10px] text-white/30 uppercase font-black tracking-tighter leading-relaxed">
                                                {error || (!deviceConnected ? <span>Connect Portal app to ws://localhost:8082/device</span> : <span>Click below to start</span>)}
                                            </p>
                                        </div>
                                        <div className="space-y-2 w-full">
                                            {deviceConnected && connectionState !== 'signaling' && (
                                                <button
                                                    onClick={startStream}
                                                    className="w-full py-3 rounded-xl bg-emerald-500 text-black text-[9px] font-black uppercase tracking-widest hover:bg-emerald-400 transition-all"
                                                >
                                                    Start Stream
                                                </button>
                                            )}
                                            <button
                                                onClick={connect}
                                                disabled={connectionState === 'connecting' || connectionState === 'signaling'}
                                                className="w-full py-3 rounded-xl bg-white text-black text-[9px] font-black uppercase tracking-widest hover:bg-zinc-200 transition-all disabled:opacity-50"
                                            >
                                                {connectionState === 'connecting' && <span>Connecting...</span>}
                                                {connectionState === 'signaling' && <span>Negotiating...</span>}
                                                {connectionState !== 'connecting' && connectionState !== 'signaling' && <span>Reconnect</span>}
                                            </button>
                                        </div>
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

// ==========================================================================
// SDP Manipulation Helpers
// ==========================================================================

function preferH264(sdp: string): string {
    const lines = sdp.split('\r\n');
    const mLineIndex = lines.findIndex(line => line.startsWith('m=video '));
    if (mLineIndex === -1) return sdp;

    // Find H264 payload types
    const h264Payloads: string[] = [];
    const rtxAptMap: Map<string, string> = new Map();

    for (const line of lines) {
        const rtpmapMatch = line.match(/^a=rtpmap:(\d+) H264\/90000/i);
        if (rtpmapMatch) {
            h264Payloads.push(rtpmapMatch[1]);
        }

        const fmtpMatch = line.match(/^a=fmtp:(\d+) apt=(\d+)/);
        if (fmtpMatch) {
            rtxAptMap.set(fmtpMatch[1], fmtpMatch[2]);
        }
    }

    if (h264Payloads.length === 0) return sdp;

    // Find RTX payloads for H264
    const rtxPayloads: string[] = [];
    for (const [rtxPt, apt] of rtxAptMap) {
        if (h264Payloads.includes(apt)) {
            rtxPayloads.push(rtxPt);
        }
    }

    // Reorder m=video line to prefer H264
    const parts = lines[mLineIndex].split(' ');
    if (parts.length <= 3) return sdp;

    const header = parts.slice(0, 3);
    const payloads = parts.slice(3);

    const preferred = payloads.filter(p => h264Payloads.includes(p) || rtxPayloads.includes(p));
    const remaining = payloads.filter(p => !h264Payloads.includes(p) && !rtxPayloads.includes(p));

    if (preferred.length === 0) return sdp;

    lines[mLineIndex] = [...header, ...preferred, ...remaining].join(' ');

    return lines.join('\r\n');
}

export default DeviceMirrorWebRTC;
