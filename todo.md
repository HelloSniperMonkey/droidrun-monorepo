# Project Iron Claw: Duolingo Daily Login Bonus

## Phase 1: Core Logic and Setup

- [ ] **Task 1: Project Scaffolding**: Create a new directory `gateway/` for the main application logic.
- [ ] **Task 2: State Management**: Create a file `gateway/daily_bonus_state.json` to store the timestamp of the last login.
- [ ] **Task 3: Main Application Logic**: Create a file `gateway/main.py` that will contain the core logic for the daily login bonus system.
- [ ] **Task 4: Implement Droidrun Interaction**: In `gateway/main.py`, implement the logic to check the last login time and navigate to the Duolingo shop if it's a new day.
- [ ] **Task 5: Background Service**: Implement a background service that periodically checks for the Duolingo app launch.

## Phase 2: Refinement and Deployment

- [ ] **Task 6: Configuration**: Add a `config.yaml` to manage settings like the Duolingo package name.
- [ ] **Task 7: Deployment script**: Create a `run.sh` script to easily start the gateway.

## Review

### Frontend UI Fixes (EndpointActions & ChatArea)
- **Issue**: UI remained in "Empty State" (How can I help you?) while backend actions (like Daily Login) were running, and didn't transition cleanly to "Chat Interface" until completion (or sometimes failed to transition visibly if result was handled incorrectly).
- **Fix**:
  - Refactored `EndpointActions` to accept an `onStart` callback.
  - Implemented `handleActionStart` in `ChatArea` to immediately add a "User" message (representing the clicked action) and an "Assistant" placeholder ("..."). This forces the UI to switch from Empty State to Chat State immediately.
  - Updated `handleActionResult` to use `replaceLastAssistantMessage` instead of `addMessage`. This ensures the initial placeholder (or "Running..." status) is replaced by the final result, avoiding duplicate messages or left-over status messages.
  - Updated `handleTaskWithPolling` to use `replaceLastAssistantMessage` for its initial "Running..." status and subsequent error/timeout messages. This ensures the initial placeholder is replaced by the "Running..." status, which is then replaced by the final result.
- **Result**: Clicking an action button now immediately shows a chat bubble for the action, followed by a loading state, and finally the result, providing immediate visual feedback and a correct state transition.

### Miscellaneous
- **Issue**: "Check Android version" button was missing from the API client definition (causing potential crashes) and needed to be confirmed in the "Miscellaneous" group.
- **Fix**:
  - Verified "Check Android version" is in the `misc` category in `ChatArea.tsx`.
  - Added `checkAndroidVersion` to `api.ts` (mapped to the mock task endpoint for now) to ensure functionality.
