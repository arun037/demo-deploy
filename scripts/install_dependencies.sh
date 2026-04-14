#!/bin/bash
set -e

APP_DIR=/var/www/analytics
cd $APP_DIR

echo "Setting up Python backend..."

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

echo "Deploying frontend..."

if [ ! -d "frontend/dist" ]; then
  echo "ERROR: dist not found!"
  ls -la frontend/
  exit 1
fi

sudo rm -rf /var/www/html/*
cp -r frontend/dist/* /var/www/html/
