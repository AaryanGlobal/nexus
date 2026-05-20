# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly.

### How to Report

1. **Do NOT** create a public GitHub issue for security vulnerabilities
2. Send a private report via:
   - GitHub Security Advisories (preferred)
   - Email to: [security contact]

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 7 days
- **Fix Development**: Depends on severity
- **Disclosure**: After fix is available

## Security Best Practices

When using Hermes-Pi Bridge:

### Authentication

- Use strong, unique authentication tokens
- Rotate tokens regularly
- Never commit tokens to version control

```yaml
# Good
auth_token: "secure-random-token-here"

# Bad
auth_token: "password123"
```

### Network Security

- Use HTTPS in production
- Restrict access to bridge ports (2719, 8080) to trusted networks
- Consider firewall rules

```bash
# Example: Restrict to localhost only
pi_url: "http://127.0.0.1:2719"
```

### Input Validation

The bridge validates all inputs, but:

- Sanitize file paths before processing
- Don't delegate untrusted code without review
- Set appropriate timeouts

### Dependencies

Keep dependencies updated:

```bash
# Python
pip install --upgrade hermes-pi-bridge

# Node.js
npm update hermes-pi-bridge
```

## Security Features

### Token Authentication

Both servers support Bearer token authentication:

```bash
# Set via environment
export HERMES_PI_BRIDGE_AUTH_TOKEN="your-token"
export HERMES_BRIDGE_TOKEN="your-token"
```

### Rate Limiting

- Max 10 requests/second per session
- Configurable via settings

### Input Limits

- Max 100KB per request body
- Max 100 items per array
- Max 50 keys per object

## Known Limitations

- No mTLS support yet (planned for v2.0)
- Tokens transmitted in plain text over HTTP (use HTTPS)
- No audit logging yet (planned for v1.1)

## Changelog for Security

### v1.0.0
- Initial release
- Bearer token authentication
- Input validation

## Questions?

See [FAQ](./docs/faq.md) or open a [discussion](https://github.com/your-org/hermes-pi-bridge/discussions).
