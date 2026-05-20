/**
 * Tests for TaskHeartbeat - crash recovery for pi bridge.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import { TaskHeartbeat, InterruptedTask } from '../src/heartbeat';

describe('TaskHeartbeat', () => {
  const testDir = '/tmp/hermes-bridge-test';
  const testLogFile = path.join(testDir, 'heartbeat.jsonl');
  let heartbeat: TaskHeartbeat;

  beforeEach(() => {
    // Clean up before each test
    if (fs.existsSync(testLogFile)) {
      fs.unlinkSync(testLogFile);
    }
    if (fs.existsSync(testDir)) {
      fs.rmSync(testDir, { recursive: true });
    }
    // Recreate directory
    fs.mkdirSync(testDir, { recursive: true });
    heartbeat = new TaskHeartbeat(testDir);
  });

  afterEach(() => {
    // Clean up after tests
    if (fs.existsSync(testLogFile)) {
      fs.unlinkSync(testLogFile);
    }
    if (fs.existsSync(testDir)) {
      fs.rmSync(testDir, { recursive: true });
    }
  });

  describe('beat()', () => {
    it('creates log file and writes entry', () => {
      heartbeat.beat('task-1', 'running');
      
      expect(fs.existsSync(testLogFile)).toBe(true);
      const content = fs.readFileSync(testLogFile, 'utf8');
      const entry = JSON.parse(content.trim());
      
      expect(entry.task_id).toBe('task-1');
      expect(entry.status).toBe('running');
      expect(entry.last_beat).toBeDefined();
    });

    it('appends multiple entries', () => {
      heartbeat.beat('task-1', 'running');
      heartbeat.beat('task-2', 'running');
      heartbeat.beat('task-1', 'running');
      
      const lines = fs.readFileSync(testLogFile, 'utf8').split('\n').filter(l => l.trim());
      expect(lines.length).toBe(3);
    });

    it('defaults to running status', () => {
      heartbeat.beat('task-1');
      
      const content = fs.readFileSync(testLogFile, 'utf8');
      const entry = JSON.parse(content.trim());
      expect(entry.status).toBe('running');
    });
  });

  describe('complete(), fail(), cancel()', () => {
    it('writes correct status', () => {
      heartbeat.complete('task-1');
      heartbeat.fail('task-2');
      heartbeat.cancel('task-3');
      
      const lines = fs.readFileSync(testLogFile, 'utf8').split('\n').filter(l => l.trim());
      expect(JSON.parse(lines[0]).status).toBe('completed');
      expect(JSON.parse(lines[1]).status).toBe('failed');
      expect(JSON.parse(lines[2]).status).toBe('cancelled');
    });
  });

  describe('recoverInterrupted()', () => {
    it('returns empty array when no log file', () => {
      const interrupted = heartbeat.recoverInterrupted();
      expect(interrupted).toEqual([]);
    });

    it('returns empty array when no old tasks', () => {
      heartbeat.beat('task-1', 'running');
      
      // Should not be interrupted (just heartbeat now)
      const interrupted = heartbeat.recoverInterrupted(3600000); // 1 hour
      expect(interrupted.length).toBe(0);
    });

    it('detects tasks not heartbeat recently', () => {
      // Write an old entry directly (simulating crash)
      const oldTime = Date.now() - 7200000; // 2 hours ago
      const oldEntry = JSON.stringify({
        task_id: 'old-task',
        status: 'running',
        last_beat: oldTime,
      });
      fs.writeFileSync(testLogFile, oldEntry + '\n', 'utf8');
      
      // Write a recent entry
      heartbeat.beat('recent-task', 'running');
      
      const interrupted = heartbeat.recoverInterrupted(3600000); // 1 hour max age
      
      expect(interrupted.length).toBe(1);
      expect(interrupted[0].task_id).toBe('old-task');
    });

    it('ignores completed tasks', () => {
      const oldTime = Date.now() - 7200000;
      const oldEntry = JSON.stringify({
        task_id: 'completed-task',
        status: 'completed',
        last_beat: oldTime,
      });
      fs.writeFileSync(testLogFile, oldEntry + '\n', 'utf8');
      
      const interrupted = heartbeat.recoverInterrupted(3600000);
      expect(interrupted.length).toBe(0);
    });
  });

  describe('compact()', () => {
    it('reduces file size', () => {
      // Write many entries
      for (let i = 0; i < 100; i++) {
        heartbeat.beat(`task-${i % 5}`, 'running'); // Only 5 unique tasks
      }
      
      const linesBefore = fs.readFileSync(testLogFile, 'utf8').split('\n').filter(l => l.trim()).length;
      expect(linesBefore).toBe(100);
      
      heartbeat.compact(10);
      
      const linesAfter = fs.readFileSync(testLogFile, 'utf8').split('\n').filter(l => l.trim()).length;
      expect(linesAfter).toBeLessThan(10);
    });
  });

  describe('getActiveCount()', () => {
    it('counts running and pending tasks', () => {
      heartbeat.beat('task-1', 'running');
      heartbeat.beat('task-2', 'pending');
      heartbeat.beat('task-3', 'completed');
      heartbeat.beat('task-4', 'running');
      
      // Latest status wins
      heartbeat.beat('task-1', 'completed');
      
      const count = heartbeat.getActiveCount();
      expect(count).toBe(2); // task-2 (pending) and task-4 (running)
    });
  });
});