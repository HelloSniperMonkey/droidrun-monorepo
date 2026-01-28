const WebSocket = require('ws');
const { spawn, exec } = require('child_process');
const http = require('http');

const WSS_PORT = 8080;
const HTTP_PORT = 8081;

// Device screen dimensions (will be updated dynamically)
let deviceWidth = 1264;
let deviceHeight = 2780;

// Get device screen size
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

// Check if ADB device is connected
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

// Simple HTTP server for status checks
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
            adb: adbStatus,
            deviceSize: size
        }));
        return;
    }

    res.writeHead(404);
    res.end(JSON.stringify({ error: 'Not found' }));
});

httpServer.listen(HTTP_PORT, () => {
    console.log(`HTTP status server listening on port ${HTTP_PORT}`);
});

const wss = new WebSocket.Server({ port: WSS_PORT });
console.log(`WebSocket server listening on port ${WSS_PORT}`);

// Inject touch event via ADB
function injectTouch(type, x, y) {
    // Convert normalized coordinates (0-1) to device pixels
    const deviceX = Math.round(x * deviceWidth);
    const deviceY = Math.round(y * deviceHeight);

    let cmd;
    switch (type) {
        case 'tap':
            cmd = `adb shell input tap ${deviceX} ${deviceY}`;
            break;
        case 'swipe':
            // For swipe, we need start and end coordinates - handled separately
            return;
        case 'down':
        case 'up':
        case 'move':
            // For more complex gestures, use sendevent (requires root) or motionevent
            // Fallback to tap for now
            if (type === 'up') {
                cmd = `adb shell input tap ${deviceX} ${deviceY}`;
            }
            break;
        default:
            return;
    }

    if (cmd) {
        exec(cmd, (error) => {
            if (error) {
                console.error(`Touch injection failed: ${error.message}`);
            }
        });
    }
}

// Inject swipe gesture
function injectSwipe(startX, startY, endX, endY, duration = 300) {
    const sx = Math.round(startX * deviceWidth);
    const sy = Math.round(startY * deviceHeight);
    const ex = Math.round(endX * deviceWidth);
    const ey = Math.round(endY * deviceHeight);

    exec(`adb shell input swipe ${sx} ${sy} ${ex} ${ey} ${duration}`, (error) => {
        if (error) {
            console.error(`Swipe injection failed: ${error.message}`);
        }
    });
}

// Inject key event
function injectKey(keycode) {
    const keycodes = {
        'back': 4,
        'home': 3,
        'recent': 187,
        'power': 26,
        'volume_up': 24,
        'volume_down': 25
    };

    const code = keycodes[keycode] || keycode;
    exec(`adb shell input keyevent ${code}`, (error) => {
        if (error) {
            console.error(`Key injection failed: ${error.message}`);
        }
    });
}

wss.on('connection', async (ws) => {
    console.log('Client connected');

    // Get device size before streaming
    await getDeviceSize();

    // Send device info to client
    ws.send(JSON.stringify({
        type: 'device_info',
        width: deviceWidth,
        height: deviceHeight
    }));

    let isStreaming = true;
    let frameCount = 0;
    
    // Use MJPEG streaming - capture frames continuously using screencap
    // This is more reliable for browser streaming than scrcpy record mode
    const captureFrame = () => {
        if (!isStreaming || ws.readyState !== WebSocket.OPEN) return;
        
        // Use adb exec-out screencap to get raw PNG, pipe to ffmpeg for JPEG conversion
        const capture = spawn('adb', ['exec-out', 'screencap', '-p'], {
            stdio: ['ignore', 'pipe', 'pipe']
        });
        
        const chunks = [];
        
        capture.stdout.on('data', (chunk) => {
            chunks.push(chunk);
        });
        
        capture.on('close', (code) => {
            if (code === 0 && chunks.length > 0 && isStreaming) {
                const pngBuffer = Buffer.concat(chunks);
                
                // Convert PNG to JPEG using ffmpeg for smaller size
                const convert = spawn('ffmpeg', [
                    '-hide_banner',
                    '-loglevel', 'error',
                    '-i', 'pipe:0',
                    '-vf', 'scale=720:-1',  // Scale down for faster transfer
                    '-q:v', '5',             // JPEG quality (2-31, lower is better)
                    '-f', 'mjpeg',
                    'pipe:1'
                ], {
                    stdio: ['pipe', 'pipe', 'pipe']
                });
                
                const jpegChunks = [];
                
                convert.stdout.on('data', (chunk) => {
                    jpegChunks.push(chunk);
                });
                
                convert.on('close', () => {
                    if (jpegChunks.length > 0 && ws.readyState === WebSocket.OPEN) {
                        const jpegBuffer = Buffer.concat(jpegChunks);
                        ws.send(jpegBuffer);
                        frameCount++;
                        if (frameCount % 30 === 0) {
                            console.log(`Sent ${frameCount} frames`);
                        }
                    }
                    // Capture next frame - aim for ~15 FPS
                    if (isStreaming) {
                        setTimeout(captureFrame, 66);
                    }
                });
                
                convert.stdin.write(pngBuffer);
                convert.stdin.end();
            } else if (isStreaming) {
                // Retry on failure
                setTimeout(captureFrame, 100);
            }
        });
        
        capture.on('error', (err) => {
            console.error('Capture error:', err.message);
            if (isStreaming) {
                setTimeout(captureFrame, 500);
            }
        });
    };
    
    // Start capturing
    console.log('Starting MJPEG stream...');
    captureFrame();

    ws.on('close', () => {
        console.log('Client disconnected, stopping stream');
        isStreaming = false;
    });

    ws.on('error', (err) => {
        console.error('WebSocket error:', err);
        isStreaming = false;
    });

    // Handle incoming control messages
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
                default:
                    console.log('Unknown message type:', data.type);
            }
        } catch (e) {
            // Binary data from potential echo, ignore
        }
    });
});
