# Iron Claw - Architecture Documentation

## Overview

Iron Claw is a **Mobile-First Autonomous Agent Architecture** that orchestrates Android device automation, voice AI calls, job hunting, and personal productivity tasks. It consists of a Python-based FastAPI gateway, a React-based web interface, a standalone job hunter service, and a mirror service for device screen streaming.

---

## ASCII Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    USER INTERFACE LAYER                                  │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │                        React + TypeScript Web App (Port 5173)                    │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │    │
│  │  │   Sidebar    │  │  ChatArea    │  │ DeviceMirror │  │  CategoryPills     │  │    │
│  │  │  (Threads)   │  │  (Messages)  │  │(WebRTC/Cloud)│  │  (Action Groups)   │  │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────────────┘  │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                            │    │
│  │  │ ChatInput    │  │LanguageSwitch│  │SnowAnimation │                            │    │
│  │  │(Attachments) │  │(i18n Support)│  │ (Visual FX)  │                            │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                            │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│                                    │                                                    │
│                                    │ HTTP/WebSocket                                       │
│                                    ▼                                                    │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    GATEWAY LAYER (Port 8000)                             │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │                         Iron Claw Gateway (FastAPI)                              │    │
│  │                                                                                  │    │
│  │  ┌──────────────────────────────────────────────────────────────────────────┐   │    │
│  │  │                         API ROUTERS                                       │   │    │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │   │    │
│  │  │  │  chat   │ │  jobs   │ │  alarms │ │   tabs  │ │  wake   │ │  hitl   │ │   │    │
│  │  │  │/api/chat│ │/api/v1/ │ │/api/v1/ │ │/api/v1/ │ │/api/v1/ │ │/api/v1/ │ │   │    │
│  │  │  │         │ │  jobs   │ │ alarms  │ │  tabs   │ │  wake   │ │  hitl   │ │   │    │
│  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ │   │    │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐                                      │   │    │
│  │  │  │  speech │ │mobilerun│ │  health │                                      │   │    │
│  │  │  │/api/v1/ │ │/api/v1/ │ │  /health│                                      │   │    │
│  │  │  │  speech │ │mobilerun│ │         │                                      │   │    │
│  │  │  └─────────┘ └─────────┘ └─────────┘                                      │   │    │
│  │  └──────────────────────────────────────────────────────────────────────────┘   │    │
│  │                                                                                  │    │
│  │  ┌──────────────────────────────────────────────────────────────────────────┐   │    │
│  │  │                         SERVICE MODULES                                   │   │    │
│  │  │                                                                            │   │    │
│  │  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │   │    │
│  │  │  │  JobHunterService│  │TemporalGuardian  │  │ VapiInterrupter  │        │   │    │
│  │  │  │  (Resume Parser) │  │ (Alarm/Calendar) │  │ (Voice Wake-up)  │        │   │    │
│  │  │  └──────────────────┘  └──────────────────┘  └──────────────────┘        │   │    │
│  │  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │   │    │
│  │  │  │  TabManagerService│  │TelegramBotService│  │Personalization   │        │   │    │
│  │  │  │  (Chrome Tabs)   │  │  (HITL Notifier) │  │ (Wallpaper/Theme) │        │   │    │
│  │  │  └──────────────────┘  └──────────────────┘  └──────────────────┘        │   │    │
│  │  │  ┌──────────────────┐  ┌──────────────────┐                              │   │    │
│  │  │  │ ScheduleExtractor│  │   NanoBananaPro  │                              │   │    │
│  │  │  │ (OCR → Calendar) │  │ (AI Wallpaper)   │                              │   │    │
│  │  │  └──────────────────┘  └──────────────────┘                              │   │    │
│  │  └──────────────────────────────────────────────────────────────────────────┘   │    │
│  │                                                                                  │    │
│  │  ┌──────────────────────────────────────────────────────────────────────────┐   │    │
│  │  │                         CORE SERVICES                                     │   │    │
│  │  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │   │    │
│  │  │  │ ExecutionService │  │   HITLService    │  │TabExecutionService│        │   │    │
│  │  │  │ (MobileRun/Droid)│  │ (Human-in-Loop)  │  │ (Chrome Control)  │        │   │    │
│  │  │  └──────────────────┘  └──────────────────┘  └──────────────────┘        │   │    │
│  │  └──────────────────────────────────────────────────────────────────────────┘   │    │
│  │                                                                                  │    │
│  │  ┌──────────────────────────────────────────────────────────────────────────┐   │    │
│  │  │                         AGENT LAYER                                       │   │    │
│  │  │  ┌──────────────────┐  ┌──────────────────┐                              │   │    │
│  │  │  │  IronClawAgent   │  │  ADBConnection   │                              │   │    │
│  │  │  │ (DroidRun Wrapper)│  │ (Device Control) │                              │   │    │
│  │  │  └──────────────────┘  └──────────────────┘                              │   │    │
│  │  └──────────────────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ ADB / MobileRun API
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              EXECUTION BACKENDS                                          │
│  ┌─────────────────────────────┐    ┌─────────────────────────────────────────────────┐ │
│  │   LOCAL: DroidRun Agent     │    │   CLOUD: MobileRun Cloud API                     │ │
│  │   (ADB-connected device)    │    │   (Remote Android devices)                       │ │
│  │                             │    │                                                  │ │
│  │  ┌─────────────────────┐    │    │  ┌───────────────────────────────────────────┐  │ │
│  │  │  Android Device     │    │    │  │      MobileRun Cloud Service              │  │ │
│  │  │  (USB/WiFi ADB)     │◄───┼────┼──┤  ┌─────────┐  ┌─────────┐  ┌─────────┐   │  │ │
│  │  └─────────────────────┘    │    │  │  │ Device  │  │ Device  │  │ Device  │   │  │ │
│  │                             │    │  │  │ Pool 1  │  │ Pool 2  │  │ Pool N  │   │  │ │
│  └─────────────────────────────┘    │  │  └─────────┘  └─────────┘  └─────────┘   │  │ │
│                                     │  └───────────────────────────────────────────┘  │ │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ WebSocket / HTTP
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              MIRROR SERVICE (Port 8080-8082)                             │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │                         Device Screen Streaming                                  │    │
│  │                                                                                  │    │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐              │    │
│  │  │   server.js      │  │ server-webrtc.js │  │server-h264-fmp4.js│              │    │
│  │  │  (MJPEG Stream)  │  │ (WebRTC Signal)  │  │ (H264 Streaming)  │              │    │
│  │  │    Port 8080     │  │    Port 8082     │  │                   │              │    │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘              │    │
│  │                                                                                  │    │
│  │  Streams: MJPEG (5-15 FPS)  │  WebRTC (Low Latency)  │  H264 (High Quality)    │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ HTTP API (Port 5123)
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              JOB HUNTER SERVICE (Port 5123)                              │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │                         AI Job Hunter (Flask)                                    │    │
│  │                                                                                  │    │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐              │    │
│  │  │ ResumeParser     │  │JobApplicationOrchestrator              │              │    │
│  │  │ (PDF → Struct)   │  │ (Apply Flow)     │  │                  │              │    │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘              │    │
│  │                                                                                  │    │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐              │    │
│  │  │ MongoDBManager   │  │GoogleSheetsManager│  │ AgentFactory     │              │    │
│  │  │ (Applications DB)│  │ (Tracking Sheet) │  │ (MobileRun/Droid)│              │    │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘              │    │
│  │                                                                                  │    │
│  │  Endpoints: /api/applications, /api/upload-resume, /api/preferences              │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────────────┘

                                    EXTERNAL SERVICES
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │   Gemini    │  │    Vapi     │  │  Telegram   │  │  Google     │  │  MongoDB    │   │
│  │   (LLM)     │  │ (Voice AI)  │  │   (Bot)     │  │  Sheets     │  │  (Database) │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                                      │
│  │  Deepgram   │  │  OpenRouter │  │  Anthropic  │                                      │
│  │(STT/Transc) │  │(Free Models)│  │  (Claude)   │                                      │
│  └─────────────┘  └─────────────┘  └─────────────┘                                      │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram

