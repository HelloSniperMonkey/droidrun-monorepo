/**
 * WebRTC Signaling Server for Droidrun Portal
 * 
 * This server acts as a signaling relay between:
 * 1. Droidrun Portal app (connects via reverse WebSocket)
 * 2. Browser clients (connects via WebSocket)
 * 
 * Architecture:
 * - Portal app connects outbound to ws://localhost:8082/device
 * - Browser connects to ws://localhost:8082/browser
 * - Server relays WebRTC signaling (offer/answer/ICE) between them
 * 
 * Protocol (Portal → Server → Browser):
 * 1. Browser sends: { action: "start_stream", width, height, fps }
 * 2. Server sends to Portal: { method: "stream/start", params: {...} }
 * 3. Portal sends: { method: "webrtc/offer", params: { sdp } }
 * 4. Server relays to Browser: { type: "offer", sdp }
 * 5. Browser sends: { type: "answer", sdp }
 * 6. Server sends to Portal: { method: "webrtc/answer", params: { sdp } }
 * 7. ICE candidates exchanged via webrtc/ice
 */

const WebSocket = require('ws');
const http = require('http');
const crypto = require('crypto');

const PORT = 8082;
const HTTP_PORT = 8083;

// Connection state
let deviceSocket = null;
let browserSocket = null;
let currentSessionId = null;
let messageId = 0;

// Pending responses (for JSON-RPC)
const pendingResponses = new Map();

// =============================================================================
// HTTP Status Server
// =============================================================================

const httpServer = http.createServer((req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Content-Type', 'application/json');

    if (req.method === 'OPTIONS') {
        res.writeHead(200);
        res.end();
        return;
    }

    if (req.url === '/status') {
        res.writeHead(200);
        res.end(JSON.stringify({
            service: 'webrtc-signaling',
            deviceConnected: deviceSocket !== null && deviceSocket.readyState === WebSocket.OPEN,
            browserConnected: browserSocket !== null && browserSocket.readyState === WebSocket.OPEN,
            sessionId: currentSessionId
        }));
        return;
    }

    res.writeHead(404);
    res.end(JSON.stringify({ error: 'Not found' }));
});

httpServer.listen(HTTP_PORT, () => {
    console.log(`HTTP status server on port ${HTTP_PORT}`);
});

// =============================================================================
// WebSocket Server
// =============================================================================

const wss = new WebSocket.Server({ port: PORT });
console.log(`WebSocket signaling server on port ${PORT}`);

wss.on('connection', (ws, req) => {
    const path = req.url;
    console.log(`New connection from path: ${path}`);

    if (path === '/device') {
        handleDeviceConnection(ws);
    } else if (path === '/browser') {
        handleBrowserConnection(ws);
    } else {
        console.log(`Unknown path: ${path}, closing connection`);
        ws.close(4000, 'Unknown path');
    }
});

// =============================================================================
// Device Connection Handler (Droidrun Portal)
// =============================================================================

function handleDeviceConnection(ws) {
    console.log('Device connected');

    // Close existing device connection if any
    if (deviceSocket && deviceSocket.readyState === WebSocket.OPEN) {
        console.log('Closing existing device connection');
        deviceSocket.close();
    }

    deviceSocket = ws;

    // Notify browser that device is connected
    sendToBrowser({ type: 'device_connected' });

    ws.on('message', (message) => {
        try {
            const data = JSON.parse(message.toString());
            handleDeviceMessage(data);
        } catch (e) {
            console.error('Failed to parse device message:', e);
        }
    });

    ws.on('close', (code, reason) => {
        console.log(`Device disconnected: code=${code}, reason=${reason}`);
        deviceSocket = null;
        currentSessionId = null;
        sendToBrowser({ type: 'device_disconnected' });
    });

    ws.on('error', (err) => {
        console.error('Device socket error:', err);
    });
}

