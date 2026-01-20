
## UI Updates - January 20, 2026

### Frontend Cleanup
- [x] Remove Gateway Root, Wake location, and Alarm time from the web frontend in `apps/web/src/components/ChatArea.tsx`
- [x] Add keyboard shortcuts: Cmd+Shift+O (New Chat) and Cmd+Shift+S (Toggle Sidebar)
- [x] Add visual key binding hint to "New Chat" button
- [x] Replace Pin icon with Delete icon in Sidebar and implement thread deletion with persistence

## Review
I have implemented the requested key bindings:
1.  **New Chat**: `Cmd + Shift + O` triggers a new chat. Added a visual hint "⇧⌘O" to the New Chat button in the sidebar.
2.  **Toggle Sidebar**: `Cmd + Shift + S` toggles the sidebar visibility.
3.  **Delete Thread**: Replaced the Pin icon with a Trash icon for the active thread. Clicking it prompts for confirmation and then deletes the thread from both the state and local storage.

Changes were made in `apps/web/src/pages/Index.tsx` (event listeners, delete handler), `apps/web/src/hooks/useLocalThreads.ts` (delete logic), and `apps/web/src/components/Sidebar.tsx` (visual hint, delete button).
Verified the build with `npm run build`.
