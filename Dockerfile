# Runs the demo with no network, a read-only filesystem and a non-root user.
# The model-free demos need no network: servers and sandbox talk over loopback only.
FROM python:3.13-slim
RUN useradd -m demo
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
USER demo
CMD ["python3", "examples/minimal_code_mode.py"]
