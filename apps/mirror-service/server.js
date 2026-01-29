const WebSocket = require('ws');
const { spawn, exec, execSync } = require('child_process');
const http = require('http');

const WSS_PORT = 8080;
const HTTP_PORT = 8081;

// Device screen dimensions
let deviceWidth = 1080;
let deviceHeight = 1920;

// Streaming configuration
const CONFIG = {
    // Capture settings
    SCALE_HEIGHT: 640,          // Scale to this height
    JPEG_QUALITY: 5,           // Quality 2-31, lower=better
    // Rate limiting
    MIN_FRAME_INTERVAL: 200,    // Minimum ms between frames (5 FPS max)
    // Retry settings
    MAX_CONSECUTIVE_ERRORS: 5
};

// =============================================================================
// Device Management
// =============================================================================

function getDeviceSize() {
    return new Promise((resolve) => {
        exec('adb shell wm size', (error, stdout) => {
            if (!error && stdout) {
                const match = stdout.match(/(\d+)x(\d+)/);
                if (match) {
                    deviceWidth = parseInt(match[1]);
                    deviceHeight = parseInt(match[2]);
                    console.log(`Device size: ${deviceWidth}x${deviceHeight}`);
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
// Input Injection
// =============================================================================

function injectTouch(type, x, y) {
    const deviceX = Math.round(x * deviceWidth);
    const deviceY = Math.round(y * deviceHeight);
    console.log(`Touch: type=${type}, device=(${deviceX}, ${deviceY})`);

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
            if (error) console.error(`Touch failed: ${error.message}`);
        });
    }
}

function injectSwipe(startX, startY, endX, endY, duration = 300) {
    const sx = Math.round(startX * deviceWidth);
    const sy = Math.round(startY * deviceHeight);
    const ex = Math.round(endX * deviceWidth);
    const ey = Math.round(endY * deviceHeight);

    exec(`adb shell input swipe ${sx} ${sy} ${ex} ${ey} ${duration}`, (error) => {
        if (error) console.error(`Swipe failed: ${error.message}`);
    });
}

function injectKey(keycode) {
    const keycodes = {
        'back': 4, 'home': 3, 'recent': 187,
        'power': 26, 'volume_up': 24, 'volume_down': 25
    };
    const code = keycodes[keycode] || keycode;
    exec(`adb shell input keyevent ${code}`, (error) => {
        if (error) console.error(`Key failed: ${error.message}`);
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
        res.end(JSON.stringify({ service: 'running', adb: adbStatus, deviceSize: size }));
        return;
    }

    res.writeHead(404);
    res.end(JSON.stringify({ error: 'Not found' }));
});

httpServer.listen(HTTP_PORT, () => {
    console.log(`HTTP status server on port ${HTTP_PORT}`);
});

// =============================================================================
// WebSocket Server with Optimized MJPEG Streaming
// =============================================================================

const wss = new WebSocket.Server({ port: WSS_PORT });
console.log(`WebSocket server on port ${WSS_PORT}`);

wss.on('connection', async (ws) => {
    console.log('Client connected');

    await getDeviceSize();

    // Send device info
    ws.send(JSON.stringify({
        type: 'device_info',
        width: deviceWidth,
        height: deviceHeight
    }));

    // Send initial volume
    const vol = await getVolume();
    if (vol) {
        ws.send(JSON.stringify({
            type: 'volume_info',
            level: vol.current,
            max: vol.max
        }));
    }

    // Volume polling
    const volumeInterval = setInterval(async () => {
        if (ws.readyState === WebSocket.OPEN) {
            const v = await getVolume();
            if (v) ws.send(JSON.stringify({ type: 'volume_info', level: v.current, max: v.max }));
        }
    }, 2000);

    let isStreaming = true;
    let frameCount = 0;
    let lastFpsTime = Date.now();
    let lastFrameTime = 0;
    let consecutiveErrors = 0;
    let isCapturing = false;

    // ==========================================================================
    // Single-threaded capture with proper error handling
    // ==========================================================================

    const captureFrame = async () => {
        if (!isStreaming || ws.readyState !== WebSocket.OPEN || isCapturing) {
            if (isStreaming) setTimeout(captureFrame, 100);
            return;
        }

        // Rate limiting
        const now = Date.now();
        const elapsed = now - lastFrameTime;
        if (elapsed < CONFIG.MIN_FRAME_INTERVAL) {
            setTimeout(captureFrame, CONFIG.MIN_FRAME_INTERVAL - elapsed);
            return;
        }

        isCapturing = true;
        const frameStart = now;

        try {
            // Single optimized pipeline: adb screencap | ffmpeg -> JPEG
            const capture = spawn('adb', ['exec-out', 'screencap', '-p'], {
                stdio: ['ignore', 'pipe', 'ignore']
            });

            const convert = spawn('ffmpeg', [
                '-hide_banner',
                '-loglevel', 'error',
                '-f', 'png_pipe',
                '-i', 'pipe:0',
                '-vf', `scale=-1:${CONFIG.SCALE_HEIGHT}`,
                '-q:v', String(CONFIG.JPEG_QUALITY),
                '-f', 'image2pipe',
                '-vcodec', 'mjpeg',
                'pipe:1'
            ], {
                stdio: ['pipe', 'pipe', 'ignore']
            });

            // Pipe screencap to ffmpeg
            capture.stdout.pipe(convert.stdin);

            const jpegChunks = [];
            convert.stdout.on('data', (chunk) => jpegChunks.push(chunk));

            convert.on('close', (code) => {
                isCapturing = false;

                if (code === 0 && jpegChunks.length > 0 && ws.readyState === WebSocket.OPEN && isStreaming) {
                    const jpegBuffer = Buffer.concat(jpegChunks);
                    const processingTime = Date.now() - frameStart;

                    consecutiveErrors = 0;
                    lastFrameTime = Date.now();

                    // Send metadata + frame
                    ws.send(JSON.stringify({
                        type: 'mjpeg_frame',
                        timestamp: Date.now(),
                        size: jpegBuffer.length,
                        processingTime
                    }));
                    ws.send(jpegBuffer);

                    frameCount++;
                } else {
                    consecutiveErrors++;
                }

                // Schedule next frame
                if (isStreaming && consecutiveErrors < CONFIG.MAX_CONSECUTIVE_ERRORS) {
                    setImmediate(captureFrame);
                } else if (consecutiveErrors >= CONFIG.MAX_CONSECUTIVE_ERRORS) {
                    console.error('Too many errors, pausing capture');
                    setTimeout(captureFrame, 2000);
                    consecutiveErrors = 0;
                }
            });

            capture.on('error', () => {
                isCapturing = false;
                consecutiveErrors++;
                if (isStreaming) setTimeout(captureFrame, 500);
            });

            convert.on('error', () => {
                isCapturing = false;
                consecutiveErrors++;
                if (isStreaming) setTimeout(captureFrame, 500);
            });

            // Timeout safety
            setTimeout(() => {
                if (isCapturing) {
                    capture.kill('SIGTERM');
                    convert.kill('SIGTERM');
                    isCapturing = false;
                }
            }, 10000);

        } catch (e) {
            console.error('Capture error:', e);
            isCapturing = false;
            if (isStreaming) setTimeout(captureFrame, 1000);
        }
    };

    // Start capture loop
    console.log('Starting MJPEG stream (optimized single-thread)...');
    captureFrame();

    // FPS logging
    const fpsInterval = setInterval(() => {
        const now = Date.now();
        const elapsed = (now - lastFpsTime) / 1000;
        if (elapsed > 0) {
            const fps = (frameCount / elapsed).toFixed(1);
            console.log(`FPS: ${fps}`);
            frameCount = 0;
            lastFpsTime = now;
        }
    }, 1000);

    // Handle client messages
    ws.on('message', (message) => {
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
                    ws.send(JSON.stringify({ type: 'pong' }));
                    break;
            }
        } catch {
            // Ignore
        }
    });

    // Cleanup
    ws.on('close', () => {
        console.log('Client disconnected');
        isStreaming = false;
        clearInterval(volumeInterval);
        clearInterval(fpsInterval);
    });

    ws.on('error', (err) => {
        console.error('WebSocket error:', err);
        isStreaming = false;
    });
});

// Cleanup
process.on('SIGINT', () => {
    console.log('Shutting down...');
    process.exit();
});

process.on('SIGTERM', () => {
    process.exit();
});

console.log('');
console.log('Mirror service ready!');
console.log('Using MJPEG streaming (ADB screencap + ffmpeg)');
console.log('Note: FPS depends on device screencap speed (~1-3 FPS typical)');
console.log('');
console.log('For faster streaming, consider:');
console.log('  1. Using scrcpy directly for display (60+ FPS)');
console.log('  2. Installing scrcpy v2.x with raw H.264 output');
console.log('  3. Running on a device with faster screencap');
