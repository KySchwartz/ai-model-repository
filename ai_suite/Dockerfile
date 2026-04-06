FROM python:3.11

# Install system tools
RUN apt-get update && apt-get install -y \
    gcc \
    libmagic1 \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install heavy ML dependencies (CPU Only)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir tensorflow-cpu

# Pre-install common libs to prevent model re-installs
RUN pip install --no-cache-dir scikit-learn scikit-image pandas numpy Pillow ipython
RUN pip install --no-cache-dir python-docx fpdf reportlab opencv-python-headless

# Verify the installs (helps for debugging build logs)
RUN python -c "import torch; print(f'Torch version: {torch.__version__}')"

# Install app-specific requirements
# IMPORTANT: Ensure torch/tensorflow/etc are NOT in this requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY routes ./routes
COPY utils ./utils

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]