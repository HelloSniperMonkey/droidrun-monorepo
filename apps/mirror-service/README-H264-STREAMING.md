# Low-Latency Android Screen Streaming via H.264/fMP4/MSE

A production-grade Android screen streaming pipeline using raw H.264, fragmented MP4, and Media Source Extensions.

## Architecture

```
┌─────────────────┐    ┌─────────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Android Phone  │───►│  adb screenrecord   │───►│  FFmpeg (once)   │───►│  WebSocket      │
│                 │    │  --output-format=h264│    │  repackage to    │    │  Binary frames  │
│                 │    │  raw H.264 stream   │    │  fragmented MP4  │    │  to browser     │
└─────────────────┘    └─────────────────────┘    └──────────────────┘    └─────────────────┘
                                                                                    │
                                                                                    ▼
                                                         ┌──────────────────────────────────────┐
                                                         │           Browser MSE                 │
                                                         │  MediaSource → SourceBuffer → <video>│
                                                         └──────────────────────────────────────┘
```

## Key Design Principles

1. **Single FFmpeg Process**: One persistent FFmpeg per session - no per-frame spawning
2. **No Decoding**: FFmpeg uses `-c copy` to repackage only (no CPU-intensive transcoding)
3. **Binary WebSocket**: Raw fMP4 chunks sent as binary frames (minimal overhead)
4. **MSE Playback**: Browser plays fMP4 natively via `<video>` element
5. **No Intermediate Files**: Pure streaming, nothing written to disk

## Components

| Component | File | Description |
|-----------|------|-------------|
| Server | `server-h264-fmp4.js` | Node.js WebSocket server with adb + FFmpeg pipeline |
| Client | `DeviceMirrorMSE.tsx` | React component with MSE playback |

## Prerequisites

- **Node.js** 18+ 
- **FFmpeg** (with H.264 demuxer support)
- **ADB** (Android Debug Bridge)
- **Android device** with USB debugging enabled

### Verify Prerequisites

```bash
# Check FFmpeg
ffmpeg -version | head -1

# Check ADB
adb version

# Check connected devices
adb devices
```

## Installation

```bash
cd apps/mirror-service
npm install
```

## Running the Server

```bash
# Start the H.264/fMP4 streaming server
node server-h264-fmp4.js
```

Expected output:
```
╔══════════════════════════════════════════════════════════════╗
║  Low-Latency Android Screen Streaming Server                 ║
║  Mode: H.264 → fMP4 → WebSocket → MSE                        ║
╠══════════════════════════════════════════════════════════════╣
║  WebSocket:  ws://localhost:8080                             ║
║  HTTP API:   http://localhost:8081/status                    ║
║  Resolution: 720x1280                                        ║
║  Bitrate:    4M                                              ║
╚══════════════════════════════════════════════════════════════╝

[STARTUP] ADB devices found: RF8R91XXXXX
[INFO] Device size: 1080x2340
```

## Using the Client

### Option 1: Use the DeviceMirrorMSE component

Replace your existing DeviceMirror import:

```tsx
// Before
import { DeviceMirror } from "@/components/DeviceMirror";

// After (for H.264/MSE streaming)
import { DeviceMirrorMSE } from "@/components/DeviceMirrorMSE";
```

### Option 2: Standalone HTML test page

