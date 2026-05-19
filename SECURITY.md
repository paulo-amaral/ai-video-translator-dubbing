# Security Policy

## Supported Versions

Security fixes are handled on the latest public release and the `main` branch.

## Reporting a Vulnerability

Please do not open a public issue for sensitive security reports.

Report vulnerabilities privately to Paulo Amaral by email:

```text
paulo dot security at gmail.com
```

Include:

- A short description of the vulnerability
- Steps to reproduce
- Affected files or commands
- Potential impact
- Suggested fix, if available

## Secrets and Credentials

This project can use API keys for Gemini, OpenAI, and ElevenLabs. Treat those keys as sensitive.

Never commit:

- `.env`
- API keys or bearer tokens
- private voice IDs tied to paid accounts
- source videos containing private content
- generated transcripts or subtitles from confidential media
- downloaded model files
- generated output videos or audio chunks

If a secret is exposed:

1. Revoke or rotate the key at the provider.
2. Remove the secret from local files and Git history.
3. Force-push only if you understand the impact on collaborators.
4. Check GitHub secret scanning alerts.

## Safe Defaults

The repository is configured to ignore `.env`, model folders, generated media, source video formats, VTT/SRT subtitle files, private key formats, and common local caches.

GitHub Actions use read-only repository permissions by default.

## Dependency Security

Dependencies are intentionally separated:

- `requirements.txt`: core pipeline
- `requirements-demucs.txt`: optional background separation
- `requirements-rvc.txt`: optional voice conversion

Dependabot is enabled for Python packages and GitHub Actions. Review dependency updates before merging because media, ML, and TTS packages may change runtime behavior.