function handleDeviceMessage(data) {
    const method = data.method;
    const params = data.params || {};
    const id = data.id;

    // Handle JSON-RPC response
    if (data.result !== undefined || data.error !== undefined) {
        const pending = pendingResponses.get(id);
        if (pending) {
            pendingResponses.delete(id);
            if (data.error) {
                console.error(`Device error for request ${id}:`, data.error);
                sendToBrowser({ type: 'error', error: data.error });
            } else {
                console.log(`Device response for request ${id}:`, data.result);
                // Handle stream/start response
                if (pending.method === 'stream/start') {
                    sendToBrowser({ type: 'stream_starting', result: data.result });
                }
            }
        }
        return;
    }

    console.log(`Device message: method=${method}`);

    switch (method) {
        case 'webrtc/offer':
            // Device generated an offer, relay to browser
            sendToBrowser({
                type: 'offer',
                sdp: params.sdp,
                sessionId: params.sessionId || currentSessionId
            });
            break;

        case 'webrtc/ice':
            // Device ICE candidate, relay to browser
            sendToBrowser({
                type: 'ice_candidate',
                candidate: params.candidate,
                sdpMid: params.sdpMid,
                sdpMLineIndex: params.sdpMLineIndex,
                sessionId: params.sessionId
            });
            break;

        case 'webrtc/answer':
            // Device generated an answer (waitForOffer=true mode), relay to browser
            sendToBrowser({
                type: 'answer',
                sdp: params.sdp,
                sessionId: params.sessionId
            });
            break;

        case 'stream/ready':
            // Device is ready for offer from browser
            sendToBrowser({
                type: 'stream_ready',
                sessionId: params.sessionId
            });
            break;

        case 'stream/error':
            sendToBrowser({
                type: 'stream_error',
                error: params.error,
                message: params.message,
                sessionId: params.sessionId
            });
            break;

        case 'stream/stopped':
            sendToBrowser({
                type: 'stream_stopped',
                reason: params.reason,
                sessionId: params.sessionId
            });
            currentSessionId = null;
            break;

        default:
            console.log(`Unknown device method: ${method}`);
    }
}

// =============================================================================
// Browser Connection Handler
// =============================================================================

function handleBrowserConnection(ws) {
    console.log('Browser connected');

    // Close existing browser connection if any
    if (browserSocket && browserSocket.readyState === WebSocket.OPEN) {
        console.log('Closing existing browser connection');
        browserSocket.close();
    }

    browserSocket = ws;

    // Notify browser of current device state
    ws.send(JSON.stringify({
        type: 'connection_status',
        deviceConnected: deviceSocket !== null && deviceSocket.readyState === WebSocket.OPEN
    }));

    ws.on('message', (message) => {
        try {
            const data = JSON.parse(message.toString());
            handleBrowserMessage(data);
        } catch (e) {
            console.error('Failed to parse browser message:', e);
        }
    });

    ws.on('close', (code, reason) => {
        console.log(`Browser disconnected: code=${code}, reason=${reason}`);
        browserSocket = null;
        // Stop stream if browser disconnects
        if (currentSessionId) {
            sendToDevice({
                id: messageId++,
                method: 'stream/stop',
                params: {}
            });
            currentSessionId = null;
        }
    });

    ws.on('error', (err) => {
        console.error('Browser socket error:', err);
    });
}

function handleBrowserMessage(data) {
    const action = data.action || data.type;
    console.log(`Browser message: action=${action}`);

    switch (action) {
        case 'start_stream':
            startStream(data);
            break;

        case 'stop_stream':
            stopStream();
            break;

        case 'answer':
            // Browser answer to device offer
            sendToDevice({
                id: messageId++,
                method: 'webrtc/answer',
                params: {
                    sdp: data.sdp,
                    sessionId: currentSessionId
                }
            });
            break;

        case 'offer':
            // Browser offer (waitForOffer=true mode)
            sendToDevice({
                id: messageId++,
                method: 'webrtc/offer',
                params: {
                    sdp: data.sdp,
                    sessionId: currentSessionId
                }
            });
            break;

        case 'ice_candidate':
            // Browser ICE candidate
            sendToDevice({
                id: messageId++,
                method: 'webrtc/ice',
                params: {
                    candidate: data.candidate,
                    sdpMid: data.sdpMid,
                    sdpMLineIndex: data.sdpMLineIndex,
                    sessionId: currentSessionId
                }
            });
            break;

        case 'ping':
            sendToBrowser({ type: 'pong' });
            break;

        case 'device_command':
            // Forward touch/key commands to device
            sendToDevice({
                id: messageId++,
                method: 'device/command',
                params: {
                    ...data,
                    sessionId: currentSessionId
                }
            });
            break;

        default:
            console.log(`Unknown browser action: ${action}`);
    }
}

