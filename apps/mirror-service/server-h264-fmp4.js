/**
 * Low-Latency Android Screen Streaming Server
 * 
 * Architecture: Android → adb screenrecord → H.264 → FFmpeg (repackage) → WebSocket → Browser MSE
 * 
 * Key Design Decisions:
 * 1. Single persistent FFmpeg process per session (no per-frame spawning)
 * 2. No decoding - FFmpeg only repackages H.264 to fMP4 using -c copy
 * 3. Binary WebSocket frames for minimal overhead
 * 4. Backpressure handling via bufferedAmount monitoring
 * 
 * @author Generated for production use
 */

const WebSocket = require('ws');
const { spawn, exec } = require('child_process');
const http = require('http');

// =============================================================================
// Configuration
// =============================================================================

const CONFIG = {
    WSS_PORT: 8080,
    HTTP_PORT: 8082,  // Changed to avoid conflict with existing server

    // Streaming settings
    SCREENRECORD_SIZE: '720x1280',  // Lower resolution for lower latency
    SCREENRECORD_BITRATE: '4M',     // 4 Mbps - balance quality/latency

    // Raw H.264 output mode (--output-format=h264)
    // Set to true for devices that support it (Android 10+, some OEMs)
    // Set to false to use MP4 container output (more compatible)
    // Set to null for auto-detection (tries raw first, falls back to MP4)
    USE_RAW_H264: false,  // Forced to false - device doesn't support raw H.264

    // Backpressure thresholds
    WS_HIGH_WATER_MARK: 1024 * 1024,  // 1MB - pause if buffered > this
    WS_LOW_WATER_MARK: 256 * 1024,     // 256KB - resume when below this

    // Chunk size for reading FFmpeg output
    // Smaller = lower latency, but more syscall overhead
    // Larger = higher latency, but more efficient
    // 16KB is a good balance for fMP4 mdat atoms
    READ_CHUNK_SIZE: 16 * 1024
};

// =============================================================================
// Device Screen Dimensions (for touch input scaling)
// =============================================================================

let deviceWidth = 1080;
let deviceHeight = 2340;

function getDeviceSize() {
    return new Promise((resolve) => {
        exec('adb shell wm size', (error, stdout) => {
            if (!error && stdout) {
                const match = stdout.match(/(\d+)x(\d+)/);
                if (match) {
                    deviceWidth = parseInt(match[1]);
                    deviceHeight = parseInt(match[2]);
                    console.log(`[INFO] Device size: ${deviceWidth}x${deviceHeight}`);
                }
            }
            resolve({ width: deviceWidth, height: deviceHeight });
        });
    });
}

function checkAdbConnection() {
    return new Promise((resolve) => {
        exec('adb devices', (error, stdout) => {
            if (error) {
                resolve({ connected: false, error: 'ADB not found' });
                return;
            }
            const lines = stdout.trim().split('\n').filter(l => l && !l.startsWith('List'));
            const devices = lines.filter(l => l.includes('device') && !l.includes('offline'));
            resolve({
                connected: devices.length > 0,
                devices: devices.map(d => d.split('\t')[0])
            });
        });
    });
}

function getVolume() {
    return new Promise((resolve) => {
        exec('adb shell cmd media_session volume --stream 3 --get', (error, stdout) => {
            if (!error && stdout) {
                const match = stdout.match(/volume is (\d+) in range \[(\d+)\.\.(\d+)\]/);
                if (match) {
                    resolve({ current: parseInt(match[1]), max: parseInt(match[3]) });
                    return;
                }
            }
            resolve(null);
        });
    });
}

// =============================================================================
// Input Injection (Touch, Swipe, Keys)
// =============================================================================

function injectTouch(type, x, y) {
    const deviceX = Math.round(x * deviceWidth);
    const deviceY = Math.round(y * deviceHeight);
    console.log(`[TOUCH] type=${type}, device=(${deviceX}, ${deviceY})`);

    let cmd;
    switch (type) {
        case 'tap':
        case 'up':
            cmd = `adb shell input tap ${deviceX} ${deviceY}`;
            break;
        default:
            return;
    }

    if (cmd) {
        exec(cmd, (error) => {
            if (error) console.error(`[ERROR] Touch failed: ${error.message}`);
        });
    }
}