```html
<!DOCTYPE html>
<html>
<head>
    <title>Android Screen Stream</title>
    <style>
        body { background: #000; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
        video { max-height: 90vh; max-width: 90vw; }
        #stats { position: fixed; top: 10px; left: 10px; color: #0f0; font-family: monospace; font-size: 12px; }
    </style>
</head>
<body>
    <video id="video" autoplay muted playsinline></video>
    <div id="stats"></div>
    <script>
        const CODEC = 'video/mp4; codecs="avc1.42E01E"';
        const video = document.getElementById('video');
        const stats = document.getElementById('stats');
        
        let bytesReceived = 0;
        let chunksReceived = 0;
        
        const mediaSource = new MediaSource();
        video.src = URL.createObjectURL(mediaSource);
        
        mediaSource.addEventListener('sourceopen', () => {
            const sourceBuffer = mediaSource.addSourceBuffer(CODEC);
            const queue = [];
            let isAppending = false;
            
            const processQueue = () => {
                if (isAppending || queue.length === 0) return;
                if (mediaSource.readyState !== 'open') return;
                if (sourceBuffer.updating) return;
                
                isAppending = true;
                sourceBuffer.appendBuffer(queue.shift());
            };
            
            sourceBuffer.addEventListener('updateend', () => {
                isAppending = false;
                processQueue();
                
                // Trim buffer to minimize latency
                if (sourceBuffer.buffered.length > 0) {
                    const end = sourceBuffer.buffered.end(0);
                    if (end - video.currentTime > 1) {
                        video.currentTime = end - 0.1;
                    }
                }
            });
            
            const ws = new WebSocket('ws://localhost:8080');
            ws.binaryType = 'arraybuffer';
            
            ws.onmessage = (e) => {
                if (e.data instanceof ArrayBuffer) {
                    bytesReceived += e.data.byteLength;
                    chunksReceived++;
                    queue.push(e.data);
                    processQueue();
                    if (video.paused) video.play();
                }
            };
            
            // Stats display
            setInterval(() => {
                const buffered = sourceBuffer.buffered.length > 0 
                    ? (sourceBuffer.buffered.end(0) - video.currentTime).toFixed(2) 
                    : 0;
                stats.textContent = `Received: ${(bytesReceived/1024/1024).toFixed(2)} MB | Chunks: ${chunksReceived} | Buffer: ${buffered}s`;
            }, 500);
        });
    </script>
</body>
</html>
```

## Data Flow Explanation

### 1. Capture Stage (Android → Host)

```bash
adb exec-out screenrecord --output-format=h264 --size 720x1280 --bit-rate 4M -
```

- **`exec-out`**: Streams binary output directly (no shell escaping)
- **`--output-format=h264`**: Raw H.264 elementary stream (no MP4 container)
- **`--size 720x1280`**: Lower resolution = faster encoding = lower latency
- **`--bit-rate 4M`**: 4 Mbps is a good balance
- **`-`**: Output to stdout

### 2. Repackaging Stage (FFmpeg)

```bash
ffmpeg -f h264 -i pipe:0 -c copy -f mp4 -movflags frag_keyframe+empty_moov+default_base_moof pipe:1
```

- **`-f h264`**: Input is raw H.264 elementary stream
- **`-i pipe:0`**: Read from stdin (piped from adb)
- **`-c copy`**: **NO DECODING** - just remux the stream
- **`-f mp4`**: Output as MP4 container
- **`-movflags`**:
  - `frag_keyframe`: New fragment at each keyframe
  - `empty_moov`: Write moov (init segment) at start
  - `default_base_moof`: Required for MSE compatibility
- **`pipe:1`**: Output to stdout

### 3. Transport Stage (WebSocket)

- FFmpeg stdout is read in chunks
- Each chunk is sent as a **binary** WebSocket frame
- Backpressure is monitored via `ws.bufferedAmount`
- If buffer exceeds 1MB, reading pauses until it drains

### 4. Playback Stage (MSE)

The browser receives fMP4 data as:
1. **Init segment** (ftyp + moov atoms) - first ~1KB
2. **Media segments** (moof + mdat atoms) - continuous chunks

The init segment contains:
- Codec information (H.264 profile/level)
- Video dimensions
- Timing info

Media segments contain:
- Compressed video frames
- Timing/duration metadata

## Latency Analysis

### Sources of Latency

| Stage | Typical Latency | Notes |
|-------|-----------------|-------|
| Android encoder | 50-100ms | H.264 encoding on device |
| USB transfer | 5-10ms | USB 2.0/3.0 |
| FFmpeg repackaging | 0-10ms | Just header rewriting |
| WebSocket | 1-5ms | Local network |
| MSE buffer | 50-100ms | Minimum for smooth playback |
| **Total** | **~150-250ms** | Under good conditions |

### Minimizing Latency

1. **Lower resolution** (`--size 480x854`) reduces encoder work
2. **Lower bitrate** (`--bit-rate 2M`) reduces USB/network pressure
3. **Aggressive buffer trimming** in MSE (keep < 1 second)
4. **Playback rate adjustment** to catch up when behind

## Common Failure Modes & Fixes

### 1. "MediaSource not supported"

**Cause**: Browser doesn't support MSE (Safari iOS, some older browsers)

**Fix**: Use a polyfill or fallback to MJPEG mode

### 2. QuotaExceededError