### 1. Chat Command Flow

```
User Input (Web)
       │
       ▼
┌──────────────┐
│  ChatArea    │
│  Component   │
└──────────────┘
       │
       ▼
┌──────────────┐     ┌──────────────┐
│  api.chat()  │────▶│  /api/chat   │
│  (lib/api.ts)│     │  (chat.py)   │
└──────────────┘     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │IronClawAgent │
                     │create_agent() │
                     └──────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
       ┌──────────────┐            ┌──────────────┐
       │ MobileRun    │            │ DroidRun     │
       │ Cloud API    │            │ Local ADB    │
       └──────────────┘            └──────────────┘
              │                           │
              └─────────────┬─────────────┘
                            ▼
                     ┌──────────────┐
                     │Android Device│
                     │  (Actions)   │
                     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │  Response    │
                     │  (Steps)     │
                     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │  ChatArea    │
                     │  (Display)   │
                     └──────────────┘
```

### 2. Device Mirror Flow (WebRTC)

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  Web Browser    │◄───────►│  WebRTC Server  │◄───────►│  Android Device │
│  (DeviceMirror  │  SDP    │  (Port 8082)    │  ADB    │  (scrcpy/       │
│   WebRTC.tsx)   │  ICE    │                 │  Stream │   Droidrun)     │
└─────────────────┘         └─────────────────┘         └─────────────────┘
        │
        │ Video Stream
        ▼