function injectSwipe(startX, startY, endX, endY, duration = 300) {
    const sx = Math.round(startX * deviceWidth);
    const sy = Math.round(startY * deviceHeight);
    const ex = Math.round(endX * deviceWidth);
    const ey = Math.round(endY * deviceHeight);

    exec(`adb shell input swipe ${sx} ${sy} ${ex} ${ey} ${duration}`, (error) => {
        if (error) console.error(`[ERROR] Swipe failed: ${error.message}`);
    });
}

function injectKey(keycode) {
    const keycodes = {
        'back': 4, 'home': 3, 'recent': 187,
        'power': 26, 'volume_up': 24, 'volume_down': 25
    };
    const code = keycodes[keycode] || keycode;
    exec(`adb shell input keyevent ${code}`, (error) => {
        if (error) console.error(`[ERROR] Key failed: ${error.message}`);
    });
}

// =============================================================================
// HTTP Status Server
// =============================================================================

const httpServer = http.createServer(async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Content-Type', 'application/json');

    if (req.method === 'OPTIONS') {
        res.writeHead(200);
        res.end();
        return;
    }

    if (req.url === '/status') {
        const adbStatus = await checkAdbConnection();
        const size = await getDeviceSize();
        res.writeHead(200);
        res.end(JSON.stringify({
            service: 'running',
            mode: 'h264-fmp4-mse',
            adb: adbStatus,
            deviceSize: size,
            config: {
                resolution: CONFIG.SCREENRECORD_SIZE,
                bitrate: CONFIG.SCREENRECORD_BITRATE
            }
        }));
        return;
    }

    res.writeHead(404);
    res.end(JSON.stringify({ error: 'Not found' }));
});

httpServer.listen(CONFIG.HTTP_PORT, () => {
    console.log(`[HTTP] Status server on port ${CONFIG.HTTP_PORT}`);
});

// =============================================================================
// Streaming Session Class
// =============================================================================

/**
 * Manages a single streaming session.
 * - Spawns adb screenrecord and FFmpeg once
 * - Pipes: screenrecord → FFmpeg → WebSocket
 * - Handles cleanup on disconnect
 */
class StreamingSession {
    constructor(ws) {
        this.ws = ws;
        this.adbProcess = null;
        this.ffmpegProcess = null;
        this.isActive = true;
        this.isPaused = false;
        this.bytesSent = 0;
        this.chunkCount = 0;
        this.startTime = Date.now();

        // Buffered chunks when backpressure is applied
        this.pendingChunks = [];
    }

    /**
     * Start the streaming pipeline.
     * 
     * Pipeline:
     *   adb exec-out screenrecord --output-format=h264 -
     *   │
     *   └──► ffmpeg -f h264 -i pipe:0 -c copy -f mp4 -movflags frag_keyframe+empty_moov pipe:1
     *        │
     *        └──► WebSocket binary frames
     */
    async start() {
        console.log('[STREAM] Starting H.264 → fMP4 pipeline...');

        // Get device dimensions first
        await getDeviceSize();

        // Send device info to client
        this.sendJSON({
            type: 'device_info',
            width: deviceWidth,
            height: deviceHeight,
            codec: 'avc1.42E01E',  // H.264 Baseline Profile, Level 3.0
            mode: 'fmp4-mse'
        });

        // Send initial volume
        const vol = await getVolume();
        if (vol) {
            this.sendJSON({
                type: 'volume_info',
                level: vol.current,
                max: vol.max
            });
        }

        // Start volume polling
        this.volumeInterval = setInterval(async () => {
            if (this.ws.readyState === WebSocket.OPEN) {
                const v = await getVolume();
                if (v) this.sendJSON({ type: 'volume_info', level: v.current, max: v.max });
            }
        }, 2000);

        // =====================================================================
        // Spawn adb screenrecord
        // 
        // Key flags:
        // --output-format=h264  : Raw H.264 elementary stream (no container)
        // --size 720x1280       : Lower resolution = lower latency
        // --bit-rate 4M         : 4 Mbps, good quality/latency balance
        // -                     : Output to stdout
        // 
        // Note: screenrecord has a 3-minute limit by default, but we restart
        // automatically when it ends.
        // =====================================================================

        this.spawnPipeline();
    }

