#!/bin/bash

# Build script for Chrome extension
echo "Building extension..."

# Set extension build flag
export EXTENSION_BUILD=true

# Build with Vite
npm run build

# Copy extension files to dist
echo "Copying extension files..."
npm run copy:extension

echo "Extension build complete! Load 'dist' folder in Chrome/Edge extensions."
