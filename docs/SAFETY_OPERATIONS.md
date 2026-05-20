# Nexus Safety & Operations Guide

## Safety Principles

### 1. No Fabrication
- All context must be user-provided
- AI suggestions are marked as `[UNVERIFIED]`
- Never assume goals or capabilities

### 2. Graceful Degradation
- System continues if components fail
- Dead letter queue preserves failed messages
- Circuit breakers prevent cascade failures

### 3. Transparency
- All agent communications are logged
- Message history is maintained
- Capability votes are transparent

---

## Operational Safety Checklist

### Pre-Deployment
- [ ] All tests pass: `python -m pytest packages/core/tests`
- [ ] Config validated: `nexus config --show`
- [ ] Storage permissions correct: `ls -la ~/.nexus/`
- [ ] Health check passes: `nexus health`

### Daily Operations
- [ ] Monitor `nexus status` for issues
- [ ] Check `nexus bridge` for queue health
- [ ] Verify `nexus daemon status`
- [ ] Review any dead letters

### Weekly Operations
- [ ] Run full test suite
- [ ] Rotate logs if needed
- [ ] Check disk space
- [ ] Review capability proposals

---

## Failure Modes & Recovery

### Component Failure

| Component | Failure Mode | Recovery |
|-----------|--------------|----------|
| Resilient Bridge | Messages stuck | Check circuit breaker, restart |
| Rate Limiter | 429 errors | Wait, check limits |
| Life Context | Data corruption | Restore from backup |
| WebSocket | Disconnection | Auto-reconnect, check firewall |

### Message Flow Failures

1. **Message Stuck in Queue**
   ```
   Check: nexus bridge
   Action: Wait for retry, or reset circuit
   ```

2. **Dead Letter Created**
   ```
   Check: nexus bridge (shows DLQ)
   Action: Review error, retry or acknowledge loss
   ```

3. **Circuit Breaker Open**
   ```
   Check: nexus bridge (shows OPEN)
   Action: Wait for recovery timeout, or manual reset
   ```

---

## Rate Limiting

### Limits
- Per minute: 30 requests (configurable)
- Per hour: 500 requests (configurable)
- Burst: 10 requests

### Handling Rate Limits
```python
from hermes_pi_bridge_core.rate_limiter import get_rate_limiter

limiter = get_rate_limiter()
status = limiter.check_limit("hermes")

if not status['can_proceed']:
    wait_time = status['retry_after']
    print(f"Wait {wait_time}s")
```

---

## Security

### Authentication
- WebSocket supports token auth
- Set auth token in config

### Authorization
- Agents have specific roles
- Hermes: strategic
- PI: tactical
- Nexus: orchestrator

### Data Protection
- Messages encrypted at rest
- TLS for WebSocket (production)
- No PII in logs

---

## Monitoring

### Health Checks
```bash
# Component health
nexus health

# Daemon status
nexus daemon status

# Bridge status
nexus bridge
```

### Metrics
- Queue depth
- Circuit breaker state
- Message success rate
- Response times

### Alerts
Set up alerts for:
- Dead letter queue > 0
- Circuit breaker OPEN > 60s
- Memory > 80%
- Queue depth > 80%

---

## Backup & Recovery

### Backup
```bash
# Backup state
cp -r ~/.nexus ~/.nexus.backup.$(date +%Y%m%d)

# Backup specifically
cp ~/.nexus/messages.json ~/.nexus.backup/
```

### Recovery
```bash
# Restore from backup
cp ~/.nexus.backup/* ~/.nexus/

# Restart daemon
nexus daemon restart
```

---

## Emergency Procedures

### Total Failure
1. Stop daemon: `nexus daemon stop`
2. Check logs: `tail ~/.nexus/daemon.log`
3. Verify state: `nexus status`
4. Restart: `nexus daemon start`

### Data Corruption
1. Stop all operations
2. Restore from backup
3. Verify integrity: `python -m pytest packages/core/tests`
4. Resume operations

### Performance Degradation
1. Check queue depth: `nexus bridge`
2. Check memory: `nexus daemon status`
3. Restart if needed: `nexus daemon restart`

---

## Compliance

### Audit Trail
- All governance decisions logged
- Message history maintained
- Capability votes recorded

### Verification
- User-provided context marked `[VERIFIED]`
- AI suggestions marked `[UNVERIFIED]`
- All votes are transparent

---

## Support

### Debug Mode
```bash
# Enable verbose logging
export NEXUS_LOG_LEVEL=DEBUG
nexus daemon restart
```

### Test Mode
```bash
# Run specific tests
python -m pytest packages/core/tests/test_bridge.py -v

# Integration tests
python -m pytest packages/core/tests/test_integration.py -v
```

### Getting Help
1. Check this documentation
2. Review test files
3. Check logs for errors
4. Run diagnostics: `nexus health && nexus bridge`