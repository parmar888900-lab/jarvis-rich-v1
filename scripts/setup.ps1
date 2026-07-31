"""Setup script for JARVIS AI (Windows PowerShell)."""

Write-Host "=== JARVIS AI Setup ===" -ForegroundColor Cyan

# Create virtual environment
if (-not (Test-Path "venv")) {
    Write-Host "Creating Python virtual environment..."
    python -m venv venv
}

Write-Host "Installing Python dependencies..."
& ".\venv\Scripts\pip" install -r requirements.txt

Write-Host "Installing frontend dependencies..."
Push-Location frontend
npm install
Pop-Location

Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Install Ollama: https://ollama.com/download"
Write-Host "  2. Pull a model:    ollama pull llama3.2"
Write-Host "  3. Start backend:   cd backend && ..\venv\Scripts\python -m uvicorn app:app --reload"
Write-Host "  4. Start frontend:  cd frontend && npm run dev"
