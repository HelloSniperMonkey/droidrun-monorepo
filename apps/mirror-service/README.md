# Android Screen Mirror Service

WebSocket-based Android screen mirroring service for Iron Claw web interface.

## Requirements

- **scrcpy** - Android screen mirroring tool
  ```bash
  brew install scrcpy
  ```

- **ffmpeg** - Video encoding/transcoding
  ```bash
  brew install ffmpeg
  ```

- **ADB** - Android Debug Bridge (comes with Android Studio or standalone)
  ```bash
  brew install android-platform-tools
  ```

## Setup

1. Connect your Android device via USB
2. Enable USB debugging on your device
3. Verify ADB connection:
   ```bash
   adb devices
   ```

## Running the Service

```bash
npm start
```

The service will:
- Start WebSocket server on port **8080**
- Start HTTP status server on port **8081**
- Stream video from scrcpy → ffmpeg → WebSocket → Browser

## How It Works

1. **scrcpy** captures the Android screen and outputs H.264 video to stdout
2. **ffmpeg** transcodes the H.264 stream to WebM (VP8 codec) for browser compatibility
3. **WebSocket** streams the WebM chunks to the browser in real-time
4. **MediaSource API** in the browser decodes and plays the video stream

## Touch Control

The service supports:
- **Tap**: Click/touch on the video
- **Swipe**: Touch and drag gestures
- **Navigation**: Back, Home, Recent Apps buttons
- **Volume**: Volume Up/Down controls

Touch coordinates are automatically scaled from normalized (0-1) to device pixels.

## Troubleshooting

### No device found
```bash
# Check ADB connection
adb devices

# If offline, reconnect
adb kill-server
adb start-server
```

### Video not streaming
- Ensure scrcpy is installed: `scrcpy --version`
- Ensure ffmpeg is installed: `ffmpeg -version`
- Check terminal for errors

### Touch not working
- Verify device size is detected (check console logs)
- Ensure touch coordinates are being sent (check browser console)
