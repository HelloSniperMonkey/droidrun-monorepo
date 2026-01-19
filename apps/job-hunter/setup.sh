#!/bin/bash
# Setup script for AI Job Hunter

echo "Setting up AI Job Hunter..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "uv is not installed. Please install it first:"
    echo "curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Check if MongoDB is running
if ! pgrep -x "mongod" > /dev/null; then
    echo "MongoDB is not running. Starting MongoDB..."
    if command -v brew &> /dev/null; then
        brew services start mongodb-community
    else
        echo "Please start MongoDB manually"
    fi
fi

# Install Python dependencies
echo "Installing Python dependencies..."
cd "$(dirname "$0")/../.." && uv sync

# Create necessary directories
echo "Creating directories..."
mkdir -p data/uploads
mkdir -p src/job_hunter/templates

# Copy environment template
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cp apps/job-hunter/.env.example .env
    echo "Please edit .env and add your API keys"
else
    echo ".env file already exists"
fi

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file and add your API keys:"
echo "   - MOBILERUN_API_KEY"
echo "   - OPENROUTER_API_KEY or ANTHROPIC_API_KEY"
echo "   - GOOGLE_SHEETS_SPREADSHEET_ID"
echo ""
echo "2. Set up Google Sheets:"
echo "   - Create a service account in Google Cloud Console"
echo "   - Enable Google Sheets API"
echo "   - Download credentials.json to project root"
echo "   - Create a Google Sheet and share with service account email"
echo ""
echo "3. Start the application:"
echo "   uv run python -m job_hunter.main web"
echo ""
echo "4. Open browser to http://localhost:5123"
echo ""