┌─────────────────┐
│  <video> Element│
│  (Live Display) │
└─────────────────┘
```

### 3. Job Application Flow

```
User Uploads Resume
        │
        ▼
┌───────────────┐
│ /api/upload   │
│   -resume     │
└───────────────┘
        │
        ▼
┌───────────────┐     ┌───────────────┐
│ResumeParser   │────▶│  Extract Text │
│(PyPDF2/LLM)   │     │  (Skills, Exp)│
└───────────────┘     └───────────────┘
        │
        ▼
┌───────────────┐
│Orchestrator   │
│(Quota Manager)│
└───────────────┘
        │
        ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│MobileRun Agent│────▶│ Chrome Mobile │────▶│ Job Portals   │
│(Auto-apply)   │     │ (Automation)  │     │(LinkedIn/etc) │
└───────────────┘     └───────────────┘     └───────────────┘
        │
        ▼
┌───────────────┐     ┌───────────────┐
│MongoDB        │     │Google Sheets  │
│(Store Apps)   │     │(Track Status) │
└───────────────┘     └───────────────┘
```

---

## Component Inventory

### Active Components (In Use)

| Component | Location | Purpose | Status |
|-----------|----------|---------|--------|
| **Web App** | `apps/web/` | React frontend | ✅ Active |
| **Gateway** | `apps/gateway/` | FastAPI backend | ✅ Active |
| **Job Hunter** | `apps/job-hunter/` | Flask job service | ✅ Active |
| **Mirror Service** | `apps/mirror-service/` | Screen streaming | ✅ Active |
| DeviceMirrorWebRTC | `web/src/components/` | WebRTC mirror | ✅ Active |
| DeviceMirrorCloud | `web/src/components/` | MobileRun mirror | ✅ Active |
| ChatArea | `web/src/components/` | Main chat UI | ✅ Active |
| Sidebar | `web/src/components/` | Thread management | ✅ Active |
| IronClawAgent | `gateway/agents/` | Main agent wrapper | ✅ Active |
| TabManagerService | `gateway/modules/` | Chrome tab control | ✅ Active |
| JobHunterService | `gateway/modules/` | Resume & apply | ✅ Active |
| VapiInterrupter | `gateway/modules/` | Voice wake calls | ✅ Active |
| TelegramBot | `gateway/modules/` | Bot notifications | ✅ Active |
| HITLService | `gateway/services/` | Human intervention | ✅ Active |

### Potentially Unused/Dead Code

| Component | Location | Issue | Recommendation |
|-----------|----------|-------|----------------|
| DeviceMirror.tsx | `web/src/components/` | Not imported in Index.tsx | ⚠️ Check usage |
| DeviceMirrorMSE.tsx | `web/src/components/` | Not imported in Index.tsx | ⚠️ Check usage |
| DeviceMirrorSimple.tsx | Listed in tabs but missing | File doesn't exist | ❌ Remove reference |
| server-h264-fmp4.js | `mirror-service/` | Not in start.sh | ⚠️ Verify usage |
| server.js (MJPEG) | `mirror-service/` | WebRTC preferred | ⚠️ May be legacy |
| NanoBananaPro | `gateway/modules/` | Complex fallback | ⚠️ Review necessity |
| PersonalizationService | `gateway/modules/` | Wallpaper feature | ⚠️ Check if used |
| ScheduleExtractor | `gateway/modules/` | OCR → Calendar | ⚠️ Check if used |
| ExecutionService | `gateway/services/` | May overlap with TabExecution | ⚠️ Review |

---

## API Endpoints Summary

### Gateway API (Port 8000)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/chat` | POST | Main chat interface |
| `/api/upload` | POST | File upload |
| `/api/transcribe` | POST | Speech-to-text |
| `/api/schedule-call` | POST | Schedule Vapi call |
| `/api/v1/jobs/*` | Various | Job hunting operations |
| `/api/v1/alarms/*` | Various | Alarm management |
| `/api/v1/tabs/*` | Various | Chrome tab control |
| `/api/v1/wake/*` | Various | Wake-up calls |
| `/api/v1/hitl/*` | Various | Human-in-the-loop |
| `/api/v1/speech/*` | Various | Speech processing |
| `/api/v1/mobilerun/*` | Various | MobileRun proxy |