**Cause**: SourceBuffer is full

**Fix**: Trim old data more aggressively:
```javascript
if (buffered.end(0) - currentTime > 0.5) {
    sourceBuffer.remove(buffered.start(0), currentTime - 0.3);
}
```

### 3. "No ADB devices"

**Cause**: USB debugging not enabled or device not authorized

**Fix**:
```bash
adb kill-server
adb start-server
adb devices  # Should prompt on phone for authorization
```

### 4. Video doesn't play / stays black

**Probable cause**: Codec mismatch

**Debug**:
```javascript
console.log(MediaSource.isTypeSupported('video/mp4; codecs="avc1.42E01E"'));  // Should be true
console.log(MediaSource.isTypeSupported('video/mp4; codecs="avc1.640028"'));  // Try High Profile
```

**Fix**: Try different codec strings:
- `avc1.42E01E` - Baseline Profile, Level 3.0
- `avc1.4D401E` - Main Profile, Level 3.0  
- `avc1.640028` - High Profile, Level 4.0

### 5. Screenrecord exits after 3 minutes

**Cause**: Android default limit

**Fix**: The server automatically restarts the pipeline. Brief glitch is expected.

### 6. High CPU usage

**Check FFmpeg is using `-c copy`** (no transcoding). CPU should be < 5%.

If high:
```bash
# Verify FFmpeg is not decoding
ps aux | grep ffmpeg
# Should show "copy" in arguments
```

### 7. WebSocket disconnects

**Cause**: Often backpressure issue

**Debug**: Check server logs for `[BACKPRESSURE]` messages

**Fix**: Reduce bitrate or resolution

## Performance Tuning

### For Low-End Devices

```javascript
const CONFIG = {
    SCREENRECORD_SIZE: '480x854',  // Smaller
    SCREENRECORD_BITRATE: '2M',    // Lower
};
```

### For Best Quality

```javascript
const CONFIG = {
    SCREENRECORD_SIZE: '1080x1920',  // Native
    SCREENRECORD_BITRATE: '8M',       // Higher
};
```

### For Lowest Latency

```javascript
// Server
SCREENRECORD_SIZE: '480x854',
SCREENRECORD_BITRATE: '1M',

// Client
MAX_BUFFER_SECONDS: 0.3,  // Very small buffer
```

## API Reference

### WebSocket Messages (Server → Client)

```typescript
// Device information (sent once on connect)
{ type: 'device_info', width: number, height: number, codec: string, mode: string }

// Volume update (periodic)
{ type: 'volume_info', level: number, max: number }

// Ping response
{ type: 'pong' }

// Error
{ type: 'error', message: string }

// Stats (on request)
{ type: 'stats', bytesSent: number, chunkCount: number, uptime: number, ... }
```

### WebSocket Messages (Client → Server)

```typescript
// Touch tap
{ type: 'tap', x: number, y: number }  // x,y in 0-1 range

// Swipe
{ type: 'swipe', startX: number, startY: number, endX: number, endY: number, duration: number }

// Key press
{ type: 'key', keycode: 'back' | 'home' | 'recent' | 'volume_up' | 'volume_down' | number }

// Ping
{ type: 'ping' }

// Request stats
{ type: 'stats' }
```

### Binary Messages

All other WebSocket frames are binary fMP4 chunks that should be appended directly to the SourceBuffer.

## Comparison with Alternatives

| Method | FPS | Latency | CPU | Quality |
|--------|-----|---------|-----|---------|
| **This (H.264/fMP4/MSE)** | 30-60 | ~150ms | Low | High |
| MJPEG (screencap) | 1-5 | ~500ms | Medium | Medium |
| scrcpy | 30-120 | ~50ms | Low | High |
| WebRTC | 30-60 | ~100ms | Medium | High |

**Why not scrcpy?** This implementation is explicitly requested to avoid scrcpy to demonstrate a pure adb/ffmpeg/mse pipeline.

## Files

```
apps/mirror-service/
├── server-h264-fmp4.js     # H.264/fMP4 streaming server (USE THIS)
├── server.js               # Legacy MJPEG server
├── package.json
└── README-H264-STREAMING.md

apps/web/src/components/
├── DeviceMirrorMSE.tsx     # MSE-based player (USE THIS)
└── DeviceMirror.tsx        # Legacy MJPEG player
```
