#!/bin/bash
# Autoresearch agent launcher with restricted permissions
# Only allows: Edit factor.py, run evaluate.py, git operations, read files

cd "$(dirname "$0")/../.."

claude -p scripts/autoresearch/program.md \
  --allowedTools "Read" \
  --allowedTools "Grep" \
  --allowedTools "Glob" \
  --allowedTools "Edit(scripts/autoresearch/factor.py)" \
  --allowedTools "Bash(python scripts/autoresearch/evaluate.py*)" \
  --allowedTools "Bash(git add scripts/autoresearch/*)" \
  --allowedTools "Bash(git commit*)" \
  --allowedTools "Bash(git reset*)" \
  --allowedTools "Bash(git tag*)" \
  --allowedTools "Bash(git log*)" \
  --allowedTools "Bash(cat scripts/autoresearch/*)"
