#!/bin/bash

set -e

echo "Stopping backend service..."

sudo systemctl stop analytics-backend || true


APP_DIR=/var/www/analytics

cd $APP_DIR

echo "Setting up Python backend..."

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

echo "Deploying frontend build..."

# React build already exists in frontend/dist
sudo rm -rf /var/www/html/*
cp -r analytics/frontend/dist/* /var/www/html/
#
sudo systemctl start analytics-backend || true