    spawnPipeline() {
        if (!this.isActive) return;

        console.log('[STREAM] Starting TCP-based streaming pipeline...');

        // =====================================================================
        // TCP Socket Streaming Approach
        // 
        // Many Android devices (especially Android 11+) have restrictions on
        // stdout for screenrecord. We work around this by:
        //
        // 1. Starting a TCP listener on the device using nc (netcat)
        // 2. Setting up adb forward to connect host port to device socket
        // 3. Running screenrecord and piping to nc
        // 4. Connecting from host to receive the stream
        //
        // Pipeline:
        //   [Device] screenrecord | nc -l -p 5000
        //            ↓ (adb forward tcp:5050 tcp:5000)
        //   [Host]   nc localhost 5050 -> FFmpeg -> WebSocket
        // =====================================================================

        const DEVICE_PORT = 5000 + Math.floor(Math.random() * 1000);  // Random port to avoid conflicts
        const HOST_PORT = 5050;

        // Step 1: Setup adb forward
        const setupForward = () => {
            return new Promise((resolve, reject) => {
                exec(`adb forward tcp:${HOST_PORT} tcp:${DEVICE_PORT}`, (error, stdout, stderr) => {
                    if (error) {
                        console.error('[ADB] Forward setup failed:', error.message);
                        reject(error);
                    } else {
                        console.log(`[ADB] Port forwarding: localhost:${HOST_PORT} -> device:${DEVICE_PORT}`);
                        resolve();
                    }
                });
            });
        };

        // Step 2: Start listener and screenrecord on device
        const startDeviceStream = () => {
            console.log('[STREAM] Starting device-side stream (nc listener + screenrecord)...');

            // Use shell to run: screenrecord with output piped to nc listener
            // The nc listener will accept one connection and stream data
            const cmd = `screenrecord --size ${CONFIG.SCREENRECORD_SIZE} --bit-rate ${CONFIG.SCREENRECORD_BITRATE} --time-limit 180 - 2>/dev/null | nc -l -p ${DEVICE_PORT}`;

            this.adbProcess = spawn('adb', ['shell', cmd], {
                stdio: ['ignore', 'pipe', 'pipe']
            });

            this.adbProcess.stderr.on('data', (data) => {
                const msg = data.toString().trim();
                if (msg) console.log(`[ADB STDERR] ${msg}`);
            });

            this.adbProcess.stdout.on('data', (data) => {
                // Debug output from shell (shouldn't have any if working)
                const msg = data.toString().trim();
                if (msg) console.log(`[ADB STDOUT] ${msg}`);
            });

            this.adbProcess.on('error', (err) => {
                console.error('[ADB ERROR]', err.message);
            });

            this.adbProcess.on('close', (code) => {
                console.log(`[ADB] Device stream process exited with code ${code}`);
                if (this.isActive && code === 0) {
                    console.log('[STREAM] Restarting pipeline (screenrecord time limit)...');
                    setTimeout(() => this.spawnPipeline(), 100);
                }
            });
        };

        // Step 3: Connect from host and pipe to FFmpeg
        const connectToStream = () => {
            return new Promise((resolve, reject) => {
                console.log('[STREAM] Connecting to device stream...');

                // Give the device a moment to start the listener
                setTimeout(() => {
                    const net = require('net');

                    const client = net.createConnection({ port: HOST_PORT, host: 'localhost' }, () => {
                        console.log('[STREAM] Connected to device stream!');
                        resolve(client);
                    });

                    client.on('error', (err) => {
                        console.error('[TCP] Connection error:', err.message);
                        reject(err);
                    });
                }, 500);
            });
        };

        // Step 4: Start FFmpeg and pipe stream through it
        const startFFmpeg = (inputStream) => {
            console.log('[STREAM] Spawning FFmpeg for fMP4 repackaging...');

            // FFmpeg command - read from stdin, output fragmented MP4
            // Input is raw H.264 from screenrecord (when piped with -)
            this.ffmpegProcess = spawn('ffmpeg', [
                '-hide_banner',
                '-loglevel', 'warning',
                '-f', 'h264',           // Raw H.264 input
                '-i', 'pipe:0',
                '-c', 'copy',
                '-f', 'mp4',
                '-movflags', 'frag_keyframe+empty_moov+default_base_moof+omit_tfhd_offset',
                'pipe:1'
            ], {
                stdio: ['pipe', 'pipe', 'pipe']
            });

            // Pipe TCP stream to FFmpeg stdin
            inputStream.pipe(this.ffmpegProcess.stdin);

            this.ffmpegProcess.stderr.on('data', (data) => {
                const msg = data.toString().trim();
                if (msg && !msg.includes('frame=')) {
                    console.log(`[FFMPEG] ${msg}`);
                }
            });

            this.ffmpegProcess.on('error', (err) => {
                console.error('[FFMPEG ERROR]', err.message);
            });

            this.ffmpegProcess.on('close', (code) => {
                console.log(`[FFMPEG] Process exited with code ${code}`);
            });

            // =====================================================================
            // Read FFmpeg output and send to WebSocket
            // =====================================================================

            this.ffmpegProcess.stdout.on('data', (chunk) => {
                if (!this.isActive) return;

                this.chunkCount++;
                this.bytesSent += chunk.length;

                // Check for backpressure
                if (this.ws.bufferedAmount > CONFIG.WS_HIGH_WATER_MARK) {
                    if (!this.isPaused) {
                        console.log('[BACKPRESSURE] High water mark reached, pausing...');
                        this.isPaused = true;
                        inputStream.pause();
                    }
                    this.pendingChunks.push(chunk);
                    return;
                }

                // Resume if we were paused and buffer is low
                if (this.isPaused && this.ws.bufferedAmount < CONFIG.WS_LOW_WATER_MARK) {
                    console.log('[BACKPRESSURE] Low water mark reached, resuming...');
                    this.isPaused = false;
                    inputStream.resume();
                    while (this.pendingChunks.length > 0 &&
                        this.ws.bufferedAmount < CONFIG.WS_HIGH_WATER_MARK) {
                        const pending = this.pendingChunks.shift();
                        this.ws.send(pending, { binary: true });
                    }
                }

                // Send binary chunk directly
                if (this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(chunk, { binary: true });
                }
            });
        };

        // Execute the pipeline setup
        setupForward()
            .then(() => startDeviceStream())
            .then(() => connectToStream())
            .then((client) => {
                this.tcpClient = client;
                startFFmpeg(client);
            })
            .catch((err) => {
                console.error('[STREAM] Pipeline setup failed:', err.message);

                // Fallback: try exec-out method with raw H.264
                console.log('[STREAM] Falling back to exec-out method...');
                this.spawnPipelineExecOut();
            });
    }

