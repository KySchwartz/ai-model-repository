FROM python:3.11

# Install system tools
RUN apt-get update && apt-get install -y \
    gcc \
    libmagic1 \
    libgl1 \
    libglib2.0-0 \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install heavy ML dependencies
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir tensorflow-cpu
RUN pip install --no-cache-dir scikit-learn scikit-image pandas numpy Pillow ipython
RUN pip install --no-cache-dir python-docx fpdf opencv-python-headless

# Install app-specific requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy ONLY the application code
COPY main.py .
COPY routes ./routes
COPY utils ./utils

# If you actually use media_shared, uncomment:
# COPY media_shared ./media_shared

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
