# CreatorOS - a self-improving content studio

Multi-agent content studio for the Agent Arena 2026 hackathon. Agents plan, write, edit and illustrate
social media posts in a learned brand voice, schedule them, and learn from engagement so later posts improve.
All AI calls go through Mesh API.

> Work in progress. Full documentation, design decisions and self-evaluation results will be added here.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then put your Mesh key in .env
python -m scripts.check_setup
```
