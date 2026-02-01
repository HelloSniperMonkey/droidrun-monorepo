import { useState, useEffect, useCallback } from 'react';
import { useDevice } from '@/contexts/DeviceContext';

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
    isPhysical?: boolean; // Flag to identify physical device
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
}

// Use the local gateway proxy to avoid CORS issues
const GATEWAY_API_URL = 'http://localhost:8000/api/v1/mobilerun';

export function useMobileRunDevices(): UseMobileRunDevicesResult {
    const [devices, setDevices] = useState<MobileRunDevice[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    
    // Use shared device context
    const { selectedDevice, setSelectedDevice } = useDevice();

    const fetchDevices = useCallback(async () => {
        setLoading(true);
        setError(null);

        try {
            // Fetch both cloud devices and physical device in parallel
            const [cloudResponse, physicalResponse] = await Promise.all([
                fetch(
                    `${GATEWAY_API_URL}/devices?page=1&pageSize=20&orderBy=createdAt&orderByDirection=desc`,
                    {
                        method: 'GET',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                    }
                ),
                fetch(`${GATEWAY_API_URL}/physical-device`, {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                })
            ]);

            if (!cloudResponse.ok) {
                const errorText = await cloudResponse.text();
                throw new Error(`Failed to fetch devices: ${cloudResponse.status} ${errorText}`);
            }

            const cloudData: DevicesResponse = await cloudResponse.json();
            const physicalData = physicalResponse.ok ? await physicalResponse.json() : { device_id: null };

            const allDevices: MobileRunDevice[] = [...(cloudData.items || [])];

            // Add physical device if configured
            if (physicalData.device_id) {
                const physicalDevice: MobileRunDevice = {
                    id: physicalData.device_id,
                    name: '📱 My Physical Device',
                    state: 'ready',
                    isPhysical: true,
                    deviceType: 'physical',
                };
                // Add physical device at the beginning
                allDevices.unshift(physicalDevice);
            }

            setDevices(allDevices);

            // Auto-select first ready device if none selected
            if (!selectedDevice && allDevices.length > 0) {
                // Prioritize physical device, then ready/assigned cloud devices
                const readyDevice = allDevices.find(d => d.isPhysical) || 
                                    allDevices.find(d => d.state === 'ready' || d.state === 'assigned');
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
    }, [selectedDevice, setSelectedDevice]);

    useEffect(() => {
        fetchDevices();
    }, [fetchDevices]);

    return {
        devices,
        loading,
        error,
        refresh: fetchDevices,
    };
}

export default useMobileRunDevices;
