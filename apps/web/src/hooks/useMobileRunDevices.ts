import { useState, useEffect, useCallback } from 'react';

export interface MobileRunDevice {
    id: string;
    name: string;
    state: 'creating' | 'assigned' | 'ready' | 'terminated' | 'unknown';
    stateMessage?: string;
    streamUrl?: string;
    streamToken?: string;
    deviceType?: string;
    country?: string;
    provider?: string;
    apps?: string[];
    createdAt?: string;
    updatedAt?: string;
    assignedAt?: string;
    taskCount?: number;
}

interface DevicesResponse {
    items: MobileRunDevice[];
    pagination: {
        hasNext: boolean;
        hasPrev: boolean;
        page: number;
        pageSize: number;
        pages: number;
        total: number;
    };
}

interface UseMobileRunDevicesResult {
    devices: MobileRunDevice[];
    loading: boolean;
    error: string | null;
    refresh: () => Promise<void>;
    selectedDevice: MobileRunDevice | null;
    setSelectedDevice: (device: MobileRunDevice | null) => void;
}

// Use the local gateway proxy to avoid CORS issues
const GATEWAY_API_URL = 'http://localhost:8000/api/v1/mobilerun';

export function useMobileRunDevices(): UseMobileRunDevicesResult {
    const [devices, setDevices] = useState<MobileRunDevice[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selectedDevice, setSelectedDevice] = useState<MobileRunDevice | null>(null);

    const fetchDevices = useCallback(async () => {
        setLoading(true);
        setError(null);

        try {
            // Call the gateway proxy endpoint instead of MobileRun API directly
            const response = await fetch(
                `${GATEWAY_API_URL}/devices?page=1&pageSize=20&orderBy=createdAt&orderByDirection=desc`,
                {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                }
            );

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Failed to fetch devices: ${response.status} ${errorText}`);
            }

            const data: DevicesResponse = await response.json();
            setDevices(data.items || []);

            // Auto-select first ready device if none selected
            if (!selectedDevice && data.items?.length > 0) {
                const readyDevice = data.items.find(d => d.state === 'ready' || d.state === 'assigned');
                if (readyDevice) {
                    setSelectedDevice(readyDevice);
                }
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to fetch devices');
            console.error('Error fetching MobileRun devices:', err);
        } finally {
            setLoading(false);
        }
    }, [selectedDevice]);

    useEffect(() => {
        fetchDevices();
    }, [fetchDevices]);

    return {
        devices,
        loading,
        error,
        refresh: fetchDevices,
        selectedDevice,
        setSelectedDevice,
    };
}

export default useMobileRunDevices;
