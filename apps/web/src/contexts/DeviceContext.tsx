import { createContext, useContext, useState, useCallback, ReactNode, useEffect } from 'react';
import type { MobileRunDevice } from '@/hooks/useMobileRunDevices';

interface DeviceContextType {
    selectedDevice: MobileRunDevice | null;
    setSelectedDevice: (device: MobileRunDevice | null) => void;
}

const DeviceContext = createContext<DeviceContextType | undefined>(undefined);

export function DeviceProvider({ children }: { children: ReactNode }) {
    const [selectedDevice, setSelectedDevice] = useState<MobileRunDevice | null>(null);

    return (
        <DeviceContext.Provider value={{ selectedDevice, setSelectedDevice }}>
            {children}
        </DeviceContext.Provider>
    );
}

export function useDevice() {
    const context = useContext(DeviceContext);
    if (!context) {
        throw new Error('useDevice must be used within a DeviceProvider');
    }
    return context;
}
