FROM python:3.12-slim

# P-06: version ranges for reproducibility
RUN pip install --no-cache-dir \
    "numpy>=2.0,<3" \
    "pandas>=2.0,<4" \
    "scipy>=1.12,<2" \
    "pyarrow>=15,<24" \
    "requests>=2.28,<3"

# Copy immutable evaluation harness + watchdog
COPY scripts/autoresearch/evaluate.py /app/evaluate.py
COPY docker/autoresearch/watchdog.py /app/watchdog.py

WORKDIR /app

# Fix path issues for containerized evaluate.py:
# - PROJECT_ROOT: evaluate.py uses this to find data/, research/ etc.
# - PYTHONPATH: so `from factor import compute_factor` finds /app/work/factor.py
ENV PROJECT_ROOT=/app
ENV PYTHONPATH=/app/work:/app
ENV QUANT_MODE=backtest

# Non-root user with writable work dir
RUN useradd -m -s /bin/bash researcher && \
    mkdir -p /app/work && chown researcher:researcher /app/work
USER researcher

CMD ["sleep", "infinity"]
