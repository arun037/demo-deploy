#!/bin/bash
set -e

APP_DIR=/var/www/analytics
cd $APP_DIR

echo "Setting up Python backend..."

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

echo "backend permissions."
sudo chown -R ubuntu:ubuntu /var/www/analytics
sudo chmod -R 755 /var/www/analytics

echo "log directory"
sudo mkdir -p /var/log/analytics
sudo chown -R ubuntu:ubuntu /var/log/analytics
sudo chmod -R 775 /var/log/analytics

echo "Deploying frontend..."

sudo rm -rf /var/www/html/*
cp -r frontend/dist/* /var/www/html/

echo "frontend permissions"
sudo chown -R www-data:www-data /var/www/html
sudo chmod -R 755 /var/www/html

