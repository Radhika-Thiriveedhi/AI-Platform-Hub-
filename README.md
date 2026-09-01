# AI Platform Hub

AI Platform Hub is an enterprise machine learning and generative artificial intelligence platform. It provides a unified gateway, model registry, real-time inference telemetry, generative image studio, and local NLP suite.

---

## Installation

### Prerequisites
- Python 3.11 or higher
- Node.js 18+ and npm (optional, for frontend developer scripts)
- Git 2.30+

### Setup Environment
```bash
# Clone the repository
git clone <repository_url>
cd AI_Platform_Hub_Realistic_v2_50k_LOC

# Create and activate a Python virtual environment
python -m venv .venv

# On Linux / macOS:
source .venv/bin/activate

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Install Python dependencies
pip install -r requirements.txt

# Install Node dependencies (optional build scripts)
npm install
```

### Environment Configuration
Copy the sample environment file to configure your local runtime:
```bash
cp example.env .env
```
*(Note: `.env` is gitignored to protect sensitive credentials and avoid committing secrets).*

---

## Build

### Local Compilation
```bash
# Compile and validate Python bytecode
python -m compileall -q .

# Build frontend assets
npm run build
```

### Docker Container Build
```bash
# Build the production Docker image
docker build -t ai-platform-hub:latest .
```

---

## Run

### Option 1: Native Python Runner
```bash
# Launch the platform gateway server (runs at http://127.0.0.1:5000)
python main.py
```
Or use the npm script:
```bash
npm start
```

### Option 2: Docker Container
```bash
# Run the application in a container
docker run -d -p 5000:5000 --name ai-platform-hub ai-platform-hub:latest
```

Once running, access the dashboard at:
- Web Interface: [http://127.0.0.1:5000](http://127.0.0.1:5000)
- Telemetry & Overview: [http://127.0.0.1:5000/dashboard/](http://127.0.0.1:5000/dashboard/)
- Inference Console: [http://127.0.0.1:5000/chat/](http://127.0.0.1:5000/chat/)
- Generative Studio: [http://127.0.0.1:5000/image/](http://127.0.0.1:5000/image/)
- NLP Analysis Suite: [http://127.0.0.1:5000/analysis/](http://127.0.0.1:5000/analysis/)

---

## Dependencies

### Core Frameworks & Libraries
- **Backend Core**: Python 3.11+, Flask `>=3.0.0`, Werkzeug `>=3.0.0`, Jinja2 `>=3.1.0`
- **Database & Storage**: SQLite with WAL (Write-Ahead Logging) mode enabled
- **Local Conversational AI**: Ollama local inference runtime (`llama3.2:latest`)
- **Generative Image Synthesis**: FLUX.1 Diffusion Model engine
- **Testing & Quality**: pytest `>=8.0.0`, coverage `>=7.4.0`
- **Build System**: Docker, Make, npm

All dependencies are pinned in `requirements.txt` and `package.json`.

---

## Usage

### 1. Telemetry Dashboard
Navigate to `/dashboard/` to monitor real-time production model endpoints, accuracy benchmarks, traffic-split percentages, feature store online synchronizations, and cluster utilization metrics.

### 2. Inference Console (Chat)
Interact directly with the local Llama 3.2 model at `/chat/` for model evaluations, architectural queries, coding assistance, and platform questions.

### 3. Image Generation Studio
Generate high-resolution generative images at `/image/` using FLUX.1 across 12 artistic styles (Photorealistic, Anime, Digital Art, Watercolor, Cyberpunk, 3D Render, etc.).

### 4. Text Analysis Suite
Run deterministic NLP analysis at `/analysis/` across 8 tasks: Sentiment Scoring, Named Entity Recognition (NER), Keyword Extraction, Summarization, Readability Scoring, Topic Modeling, Toxicity Scanning, and Language Identification.

---

## Testing

Run the automated test suite:
```bash
pytest tests/
```
Or via npm:
```bash
npm test
```