// =============================================================================
// Stream Control
// =============================================================================

function startStream(options) {
    if (!deviceSocket || deviceSocket.readyState !== WebSocket.OPEN) {
        sendToBrowser({
            type: 'error',
            error: 'Device not connected',
            message: 'Please connect the Droidrun Portal app first'
        });
        return;
    }

    // Generate session ID
    currentSessionId = crypto.randomUUID();

    const width = options.width || 720;
    const height = options.height || 1280;
    const fps = options.fps || 30;
    const waitForOffer = options.waitForOffer || false;

    // ICE servers configuration - includes TURN for NAT traversal
    const iceServers = options.iceServers || [
        { urls: ['stun:stun.l.google.com:19302'] },
        { urls: ['stun:stun.relay.metered.ca:80'] },
        {
            urls: ['turn:global.relay.metered.ca:80'],
            username: 'e8dd65c92f6d2a466146ce6e',
            credential: 'rQq9Hfqk/XqCzJg8'
        },
        {
            urls: ['turn:global.relay.metered.ca:443'],
            username: 'e8dd65c92f6d2a466146ce6e',
            credential: 'rQq9Hfqk/XqCzJg8'
        },
        {
            urls: ['turns:global.relay.metered.ca:443?transport=tcp'],
            username: 'e8dd65c92f6d2a466146ce6e',
            credential: 'rQq9Hfqk/XqCzJg8'
        }
    ];

    const id = messageId++;
    pendingResponses.set(id, { method: 'stream/start' });

    sendToDevice({
        id: id,
        method: 'stream/start',
        params: {
            width: width,
            height: height,
            fps: fps,
            sessionId: currentSessionId,
            waitForOffer: waitForOffer,
            iceServers: iceServers
        }
    });

    console.log(`Starting stream: ${width}x${height}@${fps}fps, sessionId=${currentSessionId}`);
}

function stopStream() {
    if (!deviceSocket || deviceSocket.readyState !== WebSocket.OPEN) {
        return;
    }

    sendToDevice({
        id: messageId++,
        method: 'stream/stop',
        params: {}
    });

    currentSessionId = null;
    console.log('Stream stopped');
}

// =============================================================================
// Utility Functions
// =============================================================================

function sendToDevice(data) {
    if (deviceSocket && deviceSocket.readyState === WebSocket.OPEN) {
        const msg = JSON.stringify(data);
        console.log(`→ Device: ${msg.substring(0, 200)}${msg.length > 200 ? '...' : ''}`);
        deviceSocket.send(msg);
    } else {
        console.warn('Cannot send to device: not connected');
    }
}

function sendToBrowser(data) {
    if (browserSocket && browserSocket.readyState === WebSocket.OPEN) {
        const msg = JSON.stringify(data);
        console.log(`→ Browser: ${msg.substring(0, 200)}${msg.length > 200 ? '...' : ''}`);
        browserSocket.send(msg);
    } else {
        console.warn('Cannot send to browser: not connected');
    }
}

// =============================================================================
// Cleanup
// =============================================================================

process.on('SIGINT', () => {
    console.log('Shutting down...');
    if (deviceSocket) deviceSocket.close();
    if (browserSocket) browserSocket.close();
    wss.close();
    httpServer.close();
    process.exit();
});

process.on('SIGTERM', () => {
    process.exit();
});

console.log('');
console.log('WebRTC Signaling Server ready!');
console.log('');
console.log('Endpoints:');
console.log(`  Device (Portal):  ws://localhost:${PORT}/device`);
console.log(`  Browser:          ws://localhost:${PORT}/browser`);
console.log(`  Status:           http://localhost:${HTTP_PORT}/status`);
console.log('');
console.log('To connect the Portal app, configure reverse connection URL:');
console.log(`  ws://<your-ip>:${PORT}/device`);
console.log('');