### Job Hunter API (Port 5123)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard |
| `/api/applications/<user_id>` | GET | Get applications |
| `/api/applications/google-sheets` | GET | Sheets data |
| `/api/upload-resume` | POST | Upload resume |
| `/api/preferences` | GET/POST | User prefs |
| `/api/stats` | GET | Statistics |

---

## Configuration Files

| File | Purpose |
|------|---------|
| `.env` | API keys and secrets |
| `config.yaml` | App configuration (safe packages, etc.) |
| `apps/gateway/config.yaml` | Gateway-specific config |
| `apps/job-hunter/.env` | Job hunter environment |
| `pyproject.toml` | Python dependencies |
| `apps/web/package.json` | Node dependencies |

---

## Technology Stack

### Frontend
- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS + shadcn/ui
- **State**: TanStack Query + localStorage
- **i18n**: Lingo.dev
- **Icons**: Lucide React

### Backend
- **Framework**: FastAPI (Gateway) + Flask (Job Hunter)
- **Agent**: DroidRun / MobileRun
- **LLM**: Google Gemini
- **Voice**: Vapi AI
- **Database**: MongoDB
- **Scheduling**: APScheduler

### Infrastructure
- **Process Manager**: PM2
- **Streaming**: WebSocket / WebRTC
- **Container**: Local/Cloud hybrid

---

## Security Considerations

1. **Package Whitelist**: [`ironclaw_agent.py`](apps/gateway/src/ironclaw/agents/ironclaw_agent.py:100) enforces safe packages
2. **HITL Protection**: Human intervention for sensitive actions
3. **Environment Variables**: No secrets in code
4. **CORS**: Restricted to localhost ports in production
5. **ADB Security**: TCP connections should use Tailscale/SSH tunnel

---

## Scaling Considerations

### Current Limitations
- In-memory storage for tasks (use Redis in production)
- Single ADB connection (singleton pattern)
- Local file storage (use S3 in production)

### Recommended Improvements
1. Replace `_task_storage` dict with Redis
2. Add connection pooling for ADB
3. Implement proper authentication
4. Add rate limiting
5. Use message queue for background jobs