    /**
     * Fallback pipeline using adb exec-out (works on some devices)
     */
    spawnPipelineExecOut() {
        console.log('[STREAM] Using exec-out fallback method...');

        // Try exec-out with raw H.264 format
        this.adbProcess = spawn('adb', [
            'exec-out',
            'screenrecord',
            '--output-format=h264',
            '--size', CONFIG.SCREENRECORD_SIZE,
            '--bit-rate', CONFIG.SCREENRECORD_BITRATE,
            '--time-limit', '180',
            '-'
        ], {
            stdio: ['ignore', 'pipe', 'pipe']
        });

        let receivedData = false;

        this.adbProcess.stdout.on('data', (chunk) => {
            receivedData = true;
        });

        this.adbProcess.stderr.on('data', (data) => {
            const msg = data.toString().trim();
            if (msg) console.log(`[ADB STDERR] ${msg}`);
        });

        this.adbProcess.on('error', (err) => {
            console.error('[ADB ERROR]', err.message);
            this.sendJSON({ type: 'error', message: 'ADB screenrecord failed' });
            this.stop();
        });

        this.adbProcess.on('close', (code) => {
            console.log(`[ADB] Process exited with code ${code}, received data: ${receivedData}`);

            if (!receivedData && code !== 0) {
                this.sendJSON({ type: 'error', message: `Device does not support stdout streaming (code ${code}). Please use scrcpy or a compatible device.` });
                this.stop();
                return;
            }

            if (this.isActive && code === 0) {
                console.log('[STREAM] Restarting pipeline...');
                setTimeout(() => this.spawnPipelineExecOut(), 100);
            }
        });

        // Start FFmpeg
        console.log('[STREAM] Spawning FFmpeg...');

        this.ffmpegProcess = spawn('ffmpeg', [
            '-hide_banner',
            '-loglevel', 'warning',
            '-f', 'h264',
            '-i', 'pipe:0',
            '-c', 'copy',
            '-f', 'mp4',
            '-movflags', 'frag_keyframe+empty_moov+default_base_moof+omit_tfhd_offset',
            'pipe:1'
        ], {
            stdio: ['pipe', 'pipe', 'pipe']
        });

        this.adbProcess.stdout.pipe(this.ffmpegProcess.stdin);

        this.ffmpegProcess.stderr.on('data', (data) => {
            const msg = data.toString().trim();
            if (msg && !msg.includes('frame=')) {
                console.log(`[FFMPEG] ${msg}`);
            }
        });

        this.ffmpegProcess.stdout.on('data', (chunk) => {
            if (!this.isActive) return;

            this.chunkCount++;
            this.bytesSent += chunk.length;

            if (this.ws.bufferedAmount > CONFIG.WS_HIGH_WATER_MARK) {
                if (!this.isPaused) {
                    console.log('[BACKPRESSURE] High water mark reached, pausing...');
                    this.isPaused = true;
                    if (this.adbProcess.stdout) {
                        this.adbProcess.stdout.pause();
                    }
                }
                this.pendingChunks.push(chunk);
                return;
            }

            if (this.isPaused && this.ws.bufferedAmount < CONFIG.WS_LOW_WATER_MARK) {
                console.log('[BACKPRESSURE] Low water mark reached, resuming...');
                this.isPaused = false;
                if (this.adbProcess.stdout) {
                    this.adbProcess.stdout.resume();
                }
                while (this.pendingChunks.length > 0 &&
                    this.ws.bufferedAmount < CONFIG.WS_HIGH_WATER_MARK) {
                    const pending = this.pendingChunks.shift();
                    this.ws.send(pending, { binary: true });
                }
            }

            if (this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(chunk, { binary: true });
            }
        });

        this.ffmpegProcess.on('error', (err) => {
            console.error('[FFMPEG ERROR]', err.message);
        });

        this.ffmpegProcess.on('close', (code) => {
            console.log(`[FFMPEG] Process exited with code ${code}`);
        });
    }

