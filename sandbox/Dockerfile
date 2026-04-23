FROM python:3.11

# Install system tools
RUN apt-get update && apt-get install -y \
    gcc \
    libmagic1 \
    libgl1 \
    libglib2.0-0 \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /sandbox

# Preinstall heavy ML libraries (same as ai_suite)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir tensorflow-cpu
RUN pip install --no-cache-dir scikit-learn scikit-image pandas numpy Pillow ipython transformers huggingface_hub
RUN pip install --no-cache-dir python-docx fpdf opencv-python-headless
RUN pip install --no-cache-dir llama-cpp-python

# Install app-specific requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install any other common utilities
RUN pip install --no-cache-dir ipython python-magic

COPY sandbox_runner.py /sandbox/sandbox_runner.py

# ENTRYPOINT ["python", "/sandbox/sandbox_runner.py"]