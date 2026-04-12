#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const distDir = path.join(__dirname, 'dist');

// Ensure dist directory exists
if (!fs.existsSync(distDir)) {
  fs.mkdirSync(distDir, { recursive: true });
}

// Files to copy (NOTE: sidebar.html is built by Vite, don't overwrite it!)
const filesToCopy = [
  'manifest.json',
  'background.js',
  'content.js',
  'content.css'
  // sidebar.html is processed by Vite and should NOT be copied from source
];

console.log('Copying extension files...');

// Copy individual files
filesToCopy.forEach(file => {
  const src = path.join(__dirname, file);
  const dest = path.join(distDir, file);
  
  if (fs.existsSync(src)) {
    fs.copyFileSync(src, dest);
    console.log(`✓ Copied ${file}`);
  } else {
    console.warn(`⚠ Warning: ${file} not found`);
  }
});

// Copy public directory recursively
const publicDir = path.join(__dirname, 'public');
if (fs.existsSync(publicDir)) {
  console.log('Copying public assets...');
  copyDir(publicDir, path.join(distDir, 'public'));
  
  // Also copy public contents directly to dist (for logo access)
  const publicContents = fs.readdirSync(publicDir);
  publicContents.forEach(item => {
    const src = path.join(publicDir, item);
    const dest = path.join(distDir, item);
    const stat = fs.statSync(src);
    
    if (stat.isDirectory()) {
      copyDir(src, dest);
    } else {
      fs.copyFileSync(src, dest);
    }
  });
  console.log('✓ Copied public assets');
}

function copyDir(src, dest) {
  if (!fs.existsSync(dest)) {
    fs.mkdirSync(dest, { recursive: true });
  }
  
  const entries = fs.readdirSync(src);
  entries.forEach(entry => {
    const srcPath = path.join(src, entry);
    const destPath = path.join(dest, entry);
    const stat = fs.statSync(srcPath);
    
    if (stat.isDirectory()) {
      copyDir(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  });
}

console.log('Extension files copied successfully!');
