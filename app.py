from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import os
import json
from pathlib import Path
import threading
import time
from page_cloner import WebsiteCloner

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# Global variables for progress tracking
capture_progress = {}
capture_lock = threading.Lock()

cloner = WebsiteCloner()

@app.route('/')
def index():
    """Main dashboard"""
    captures = cloner.get_all_captures()
    return render_template('index.html', captures=captures)

@app.route('/api/capture', methods=['POST'])
def capture_website():
    """Start website capture"""
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    # Start capture in background thread
    thread_id = str(int(time.time() * 1000))
    
    def capture_with_progress():
        def progress_callback(message):
            with capture_lock:
                capture_progress[thread_id] = {
                    'status': 'in_progress',
                    'message': message,
                    'timestamp': time.time()
                }
        
        try:
            result = cloner.capture_page(url, progress_callback)
            with capture_lock:
                capture_progress[thread_id] = {
                    'status': 'completed',
                    'message': 'Capture completed successfully!',
                    'result': result,
                    'timestamp': time.time()
                }
        except Exception as e:
            with capture_lock:
                capture_progress[thread_id] = {
                    'status': 'error',
                    'message': f'Error: {str(e)}',
                    'timestamp': time.time()
                }
    
    thread = threading.Thread(target=capture_with_progress)
    thread.start()
    
    return jsonify({'thread_id': thread_id})

@app.route('/api/progress/<thread_id>')
def get_progress(thread_id):
    """Get capture progress"""
    with capture_lock:
        progress = capture_progress.get(thread_id, {
            'status': 'not_found',
            'message': 'Capture not found'
        })
    
    # Clean up old progress entries
    current_time = time.time()
    with capture_lock:
        keys_to_remove = [
            key for key, value in capture_progress.items()
            if current_time - value.get('timestamp', 0) > 300  # 5 minutes
        ]
        for key in keys_to_remove:
            del capture_progress[key]
    
    return jsonify(progress)

@app.route('/api/captures')
def get_captures():
    """Get all captures"""
    captures = cloner.get_all_captures()
    return jsonify(captures)

@app.route('/view/<folder_name>')
def view_capture(folder_name):
    """View specific capture in full screen"""
    capture_dir = cloner.base_dir / folder_name
    if not capture_dir.exists():
        return "Capture not found", 404
    
    # Load metadata
    metadata_path = capture_dir / "metadata.json"
    metadata = {}
    if metadata_path.exists():
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
    
    return render_template('view.html', 
                         folder_name=folder_name, 
                         metadata=metadata)

@app.route('/compare/<folder_name>')
def compare_capture(folder_name):
    """Compare capture with original"""
    capture_dir = cloner.base_dir / folder_name
    if not capture_dir.exists():
        return "Capture not found", 404
    
    # Load metadata
    metadata_path = capture_dir / "metadata.json"
    metadata = {}
    if metadata_path.exists():
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
    
    return render_template('compare.html', 
                         folder_name=folder_name, 
                         metadata=metadata)

@app.route('/captured/<folder_name>/<path:filename>')
def serve_captured_file(folder_name, filename):
    """Serve captured files"""
    capture_dir = cloner.base_dir / folder_name
    if not capture_dir.exists():
        return "Capture not found", 404
    
    return send_from_directory(capture_dir, filename)

@app.route('/_next/static/chunks/<path:filename>')
def serve_nextjs_chunks(filename):
    """Serve Next.js JavaScript chunks from the most recent capture"""
    captures = cloner.get_all_captures()
    if not captures:
        return "No captures available", 404
    
    # Use the most recent capture
    latest_capture = captures[0]
    folder_name = latest_capture['folder_name']
    capture_dir = cloner.base_dir / folder_name
    
    # Look for the JS file in assets/js directory
    js_file_path = capture_dir / "assets" / "js" / filename
    if js_file_path.exists():
        return send_file(js_file_path, mimetype='application/javascript')
    
    return "JavaScript chunk not found", 404

@app.route('/_next/static/css/<path:filename>')
def serve_nextjs_css(filename):
    """Serve Next.js CSS files from the most recent capture"""
    captures = cloner.get_all_captures()
    if not captures:
        return "No captures available", 404
    
    # Use the most recent capture
    latest_capture = captures[0]
    folder_name = latest_capture['folder_name']
    capture_dir = cloner.base_dir / folder_name
    
    # Look for the CSS file in assets/css directory
    css_file_path = capture_dir / "assets" / "css" / filename
    if css_file_path.exists():
        return send_file(css_file_path, mimetype='text/css')
    
    return "CSS file not found", 404

@app.route('/_next/static/media/<path:filename>')
def serve_nextjs_media(filename):
    """Serve Next.js media files from the most recent capture"""
    captures = cloner.get_all_captures()
    if not captures:
        return "No captures available", 404
    
    # Use the most recent capture
    latest_capture = captures[0]
    folder_name = latest_capture['folder_name']
    capture_dir = cloner.base_dir / folder_name
    
    # Look for the media file in assets/images directory
    media_file_path = capture_dir / "assets" / "images" / filename
    if media_file_path.exists():
        # Determine MIME type based on file extension
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            mimetype = f'image/{filename.split(".")[-1].lower()}'
        elif filename.lower().endswith('.svg'):
            mimetype = 'image/svg+xml'
        elif filename.lower().endswith('.webp'):
            mimetype = 'image/webp'
        else:
            mimetype = 'application/octet-stream'
        
        return send_file(media_file_path, mimetype=mimetype)
    
    return "Media file not found", 404

@app.route('/download/<folder_name>')
def download_capture(folder_name):
    """Download capture as ZIP"""
    try:
        zip_path = cloner.create_zip(folder_name)
        return send_file(zip_path, as_attachment=True, download_name=f"{folder_name}.zip")
    except Exception as e:
        return f"Error creating ZIP: {str(e)}", 500

@app.route('/api/delete/<folder_name>', methods=['DELETE'])
def delete_capture(folder_name):
    """Delete a capture"""
    try:
        capture_dir = cloner.base_dir / folder_name
        if capture_dir.exists():
            import shutil
            shutil.rmtree(capture_dir)
            return jsonify({'message': 'Capture deleted successfully'})
        else:
            return jsonify({'error': 'Capture not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/screenshot/<folder_name>')
def get_screenshot(folder_name):
    """Get screenshot of capture"""
    capture_dir = cloner.base_dir / folder_name
    screenshot_path = capture_dir / "screenshot.png"
    
    if not screenshot_path.exists():
        return "Screenshot not found", 404
    
    return send_file(screenshot_path, mimetype='image/png')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)