/**
 * Task Heartbeat - Minimal persistence for pi bridge.
 * 
 * Provides crash recovery by logging task heartbeats to an append-only file.
 * This allows pi to recover interrupted tasks on restart without adding
 * a database dependency.
 * 
 * Format: JSONL (newline-delimited JSON)
 * Location: ~/.pi/agent/.hermes-bridge/heartbeat.jsonl
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export interface HeartbeatEntry {
  task_id: string;
  status: 'running' | 'pending' | 'completed' | 'failed' | 'cancelled';
  last_beat: number;  // Unix timestamp ms
}

export interface InterruptedTask {
  task_id: string;
  last_beat: number;
  elapsed_ms: number;
}

export class TaskHeartbeat {
  private logFile: string;
  private dir: string;

  constructor(dataDir?: string) {
    // Default location in pi's agent directory
    this.dir = dataDir || path.join(os.homedir(), '.pi', 'agent', '.hermes-bridge');
    this.logFile = path.join(this.dir, 'heartbeat.jsonl');
  }

  /**
   * Record a task heartbeat. Append-only for crash safety.
   */
  beat(taskId: string, status: string = 'running'): void {
    const entry: HeartbeatEntry = {
      task_id: taskId,
      status: status as HeartbeatEntry['status'],
      last_beat: Date.now(),
    };

    try {
      // Ensure directory exists
      if (!fs.existsSync(this.dir)) {
        fs.mkdirSync(this.dir, { recursive: true });
      }

      // O_APPEND ensures atomic write at OS level
      const line = JSON.stringify(entry) + '\n';
      fs.appendFileSync(this.logFile, line, 'utf8');
    } catch (err) {
      // Non-fatal: heartbeat failure shouldn't break task execution
      console.error('Failed to write heartbeat:', err);
    }
  }

  /**
   * Mark task as completed (removes from active tracking).
   */
  complete(taskId: string): void {
    this.beat(taskId, 'completed');
  }

  /**
   * Mark task as failed.
   */
  fail(taskId: string): void {
    this.beat(taskId, 'failed');
  }

  /**
   * Mark task as cancelled.
   */
  cancel(taskId: string): void {
    this.beat(taskId, 'cancelled');
  }

  /**
   * Recover tasks that were running when pi crashed.
   * Call this on server startup.
   * 
   * @param maxAgeMs - Tasks not heartbeat'd for this long are considered interrupted
   * @returns List of interrupted tasks
   */
  recoverInterrupted(maxAgeMs: number = 3600000): InterruptedTask[] {
    if (!fs.existsSync(this.logFile)) {
      return [];
    }

    const now = Date.now();
    const latestByTask = new Map<string, HeartbeatEntry>();
    const statusByTask = new Map<string, string>();

    try {
      const content = fs.readFileSync(this.logFile, 'utf8');
      const lines = content.split('\n');

      for (const line of lines) {
        if (!line.trim()) continue;

        try {
          const entry: HeartbeatEntry = JSON.parse(line);

          // Keep latest heartbeat per task
          const existing = latestByTask.get(entry.task_id);
          if (!existing || entry.last_beat > existing.last_beat) {
            latestByTask.set(entry.task_id, entry);
          }

          // Track most recent status
          statusByTask.set(entry.task_id, entry.status);
        } catch {
          // Skip malformed lines
          continue;
        }
      }

      // Find tasks that were running but haven't heartbeat'd recently
      const interrupted: InterruptedTask[] = [];

      for (const [taskId, entry] of latestByTask.entries()) {
        const status = statusByTask.get(taskId);

        // Only consider tasks that were 'running' or 'pending'
        if (status === 'completed' || status === 'failed' || status === 'cancelled') {
          continue;
        }

        const elapsed = now - entry.last_beat;
        if (elapsed > maxAgeMs) {
          interrupted.push({
            task_id: taskId,
            last_beat: entry.last_beat,
            elapsed_ms: elapsed,
          });
        }
      }

      return interrupted;
    } catch (err) {
      console.error('Failed to recover tasks:', err);
      return [];
    }
  }

  /**
   * Compact the heartbeat log to prevent unbounded growth.
   * Keeps the latest entry for each task plus recent entries.
   */
  compact(maxEntries: number = 500): void {
    if (!fs.existsSync(this.logFile)) {
      return;
    }

    try {
      const content = fs.readFileSync(this.logFile, 'utf8');
      const lines = content.split('\n').filter(l => l.trim());

      if (lines.length <= maxEntries) {
        return;  // No compaction needed
      }

      // Keep latest entry per task
      const latestByTask = new Map<string, HeartbeatEntry>();

      for (const line of lines) {
        try {
          const entry: HeartbeatEntry = JSON.parse(line);
          latestByTask.set(entry.task_id, entry);
        } catch {
          continue;
        }
      }

      // Rewrite with latest entries
      const compacted = [...latestByTask.values()]
        .map(e => JSON.stringify(e))
        .join('\n') + '\n';

      fs.writeFileSync(this.logFile, compacted, 'utf8');
    } catch (err) {
      console.error('Failed to compact heartbeat log:', err);
    }
  }

  /**
   * Clear all heartbeat data for a task (after result reported).
   */
  clearTask(taskId: string): void {
    if (!fs.existsSync(this.logFile)) {
      return;
    }

    try {
      const content = fs.readFileSync(this.logFile, 'utf8');
      const lines = content.split('\n');
      const filtered = lines.filter(line => {
        if (!line.trim()) return false;
        try {
          const entry = JSON.parse(line);
          return entry.task_id !== taskId;
        } catch {
          return false;
        }
      });

      fs.writeFileSync(this.logFile, filtered.join('\n'), 'utf8');
    } catch (err) {
      console.error('Failed to clear task heartbeat:', err);
    }
  }

  /**
   * Get count of active (running) tasks.
   */
  getActiveCount(): number {
    if (!fs.existsSync(this.logFile)) {
      return 0;
    }

    try {
      const content = fs.readFileSync(this.logFile, 'utf8');
      const lines = content.split('\n');
      const latestByTask = new Map<string, string>();

      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const entry: HeartbeatEntry = JSON.parse(line);
          latestByTask.set(entry.task_id, entry.status);
        } catch {
          continue;
        }
      }

      let count = 0;
      for (const status of latestByTask.values()) {
        if (status === 'running' || status === 'pending') {
          count++;
        }
      }
      return count;
    } catch {
      return 0;
    }
  }
}
