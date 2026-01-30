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
    Cloud,
    RefreshCw,
    ChevronDown
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useMobileRunDevices, MobileRunDevice } from "@/hooks/useMobileRunDevices";

interface DeviceInfo {
    width: number;
    height: number;
}

type ConnectionState = 'disconnected' | 'connecting' | 'signaling' | 'connected' | 'error';

// Use gateway proxy for WebSocket to avoid browser header limitations
// The gateway adds the Authorization header that MobileRun requires
const GATEWAY_WS_BASE = "ws://localhost:8000/api/v1/mobilerun/devices";

export const DeviceMirrorCloud = () => {
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
    const [showDeviceSelector, setShowDeviceSelector] = useState(false);

    const wsRef = useRef<WebSocket | null>(null);
    const pcRef = useRef<RTCPeerConnection | null>(null);
    const sessionIdRef = useRef<string>('');
    const statsIntervalRef = useRef<NodeJS.Timeout | null>(null);
    const lastBytesRef = useRef<number>(0);
    const lastTimeRef = useRef<number>(0);

    // Touch state for gesture detection
    const touchStartRef = useRef<{ x: number; y: number; time: number } | null>(null);

    // Use MobileRun devices hook
    const {
        devices,
        loading: devicesLoading,
        error: devicesError,
        refresh: refreshDevices,
        selectedDevice,
        setSelectedDevice
    } = useMobileRunDevices();

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

                        if (report.framesPerSecond) {
                            setFps(Math.round(report.framesPerSecond));
                        }
                    }

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
    // WebRTC Connection for MobileRun Cloud
    // ==========================================================================

    // Reusable function to set up event handlers on a peer connection
    const setupPeerConnectionHandlers = useCallback((pc: RTCPeerConnection) => {
        pc.ontrack = (event) => {
            console.log('🎥 [Cloud] Received track:', event.track.kind, 'readyState:', event.track.readyState);

            if (event.track.kind === 'video' && videoRef.current) {
                console.log('🎥 [Cloud] Setting video srcObject...');
                const stream = event.streams[0];
                videoRef.current.srcObject = stream;

                event.track.onended = () => console.log('🎥 [Cloud] Track ended');
                event.track.onmute = () => console.log('🎥 [Cloud] Track muted');
                event.track.onunmute = () => console.log('🎥 [Cloud] Track unmuted');

                videoRef.current.play()
                    .then(() => console.log('🎥 [Cloud] Video playback started!'))
                    .catch(e => console.error('🎥 [Cloud] Video play error:', e));

                videoRef.current.onloadedmetadata = () => {
                    console.log('🎥 [Cloud] Video metadata loaded:', videoRef.current?.videoWidth, 'x', videoRef.current?.videoHeight);
                    if (videoRef.current) {
                        setDeviceInfo({
                            width: videoRef.current.videoWidth,
                            height: videoRef.current.videoHeight
                        });
                    }
                };
            }
        };

        pc.onicecandidate = (event) => {
            if (event.candidate && wsRef.current?.readyState === WebSocket.OPEN) {
                // Use 'candidate' type to match MobileRun protocol
                wsRef.current.send(JSON.stringify({
                    type: 'candidate',
                    candidate: event.candidate.candidate,
                    sdpMid: event.candidate.sdpMid,
                    sdpMLineIndex: event.candidate.sdpMLineIndex,
                    sessionId: sessionIdRef.current
                }));
            }
        };

        pc.oniceconnectionstatechange = () => {
            console.log('🧊 [Cloud] ICE connection state:', pc.iceConnectionState);
            switch (pc.iceConnectionState) {
                case 'connected':
                case 'completed':
                    console.log('🧊 [Cloud] ICE connected!');
                    setConnectionState('connected');
                    startStatsCollection();
                    break;
                case 'disconnected':
                    setConnectionState('disconnected');
                    stopStatsCollection();
                    break;
                case 'failed':
                    setConnectionState('error');
                    setError('ICE connection failed');
                    stopStatsCollection();
                    break;
                case 'closed':
                    setConnectionState('disconnected');
                    stopStatsCollection();
                    break;
            }
        };

        pc.onconnectionstatechange = () => {
            console.log('🔗 [Cloud] Connection state:', pc.connectionState);
        };
    }, [startStatsCollection, stopStatsCollection]);

    const createPeerConnection = useCallback(() => {
        const config: RTCConfiguration = {
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun.relay.metered.ca:80' },
            ],
            bundlePolicy: 'max-bundle',
            rtcpMuxPolicy: 'require',
            iceTransportPolicy: 'all'
        };

        const pc = new RTCPeerConnection(config);
        setupPeerConnectionHandlers(pc);
        pcRef.current = pc;
        return pc;
    }, [setupPeerConnectionHandlers]);

    const handleOffer = useCallback(async (sdp: string) => {
        console.log('[Cloud] Handling offer, creating answer...');

        let pc = pcRef.current;
        if (!pc) {
            pc = createPeerConnection();
        }

        try {
            const offer = new RTCSessionDescription({ type: 'offer', sdp });
            await pc.setRemoteDescription(offer);

            const answer = await pc.createAnswer();
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
            console.error('[Cloud] Failed to handle offer:', e);
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
            console.error('[Cloud] Failed to add ICE candidate:', e);
        }
    }, []);

    // ==========================================================================
    // MobileRun Cloud Signaling Connection
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
        if (!selectedDevice) {
            setError('No device selected');
            return;
        }

        setError(null);
        setConnectionState('connecting');
        cleanup();

        try {
            // Connect through gateway proxy (it handles the Authorization header)
            const streamUrl = `${GATEWAY_WS_BASE}/${selectedDevice.id}/stream`;
            console.log(`[Cloud] Connecting to gateway proxy: ${streamUrl}`);

            const ws = new WebSocket(streamUrl);
            wsRef.current = ws;

            // Generate a unique session ID for this connection
            const sessionId = Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
            sessionIdRef.current = sessionId;
            console.log(`[Cloud] Session ID: ${sessionId}`);

            // Function to create offer and send it to server
            const createAndSendOffer = async (pc: RTCPeerConnection) => {
                try {
                    // Add a transceiver for receiving video
                    pc.addTransceiver('video', { direction: 'recvonly' });
                    pc.addTransceiver('audio', { direction: 'inactive' });

                    const offer = await pc.createOffer();
                    const modifiedSdp = preferH264(offer.sdp || '');
                    const modifiedOffer = new RTCSessionDescription({
                        type: 'offer',
                        sdp: modifiedSdp
                    });

                    await pc.setLocalDescription(modifiedOffer);

                    // Send the offer to server
                    if (ws.readyState === WebSocket.OPEN) {
                        console.log('[Cloud] Sending offer to server...');
                        ws.send(JSON.stringify({
                            type: 'offer',
                            sdp: modifiedOffer.sdp,
                            sessionId: sessionIdRef.current
                        }));
                    }
                } catch (e) {
                    console.error('[Cloud] Failed to create offer:', e);
                    setError('Failed to create WebRTC offer');
                    setConnectionState('error');
                }
            };

            ws.onopen = () => {
                console.log("[Cloud] Connected to MobileRun stream");
                setConnectionState('signaling');

                // Step 1: Request RTC configuration from server
                ws.send(JSON.stringify({
                    type: 'requestRtcConfiguration',
                    sessionId: sessionId
                }));
            };

            ws.onmessage = async (event) => {
                try {
                    const data = JSON.parse(event.data);
                    console.log('[Cloud] Message:', data.type, data);

                    switch (data.type) {
                        case 'rtcConfiguration':
                            // Step 2: Received RTC configuration with ICE servers
                            console.log('[Cloud] Received RTC configuration:', data.rtcConfiguration);

                            if (data.rtcConfiguration?.iceServers) {
                                const config: RTCConfiguration = {
                                    ...data.rtcConfiguration,
                                    bundlePolicy: data.rtcConfiguration.bundlePolicy || 'balanced',
                                    rtcpMuxPolicy: data.rtcConfiguration.rtcpMuxPolicy || 'require',
                                    iceTransportPolicy: data.rtcConfiguration.iceTransportPolicy || 'all'
                                };

                                // Create peer connection with server's ICE config
                                if (pcRef.current) {
                                    pcRef.current.close();
                                }
                                const pc = new RTCPeerConnection(config);
                                pcRef.current = pc;

                                // Set up handlers (including ICE candidate sending)
                                setupPeerConnectionHandlers(pc);

                                // Step 3: Create and send offer
                                await createAndSendOffer(pc);
                            }
                            break;

                        case 'answer':
                            // Step 4: Server responds with answer
                            console.log('[Cloud] Received answer from server');
                            if (pcRef.current && data.sdp) {
                                try {
                                    await pcRef.current.setRemoteDescription(
                                        new RTCSessionDescription({ type: 'answer', sdp: data.sdp })
                                    );
                                    console.log('[Cloud] Remote description set successfully');

                                    // Start requesting frames after connection is established
                                    // This is for pull-based video delivery
                                    setTimeout(() => {
                                        if (ws.readyState === WebSocket.OPEN) {
                                            ws.send(JSON.stringify({
                                                type: 'requestFrame',
                                                sessionId: sessionIdRef.current
                                            }));
                                        }
                                    }, 500);
                                } catch (e) {
                                    console.error('[Cloud] Failed to set remote description:', e);
                                }
                            }
                            break;

                        case 'candidate':
                            // ICE candidate from server
                            if (data.candidate && pcRef.current) {
                                try {
                                    await pcRef.current.addIceCandidate(new RTCIceCandidate({
                                        candidate: data.candidate,
                                        sdpMid: data.sdpMid,
                                        sdpMLineIndex: data.sdpMLineIndex
                                    }));
                                } catch (e) {
                                    console.error('[Cloud] Failed to add ICE candidate:', e);
                                }
                            }
                            break;

                        case 'error':
                            console.error('[Cloud] Server error:', data);
                            setError(data.message || data.error || 'Cloud stream error');
                            setConnectionState('error');
                            break;

                        default:
                            console.log('[Cloud] Unhandled message type:', data.type);
                    }
                } catch (e) {
                    console.error('[Cloud] Failed to parse message:', e, event.data);
                }
            };

            ws.onclose = (event) => {
                console.log(`[Cloud] Connection closed: ${event.code} ${event.reason}`);
                setConnectionState('disconnected');
                cleanup();
            };

            ws.onerror = (event) => {
                console.error('[Cloud] WebSocket error:', event);
                setError("Failed to connect to MobileRun cloud stream");
                setConnectionState('error');
            };
        } catch (e) {
            console.error('[Cloud] Connection error:', e);
            setError("Failed to initialize cloud connection");
            setConnectionState('error');
        }
    }, [selectedDevice, cleanup, setupPeerConnectionHandlers]);

    const disconnect = useCallback(() => {
        if (wsRef.current) {
            wsRef.current.send(JSON.stringify({ action: 'stop_stream' }));
            wsRef.current.close();
        }
        cleanup();
        setConnectionState('disconnected');
    }, [cleanup]);

    // Auto-connect when device is selected
    useEffect(() => {
        if (selectedDevice && connectionState === 'disconnected') {
            connect();
        }
        return () => disconnect();
    }, [selectedDevice]);

    // ==========================================================================
    // Input Handling
    // ==========================================================================

    const sendCommand = useCallback((command: object) => {
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

    const renderConnectionText = () => {
        switch (connectionState) {
            case 'disconnected': return <span>Disconnected</span>;
            case 'connecting': return <span>Connecting to Cloud...</span>;
            case 'signaling': return <span>Establishing WebRTC...</span>;
            case 'connected': return <span>Cloud H.264 Stream</span>;
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
                            <Cloud className="h-3 w-3 text-cyan-400" />
                            Cloud Stream
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

            {/* Device Selector */}
            <div className="px-6 py-3 relative z-50 border-b border-white/[0.03]">
                <div className="relative">
                    <button
                        onClick={() => setShowDeviceSelector(!showDeviceSelector)}
                        className="w-full flex items-center justify-between px-4 py-2.5 rounded-xl bg-white/[0.03] border border-white/5 hover:border-cyan-500/30 transition-all"
                    >
                        <div className="flex items-center gap-3">
                            <div className={cn(
                                "w-2 h-2 rounded-full",
                                selectedDevice?.state === 'ready' ? "bg-emerald-500" :
                                    selectedDevice?.state === 'assigned' ? "bg-yellow-500" : "bg-white/20"
                            )} />
                            <span className="text-xs font-bold text-white/80">
                                {selectedDevice?.name || 'Select a device...'}
                            </span>
                        </div>
                        <div className="flex items-center gap-2">
                            <button
                                onClick={(e) => { e.stopPropagation(); refreshDevices(); }}
                                className="p-1 rounded hover:bg-white/10 transition-colors"
                            >
                                <RefreshCw className={cn("h-3 w-3 text-white/40", devicesLoading && "animate-spin")} />
                            </button>
                            <ChevronDown className={cn("h-4 w-4 text-white/40 transition-transform", showDeviceSelector && "rotate-180")} />
                        </div>
                    </button>

                    {showDeviceSelector && (
                        <div className="absolute top-full left-0 right-0 mt-2 py-2 bg-zinc-900 border border-white/10 rounded-xl shadow-2xl z-50 max-h-60 overflow-y-auto">
                            {devicesLoading ? (
                                <div className="px-4 py-3 text-center text-white/40 text-xs">Loading devices...</div>
                            ) : devicesError ? (
                                <div className="px-4 py-3 text-center text-red-400 text-xs">{devicesError}</div>
                            ) : devices.length === 0 ? (
                                <div className="px-4 py-3 text-center text-white/40 text-xs">No devices found</div>
                            ) : (
                                devices.map((device) => (
                                    <button
                                        key={device.id}
                                        onClick={() => {
                                            setSelectedDevice(device);
                                            setShowDeviceSelector(false);
                                        }}
                                        className={cn(
                                            "w-full flex items-center gap-3 px-4 py-2.5 hover:bg-white/5 transition-colors",
                                            selectedDevice?.id === device.id && "bg-cyan-500/10"
                                        )}
                                    >
                                        <div className={cn(
                                            "w-2 h-2 rounded-full",
                                            device.state === 'ready' ? "bg-emerald-500" :
                                                device.state === 'assigned' ? "bg-yellow-500" : "bg-white/20"
                                        )} />
                                        <div className="flex-1 text-left">
                                            <p className="text-xs font-bold text-white/80">{device.name || device.id.slice(0, 8)}</p>
                                            <p className="text-[10px] text-white/40">{device.state} • {device.deviceType || 'unknown'}</p>
                                        </div>
                                    </button>
                                ))
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* Device Stream Area */}
            <div className="flex-1 flex items-center justify-center p-4 relative z-10 overflow-hidden min-h-0">
                <div
                    className="relative h-full group/frame transition-all duration-700 ease-in-out"
                    style={{
                        aspectRatio: deviceInfo && deviceInfo.width > 0
                            ? `${deviceInfo.width} / ${deviceInfo.height}`
                            : '9/19.5'
                    }}
                >
                    <div className="absolute inset-0 bg-cyan-500/5 blur-[100px] rounded-[3rem] opacity-0 group-hover/frame:opacity-100 transition-opacity duration-1000" />

                    <div className="relative w-full h-full rounded-[3rem] bg-black p-[2px] shadow-2xl ring-1 ring-cyan-500/20 transition-transform duration-500 hover:scale-[1.01]">
                        <div className="w-full h-full rounded-[2.9rem] bg-zinc-900/50 backdrop-blur-3xl p-1.5 relative overflow-hidden border border-white/10">
                            <div className="w-full h-full rounded-[2.5rem] bg-black overflow-hidden relative border border-white/5">
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

                                {connectionState !== 'connected' && (
                                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-zinc-950 z-30 p-8 text-center">
                                        <div className="relative mb-8">
                                            <div className="w-16 h-16 rounded-3xl bg-white/[0.03] border border-cyan-500/20 flex items-center justify-center relative overflow-hidden">
                                                <div className="absolute inset-0 bg-gradient-to-t from-cyan-500/10 to-transparent animate-pulse" />
                                                {connectionState === 'connecting' || connectionState === 'signaling' ? (
                                                    <Cloud className="h-6 w-6 text-cyan-400 animate-pulse" />
                                                ) : (
                                                    <WifiOff className="h-6 w-6 text-white/20" />
                                                )}
                                            </div>
                                            {(connectionState === 'connecting' || connectionState === 'signaling') && (
                                                <div className="absolute -inset-4 border border-cyan-500/30 rounded-full animate-ping opacity-20" />
                                            )}
                                        </div>
                                        <div className="space-y-2 mb-8">
                                            <h3 className="text-sm font-black text-white uppercase tracking-widest">
                                                {connectionState === 'connecting' && <span>Connecting to Cloud</span>}
                                                {connectionState === 'signaling' && <span>Establishing WebRTC</span>}
                                                {connectionState !== 'connecting' && connectionState !== 'signaling' && !selectedDevice && <span>Select a Device</span>}
                                                {connectionState !== 'connecting' && connectionState !== 'signaling' && selectedDevice && <span>Stream Offline</span>}
                                            </h3>
                                            <p className="text-[10px] text-white/30 uppercase font-black tracking-tighter leading-relaxed">
                                                {error || (!selectedDevice ? <span>Choose a cloud device above</span> : <span>Click below to reconnect</span>)}
                                            </p>
                                        </div>
                                        <div className="space-y-2 w-full">
                                            {selectedDevice && connectionState !== 'signaling' && connectionState !== 'connecting' && (
                                                <button
                                                    onClick={connect}
                                                    className="w-full py-3 rounded-xl bg-cyan-500 text-black text-[9px] font-black uppercase tracking-widest hover:bg-cyan-400 transition-all"
                                                >
                                                    Connect to Cloud
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="absolute -left-[3px] top-24 w-[3px] h-8 bg-zinc-800 rounded-l-sm border-l border-cyan-500/20" />
                        <div className="absolute -left-[3px] top-36 w-[3px] h-12 bg-zinc-800 rounded-l-sm border-l border-cyan-500/20" />
                        <div className="absolute -left-[3px] top-52 w-[3px] h-12 bg-zinc-800 rounded-l-sm border-l border-cyan-500/20" />
                        <div className="absolute -right-[3px] top-40 w-[3px] h-16 bg-zinc-800 rounded-r-sm border-r border-cyan-500/20" />
                    </div>
                </div>
            </div>

            {/* Navigation & Controls */}
            <div className="px-6 pb-8 space-y-6 relative z-10">
                <div className="bg-black/40 backdrop-blur-xl border border-cyan-500/10 rounded-2xl flex items-center h-14 overflow-hidden shadow-2xl">
                    <button onClick={handleBack} className="flex-1 h-full flex items-center justify-center hover:bg-white/5 transition-all group border-r border-white/5">
                        <ChevronLeft className="h-5 w-5 text-white/20 group-hover:text-cyan-400 transition-colors" />
                    </button>
                    <button onClick={handleHome} className="flex-1 h-full flex items-center justify-center hover:bg-white/5 transition-all group border-r border-white/5">
                        <div className="w-5 h-5 rounded-full border-2 border-white/20 group-hover:border-cyan-400 transition-colors" />
                    </button>
                    <button onClick={handleRecent} className="flex-1 h-full flex items-center justify-center hover:bg-white/5 transition-all group">
                        <Square className="h-4.5 w-4.5 text-white/20 group-hover:text-cyan-400 transition-colors" />
                    </button>
                </div>

                <div className="px-2">
                    <div className="flex items-center gap-4 group/vol">
                        <button onClick={handleVolumeDown} className="text-white/20 hover:text-cyan-400 transition-colors">
                            <VolumeX className="h-4 w-4" />
                        </button>
                        <div className="flex-1 h-1.5 bg-white/5 rounded-full relative overflow-hidden group-hover/vol:bg-white/10 transition-colors">
                            <div
                                className="absolute inset-y-0 left-0 bg-cyan-500/40 rounded-full transition-all duration-300"
                                style={{ width: `${(volume.level / volume.max) * 100}%` }}
                            />
                            <div
                                className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-cyan-400 rounded-full shadow-lg opacity-0 group-hover/vol:opacity-100 transition-all duration-300"
                                style={{ left: `${(volume.level / volume.max) * 100}%`, transform: 'translate(-50%, -50%)' }}
                            />
                        </div>
                        <button onClick={handleVolumeUp} className="text-white/20 hover:text-cyan-400 transition-colors">
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

    const rtxPayloads: string[] = [];
    for (const [rtxPt, apt] of rtxAptMap) {
        if (h264Payloads.includes(apt)) {
            rtxPayloads.push(rtxPt);
        }
    }

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

export default DeviceMirrorCloud;
