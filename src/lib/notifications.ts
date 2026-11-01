export type Notice = {
    id: string;
    created_at: string;
    read_at: string | null;
    message: string;
};
export class NotificationTracker {
    private seen = new Map<string, number>();
    private floor = Number.NEGATIVE_INFINITY;
    private initialized = false;
    constructor(private readonly capacity = 2000) {
        if (capacity < 1)
            throw new Error('Capacity must be positive');
    }
    reset() { this.seen.clear(); this.floor = Number.NEGATIVE_INFINITY; this.initialized = false; }
    get size() { return this.seen.size; }
    poll<T extends Notice>(records: readonly T[]): T[] {
        const valid = records.filter(r => Number.isFinite(Date.parse(r.created_at)));
        const initial = !this.initialized;
        if (initial) {
            this.initialized = true;
            this.floor = valid.length ? Math.min(...valid.map(r => Date.parse(r.created_at))) - 1 : Number.NEGATIVE_INFINITY;
        }
        const fresh = initial ? [] : valid.filter(r => !r.read_at && !this.seen.has(r.id) && Date.parse(r.created_at) > this.floor);
        valid.forEach(r => {
            if (Date.parse(r.created_at) > this.floor)
                this.seen.set(r.id, Date.parse(r.created_at));
        });
        if (this.seen.size > this.capacity) {
            const sorted = [...this.seen].sort((a, b) => b[1] - a[1]);
            const evicted = sorted.slice(this.capacity);
            this.floor = Math.max(this.floor, ...evicted.map(([, time]) => time));
            this.seen = new Map(sorted.slice(0, this.capacity));
        }
        return fresh;
    }
}
