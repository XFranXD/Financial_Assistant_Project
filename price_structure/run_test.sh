#!/bin/bash
set -e

echo "================================================"
echo " Subsystem 4 — Price Structure Analyzer Test"
echo "================================================"

echo ""
echo "Creating temporary virtual environment..."
python3 -m venv .venv_temp

echo "Activating and installing dependencies..."
source .venv_temp/bin/activate
pip install -q yfinance pandas numpy

echo ""
echo "Running standalone test..."
echo ""
python test_standalone.py

echo ""
echo "================================================"
echo "Cleaning up virtual environment..."
deactivate
rm -rf .venv_temp
echo "Done. Virtual environment removed."
echo "================================================"
