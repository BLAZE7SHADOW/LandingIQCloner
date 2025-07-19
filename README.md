# 🌐 Website Cloner

A powerful tool to capture and clone any website with pixel-perfect accuracy. Create offline copies of websites that look and work exactly like the original.

## ✨ Features

- **🎯 Pixel Perfect**: Captures exactly what you see in the browser
- **📱 Responsive**: Preserves mobile and desktop layouts
- **⚡ Fast**: Works offline once captured
- **🔍 Comparison View**: Side-by-side comparison with original
- **📁 History**: Keeps all your captures organized
- **💾 Export**: Download captures as ZIP files
- **🎨 Modern UI**: Clean, intuitive interface

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Installation

1. **Clone or download this repository**
2. **Run the setup script**:
   ```bash
   cd website_cloner
   python3 setup.py
   ```

3. **Start the application**:
   ```bash
   python3 app.py
   ```

4. **Open your browser** to `http://localhost:5000`

### Manual Installation

If the setup script doesn't work, install manually:

```bash
# Install Python packages
pip3 install -r requirements.txt

# Install Playwright browsers
python3 -m playwright install chromium

# Start the application
python3 app.py
```

## 🎯 How to Use

### Basic Usage

1. **Enter a URL** in the input field (e.g., `https://example.com`)
2. **Click "Capture"** to start the cloning process
3. **Wait for completion** - you'll see real-time progress
4. **View your capture** in the history sidebar

### Viewing Captures

- **View**: Open the captured site in full screen
- **Compare**: Side-by-side comparison with the original
- **Download**: Export as ZIP file
- **Delete**: Remove the capture

### Comparison Modes

- **Split View**: Original and captured side-by-side
- **Original Only**: View just the original website
- **Captured Only**: View just the captured website
- **New Tab**: Open captured site in a new tab

## 📁 File Structure

```
website_cloner/
├── app.py                 # Flask web application
├── page_cloner.py         # Core capture engine
├── requirements.txt       # Python dependencies
├── setup.py              # Setup script
├── templates/            # HTML templates
│   ├── index.html        # Main dashboard
│   ├── view.html         # Full-screen view
│   └── compare.html      # Comparison view
├── static/               # CSS and JavaScript
│   ├── style.css         # UI styling
│   └── script.js         # Frontend functionality
└── captured_sites/       # Captured websites
    └── example_com_2024_07_18_14_30_25/
        ├── index.html     # Captured HTML
        ├── assets/        # CSS, JS, images
        ├── screenshot.png # Visual verification
        └── metadata.json  # Capture information
```

## 🔧 Technical Details

### How It Works

1. **Browser Automation**: Uses Playwright to load the website in a real browser
2. **Asset Discovery**: Finds all CSS, JavaScript, images, and fonts
3. **Download**: Downloads all assets to local storage
4. **HTML Rewriting**: Updates all links to point to local files
5. **Comparison**: Serves both original and captured versions

### Supported Content

- ✅ HTML, CSS, JavaScript
- ✅ Images (PNG, JPG, SVG, WebP)
- ✅ Web fonts (Google Fonts, custom fonts)
- ✅ CSS animations and transitions
- ✅ Responsive design
- ✅ Modern frameworks (React, Vue, Angular)
- ✅ Single Page Applications (SPAs)
- ✅ Dynamic content

### Limitations

- ❌ Real-time data (APIs, live feeds)
- ❌ Server-side functionality
- ❌ User authentication
- ❌ WebSocket connections
- ❌ Complex JavaScript interactions requiring backend

## 🌟 Examples

### Test with these websites:

- **Simple**: `https://example.com`
- **News**: `https://news.ycombinator.com`
- **Portfolio**: `https://github.com`
- **E-commerce**: `https://amazon.com`

## 🛠️ Development

### Running in Development

```bash
# Set Flask environment
export FLASK_ENV=development

# Run with auto-reload
python app.py
```

### Project Structure

- `page_cloner.py`: Core website capture logic
- `app.py`: Flask web server and API endpoints
- `templates/`: Jinja2 HTML templates
- `static/`: CSS and JavaScript files

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

## 🐛 Troubleshooting

### Common Issues

**"Playwright not found"**
```bash
playwright install chromium
```

**"Permission denied"**
```bash
chmod +x setup.py
```

**"Port already in use"**
```bash
# Kill process on port 5000
kill -9 $(lsof -ti:5000)
```

**"Module not found"**
```bash
pip install -r requirements.txt
```

### Support

If you encounter issues:
1. Check the console for error messages
2. Verify all dependencies are installed
3. Try with a simple website first (e.g., example.com)
4. Check network connectivity

## 🎉 Enjoy!

Start capturing websites and creating perfect offline copies! 🚀