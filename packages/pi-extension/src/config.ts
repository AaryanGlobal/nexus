/**
 * Configuration management for pi side of Hermes-Pi Bridge.
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

/** Default configuration values */
const DEFAULT_HERMES_URL = 'http://localhost:8080';
const DEFAULT_PI_PORT = 2719;
const DEFAULT_AUTH_TOKEN = '';

/** pi settings file path */
const PI_SETTINGS_PATH = path.join(os.homedir(), '.pi', 'agent', 'settings.json');

/** pi extension config file */
const EXTENSION_CONFIG_PATH = path.join(os.homedir(), '.pi', 'agent', 'hermes-bridge.json');

/** Configuration schema */
export interface BridgeConfig {
  hermesUrl: string;
  piPort: number;
  authToken: string;
}

/**
 * Load configuration from pi settings and extension config.
 */
export function loadConfig(): BridgeConfig {
  // Load from extension config first (overrides)
  let config: BridgeConfig = {
    hermesUrl: DEFAULT_HERMES_URL,
    piPort: DEFAULT_PI_PORT,
    authToken: DEFAULT_AUTH_TOKEN,
  };
  
  // Read extension config
  if (fs.existsSync(EXTENSION_CONFIG_PATH)) {
    try {
      const extConfig = JSON.parse(fs.readFileSync(EXTENSION_CONFIG_PATH, 'utf-8'));
      config = { ...config, ...extConfig };
    } catch (e) {
      console.error('Failed to read extension config:', e);
    }
  }
  
  // Read from pi settings
  if (fs.existsSync(PI_SETTINGS_PATH)) {
    try {
      const settings = JSON.parse(fs.readFileSync(PI_SETTINGS_PATH, 'utf-8'));
      if (settings.hermesBridge) {
        config = { ...config, ...settings.hermesBridge };
      }
    } catch (e) {
      console.error('Failed to read pi settings:', e);
    }
  }
  
  // Environment variables override
  if (process.env.HERMES_BRIDGE_URL) {
    config.hermesUrl = process.env.HERMES_BRIDGE_URL;
  }
  if (process.env.HERMES_BRIDGE_TOKEN) {
    config.authToken = process.env.HERMES_BRIDGE_TOKEN;
  }
  
  return config;
}

/**
 * Save configuration to extension config file.
 */
export function saveConfig(config: Partial<BridgeConfig>): void {
  // Ensure directory exists
  const dir = path.dirname(EXTENSION_CONFIG_PATH);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  
  // Load existing config
  let existing: Record<string, unknown> = {};
  if (fs.existsSync(EXTENSION_CONFIG_PATH)) {
    try {
      existing = JSON.parse(fs.readFileSync(EXTENSION_CONFIG_PATH, 'utf-8'));
    } catch (e) {
      // Ignore, start fresh
    }
  }
  
  // Merge and save
  const merged = { ...existing, ...config };
  fs.writeFileSync(EXTENSION_CONFIG_PATH, JSON.stringify(merged, null, 2));
}
