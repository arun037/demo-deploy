#!/bin/bash
echo "Starting backend..."
sudo systemctl daemon-reload
sudo systemctl restart analytics.service
