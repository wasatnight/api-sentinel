export async function request<T>(path: string, method = 'GET', body?: unknown, signal?: AbortSignal): Promise<T> {
    let response: Response;
    try {
        const deadline = AbortSignal.timeout(12000);
        response = await fetch('/api/v1' + path, { method, headers: body === undefined ? {} : { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body), signal: signal ? AbortSignal.any([signal, deadline]) : deadline });
    }
    catch (error) {
        if (signal?.aborted)
            throw error;
        throw new Error("Could not connect to the backend. Make sure the backend is running.");
    }
    if (!response.ok) {
        let detail = '';
        try {
            const error = await response.json();
            detail = typeof error.detail === 'string' ? error.detail : Array.isArray(error.detail) ? error.detail.map((e: {
                msg: string;
            }) => e.msg).join(' · ') : '';
        }
        catch { /* A stopped Vite proxy may return a non-JSON response. */ }
        throw new Error(detail || "Could not complete the operation. Check the backend connection.");
    }
    return response.status === 204 ? undefined as T : response.json();
}
