# Security Policy

## Reporting Security Vulnerabilities

We take security issues seriously. If you discover a security vulnerability, please report it responsibly.

**Recommended: Use GitHub's Private Vulnerability Reporting**

Submit your report through GitHub's private vulnerability reporting system:

**[Report a vulnerability](https://github.com/advisories/new)**

This method allows you to report vulnerabilities privately and directly to the maintainers. Reports are triaged within 7 days and you will receive updates on the progress toward a fix.

### What to Include in a Report

When reporting, please include as much of the following information as possible:

- Type of vulnerability (e.g., code injection, path traversal, credential exposure)
- Full paths of source file(s) related to the vulnerability
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact assessment of the vulnerability

## Public Issue Guidelines

### Do Not Paste Secrets in Public Issues

When creating issues or discussions, **never** include:

- API keys, tokens, or access credentials
- Passwords or secrets of any kind
- Private keys (SSH, GPG, etc.)
- Cloud service credentials (AWS keys, Azure secrets, GCP tokens)
- Database connection strings containing credentials
- Model API keys or access tokens
- File paths that expose sensitive system information

**If you accidentally expose secrets:**

1. Immediately rotate or revoke the exposed credentials
2. Notify the relevant service providers
3. Do not assume that deleting the issue removes the secret from git history

### Safe Issue Practices

- Use placeholder values (e.g., `sk-xxxx`, `token-xxxx`) for any credentials
- Use environment variable references (e.g., `${API_KEY}`) without actual values
- If logs are needed, use redacted examples with `[REDACTED]` placeholders

## Supported Versions

We provide security updates for the following versions:

| Version | Supported          | Notes                           |
| ------- | ------------------ | ------------------------------- |
| main    | :white_check_mark: | Latest development branch       |
| X.Y.Z   | :white_check_mark: | Current stable release         |
| X.Y     | :x:                | Use latest stable or main        |

When a version is no longer supported, we recommend upgrading to a supported version to receive security patches.

## Data and Credentials Security

### Handling Sensitive Data

This project may handle:

- **Model credentials**: API keys for LLM services (OpenAI, Anthropic, local models)
- **Repository access tokens**: GitHub tokens for cloning and operations
- **Experiment data**: Potentially sensitive research outputs

### Best Practices

1. **Environment variables**: Store credentials in environment variables, not in configuration files
2. **Secret management**: Use proper secret management solutions (e.g., cloud KMS, HashiCorp Vault)
3. **Git history awareness**: Be aware that git history is immutable; do not commit sensitive data
4. **Temporary files**: Clean up temporary files containing sensitive data after use
5. **Logs**: Enable log redaction to automatically mask sensitive values

### Model Security

When using external AI/ML models:

- Verify model sources before use
- Be cautious with model outputs that may contain sensitive training data
- Do not send confidential data to third-party model APIs unless necessary
- Consider using local models for sensitive workloads

## Response Timeline

We aim to respond to security reports within:

- **Initial triage**: 7 days
- **Severity assessment**: 14 days
- **Fix development**: Depends on complexity, typically 30-90 days
- **Disclosure**: Coordinated with reporter when fix is available

## Security Acknowledgments

We appreciate the security community's efforts to improve this project's security. Contributors who report valid security issues will be acknowledged (unless anonymity is requested).

## Related Documentation

For additional security-related information, see:

- [Internal Security Guide](docs/security.md) - Detailed internal security documentation
- `.gitignore` - Files excluded from version control
- `repro.yaml` - Security configuration options
