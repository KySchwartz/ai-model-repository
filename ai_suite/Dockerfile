FROM python:3.11

# Install system tools for building packages and file detection
RUN apt-get update && apt-get install -y \
    gcc \
    libmagic1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Define Pre-installs (Bigger drive space, slower build / faster for users)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir tensorflow-cpu
RUN pip install --no-cache-dir scikit-learn scikit-image pandas numpy Pillow ipython
RUN pip install --no-cache-dir python-docx fpdf opencv-python-headless

# Create a workspace for extracting zip files
RUN mkdir -p /app/workspaces && chmod 777 /app/workspaces

COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]