    sendJSON(data) {
        if (this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }

    handleMessage(message) {
        try {
            const data = JSON.parse(message.toString());
            switch (data.type) {
                case 'tap':
                    injectTouch('tap', data.x, data.y);
                    break;
                case 'swipe':
                    injectSwipe(data.startX, data.startY, data.endX, data.endY, data.duration);
                    break;
                case 'key':
                    injectKey(data.keycode);
                    break;
                case 'ping':
                    this.sendJSON({ type: 'pong' });
                    break;
                case 'stats':
                    this.sendJSON({
                        type: 'stats',
                        bytesSent: this.bytesSent,
                        chunkCount: this.chunkCount,
                        uptime: Date.now() - this.startTime,
                        isPaused: this.isPaused,
                        pendingChunks: this.pendingChunks.length,
                        wsBuffered: this.ws.bufferedAmount
                    });
                    break;
            }
        } catch {
            // Ignore parse errors
        }
    }

    stop() {
        console.log('[STREAM] Stopping session...');
        this.isActive = false;

        // Clear intervals
        if (this.volumeInterval) {
            clearInterval(this.volumeInterval);
        }

        // Kill TCP client
        if (this.tcpClient) {
            this.tcpClient.destroy();
            this.tcpClient = null;
        }

        // Kill ADB process
        if (this.adbProcess) {
            this.adbProcess.stdout?.unpipe();
            this.adbProcess.kill('SIGTERM');
            this.adbProcess = null;
        }

        // Kill FFmpeg process
        if (this.ffmpegProcess) {
            this.ffmpegProcess.stdin?.end();
            this.ffmpegProcess.kill('SIGTERM');
            this.ffmpegProcess = null;
        }

        // Clear pending chunks
        this.pendingChunks = [];

        // Remove adb forward
        exec('adb forward --remove-all', () => { });

        console.log(`[STREAM] Session ended. Sent ${(this.bytesSent / 1024 / 1024).toFixed(2)} MB in ${this.chunkCount} chunks`);
    }

    getStats() {
        return {
            bytesSent: this.bytesSent,
            chunkCount: this.chunkCount,
            uptime: Date.now() - this.startTime,
            isPaused: this.isPaused
        };
    }
}

// =============================================================================
// WebSocket Server
// =============================================================================

const wss = new WebSocket.Server({ port: CONFIG.WSS_PORT });
console.log(`[WSS] WebSocket server on port ${CONFIG.WSS_PORT}`);

// Track active sessions
const activeSessions = new Map();

wss.on('connection', async (ws, req) => {
    const clientId = `${req.socket.remoteAddress}:${req.socket.remotePort}`;
    console.log(`[WSS] Client connected: ${clientId}`);

    // Check if there's already an active session
    // Only allow one streaming session at a time to prevent resource conflicts
    if (activeSessions.size > 0) {
        console.log('[WSS] Rejecting connection: another session is active');
        ws.send(JSON.stringify({
            type: 'error',
            message: 'Another streaming session is active. Please wait.'
        }));
        ws.close();
        return;
    }

    // Create new streaming session
    const session = new StreamingSession(ws);
    activeSessions.set(clientId, session);

    // Start streaming
    await session.start();

    // Handle messages from client
    ws.on('message', (message) => {
        session.handleMessage(message);
    });

    // Handle disconnect
    ws.on('close', () => {
        console.log(`[WSS] Client disconnected: ${clientId}`);
        session.stop();
        activeSessions.delete(clientId);
    });

    // Handle errors
    ws.on('error', (err) => {
        console.error(`[WSS] WebSocket error for ${clientId}:`, err.message);
        session.stop();
        activeSessions.delete(clientId);
    });
});

// =============================================================================
// Graceful Shutdown
// =============================================================================

function shutdown() {
    console.log('\n[SHUTDOWN] Cleaning up...');

    // Stop all active sessions
    for (const [clientId, session] of activeSessions) {
        console.log(`[SHUTDOWN] Stopping session for ${clientId}`);
        session.stop();
    }
    activeSessions.clear();

    // Close servers
    wss.close(() => {
        console.log('[SHUTDOWN] WebSocket server closed');
    });

    httpServer.close(() => {
        console.log('[SHUTDOWN] HTTP server closed');
        process.exit(0);
    });

    // Force exit after 5 seconds
    setTimeout(() => {
        console.log('[SHUTDOWN] Forcing exit...');
        process.exit(1);
    }, 5000);
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

// =============================================================================
// Startup
// =============================================================================

console.log('');
console.log('╔══════════════════════════════════════════════════════════════╗');
console.log('║  Low-Latency Android Screen Streaming Server                 ║');
console.log('║  Mode: H.264 → fMP4 → WebSocket → MSE                        ║');
console.log('╠══════════════════════════════════════════════════════════════╣');
console.log(`║  WebSocket:  ws://localhost:${CONFIG.WSS_PORT}                             ║`);
console.log(`║  HTTP API:   http://localhost:${CONFIG.HTTP_PORT}/status                   ║`);
console.log(`║  Resolution: ${CONFIG.SCREENRECORD_SIZE}                                     ║`);
console.log(`║  Bitrate:    ${CONFIG.SCREENRECORD_BITRATE}                                        ║`);
console.log('╚══════════════════════════════════════════════════════════════╝');
console.log('');

// Verify ADB connection on startup
checkAdbConnection().then((status) => {
    if (status.connected) {
        console.log(`[STARTUP] ADB devices found: ${status.devices.join(', ')}`);
        getDeviceSize();
    } else {
        console.warn('[STARTUP] No ADB devices connected. Please connect a device.');
    }
});
