import os
import re
import requests
import json
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse, quote, unquote, parse_qs
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import shutil
import zipfile
import html


class WebsiteCloner:
    def __init__(self, base_dir="captured_sites"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def sanitize_filename(self, filename):
        """Convert filename to safe filesystem name"""
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = re.sub(r'[^\w\s\-_.]', '', filename)
        return filename[:100]  # Limit length
        
    def parse_nextjs_image_url(self, url):
        """Parse Next.js image optimization URLs to extract actual image path"""
        try:
            # Check if this is a Next.js image optimization URL
            if '/_next/image?' in url:
                parsed = urlparse(url)
                query_params = parse_qs(parsed.query)
                
                # Extract the actual image URL from the 'url' parameter
                if 'url' in query_params:
                    actual_url = unquote(query_params['url'][0])
                    return actual_url
            
            return url
        except Exception:
            return url
    
    def normalize_url_for_matching(self, url):
        """Normalize URL for matching by handling HTML entities"""
        # Decode HTML entities to get the actual URL
        decoded_url = html.unescape(url)
        return decoded_url
    
    def create_url_mapping(self, assets):
        """Create mapping from original URLs (both encoded/decoded) to local paths"""
        url_mapping = {}
        
        for asset_type, asset_list in assets.items():
            for asset in asset_list:
                if asset.get('local_path'):
                    original_url = asset['original_url']
                    local_path = asset['local_path']
                    
                    # Map both original and normalized versions
                    url_mapping[original_url] = local_path
                    url_mapping[self.normalize_url_for_matching(original_url)] = local_path
                    
                    # Also map HTML-encoded version
                    encoded_url = html.escape(original_url)
                    url_mapping[encoded_url] = local_path
        
        return url_mapping
        
    def create_capture_folder(self, url):
        """Create timestamped folder for capture"""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.replace('www.', '')
        timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        folder_name = f"{self.sanitize_filename(domain)}_{timestamp}"
        
        capture_dir = self.base_dir / folder_name
        capture_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        (capture_dir / "assets" / "css").mkdir(parents=True, exist_ok=True)
        (capture_dir / "assets" / "js").mkdir(parents=True, exist_ok=True)
        (capture_dir / "assets" / "images").mkdir(parents=True, exist_ok=True)
        (capture_dir / "assets" / "fonts").mkdir(parents=True, exist_ok=True)
        (capture_dir / "assets" / "videos").mkdir(parents=True, exist_ok=True)
        (capture_dir / "assets" / "audio").mkdir(parents=True, exist_ok=True)
        (capture_dir / "assets" / "documents").mkdir(parents=True, exist_ok=True)
        
        return capture_dir
    
    def _create_analysis_package(self, capture_dir, assets, metadata):
        """Create analysis package optimized for LLM analysis"""
        try:
            # Create analysis package directory
            analysis_dir = capture_dir / "analysis-package"
            analysis_dir.mkdir(exist_ok=True)
            
            # Create subdirectories
            (analysis_dir / "key-assets").mkdir(exist_ok=True)
            (analysis_dir / "key-assets" / "logos").mkdir(exist_ok=True)
            (analysis_dir / "key-assets" / "hero-images").mkdir(exist_ok=True)
            (analysis_dir / "key-assets" / "feature-screenshots").mkdir(exist_ok=True)
            
            # Copy essential files
            self._copy_essential_files(capture_dir, analysis_dir)
            
            # Extract and organize key visual assets
            self._extract_key_assets(capture_dir, analysis_dir, assets)
            
            # Generate analysis documentation
            self._generate_analysis_documentation(capture_dir, analysis_dir, assets, metadata)
            
            print(f"✅ Analysis package created at: {analysis_dir}")
            
        except Exception as e:
            print(f"Warning: Failed to create analysis package: {e}")
    
    def _copy_essential_files(self, capture_dir, analysis_dir):
        """Copy essential files for analysis"""
        essential_files = [
            "index.html",
            "screenshot.png", 
            "metadata.json"
        ]
        
        for filename in essential_files:
            source_path = capture_dir / filename
            if source_path.exists():
                shutil.copy2(source_path, analysis_dir / filename)
        
        # Find and copy main CSS file
        css_dir = capture_dir / "assets" / "css"
        if css_dir.exists():
            css_files = list(css_dir.glob("*.css"))
            if css_files:
                # Copy the largest CSS file (likely the main stylesheet)
                main_css = max(css_files, key=lambda f: f.stat().st_size)
                shutil.copy2(main_css, analysis_dir / "main-styles.css")
    
    def _extract_key_assets(self, capture_dir, analysis_dir, assets):
        """Extract and organize key visual assets"""
        images_dir = capture_dir / "assets" / "images"
        if not images_dir.exists():
            return
        
        # Define patterns for different asset types
        logo_patterns = ['logo', 'brand', 'icon']
        hero_patterns = ['hero', 'banner', 'background', 'main']
        feature_patterns = ['feature', 'screenshot', 'demo', 'example']
        
        # Get all image files
        image_files = list(images_dir.glob("*"))
        
        # Categorize and copy assets
        for img_file in image_files:
            filename_lower = img_file.name.lower()
            
            # Check for logos
            if any(pattern in filename_lower for pattern in logo_patterns):
                shutil.copy2(img_file, analysis_dir / "key-assets" / "logos" / img_file.name)
            
            # Check for hero images (also copy larger images)
            elif (any(pattern in filename_lower for pattern in hero_patterns) or 
                  img_file.stat().st_size > 100000):  # Large images likely to be hero/background
                shutil.copy2(img_file, analysis_dir / "key-assets" / "hero-images" / img_file.name)
            
            # Check for feature screenshots
            elif any(pattern in filename_lower for pattern in feature_patterns):
                shutil.copy2(img_file, analysis_dir / "key-assets" / "feature-screenshots" / img_file.name)
    
    def _generate_analysis_documentation(self, capture_dir, analysis_dir, assets, metadata):
        """Generate analysis documentation and asset inventory"""
        
        # Create analysis brief
        analysis_brief = f"""# Landing Page Analysis Brief

## Site Information
- **Original URL**: {metadata.get('original_url', 'N/A')}
- **Final URL**: {metadata.get('final_url', 'N/A')}
- **Capture Time**: {metadata.get('capture_time', 'N/A')}
- **Folder**: {metadata.get('folder_name', 'N/A')}

## Asset Summary
- **CSS Files**: {metadata.get('assets', {}).get('css', 0)}
- **JavaScript Files**: {metadata.get('assets', {}).get('js', 0)}
- **Images**: {metadata.get('assets', {}).get('images', 0)}
- **Videos**: {metadata.get('assets', {}).get('videos', 0)}
- **Fonts**: {metadata.get('assets', {}).get('fonts', 0)}

## Files Included for Analysis

### Essential Files
1. **index.html** - Complete HTML structure and content
2. **screenshot.png** - Full page visual representation
3. **metadata.json** - Technical capture metadata
4. **main-styles.css** - Primary stylesheet with design system

### Key Visual Assets
- **Logos & Branding**: Located in `key-assets/logos/`
- **Hero Images**: Located in `key-assets/hero-images/`
- **Feature Screenshots**: Located in `key-assets/feature-screenshots/`

## Analysis Capabilities

This package enables comprehensive analysis of:
- **Visual Design**: Layout, typography, color scheme, spacing
- **User Experience**: Navigation, content hierarchy, call-to-actions
- **Content Strategy**: Messaging, value propositions, social proof
- **Technical Implementation**: HTML structure, CSS architecture
- **Conversion Optimization**: CTA placement, form design, trust signals
- **Brand Consistency**: Logo usage, color palette, visual elements
- **Responsive Design**: Mobile-first approach, breakpoints
- **Accessibility**: Semantic HTML, contrast ratios, navigation

## Recommended Analysis Approach

1. **Visual Assessment**: Start with screenshot.png for overall layout
2. **Content Analysis**: Review index.html for messaging and structure
3. **Design System**: Examine main-styles.css for design tokens
4. **Asset Quality**: Evaluate key visual assets for brand consistency
5. **Technical Review**: Check metadata.json for performance metrics

This package contains all necessary data for professional-grade landing page analysis.
"""
        
        # Write analysis brief
        with open(analysis_dir / "analysis-brief.md", 'w', encoding='utf-8') as f:
            f.write(analysis_brief)
        
        # Create asset inventory
        asset_inventory = {
            "capture_info": {
                "url": metadata.get('original_url'),
                "capture_time": metadata.get('capture_time'),
                "total_assets": sum(metadata.get('assets', {}).values())
            },
            "essential_files": {
                "html": "index.html",
                "screenshot": "screenshot.png", 
                "metadata": "metadata.json",
                "main_css": "main-styles.css"
            },
            "key_assets": {
                "logos": self._list_files_in_dir(analysis_dir / "key-assets" / "logos"),
                "hero_images": self._list_files_in_dir(analysis_dir / "key-assets" / "hero-images"),
                "feature_screenshots": self._list_files_in_dir(analysis_dir / "key-assets" / "feature-screenshots")
            },
            "analysis_recommendations": [
                "Start with visual assessment using screenshot.png",
                "Review content structure in index.html",
                "Analyze design system in main-styles.css",
                "Evaluate brand consistency across key assets",
                "Check technical implementation in metadata.json"
            ]
        }
        
        # Write asset inventory
        with open(analysis_dir / "asset-inventory.json", 'w', encoding='utf-8') as f:
            json.dump(asset_inventory, f, indent=2)
        
        print(f"Generated analysis documentation with {len(asset_inventory['key_assets']['logos']) + len(asset_inventory['key_assets']['hero_images']) + len(asset_inventory['key_assets']['feature_screenshots'])} key assets")
    
    def _list_files_in_dir(self, directory):
        """List files in a directory"""
        if directory.exists():
            return [f.name for f in directory.iterdir() if f.is_file()]
        return []
        
    def capture_page(self, url, progress_callback=None):
        """Main capture function"""
        def log_progress(message):
            if progress_callback:
                progress_callback(message)
            print(message)
            
        try:
            log_progress("🚀 Starting capture...")
            capture_dir = self.create_capture_folder(url)
            
            # Initialize browser
            log_progress("🌐 Launching browser...")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # Set realistic viewport
                page.set_viewport_size({"width": 1920, "height": 1080})
                
                log_progress("📄 Loading page...")
                response = page.goto(url, wait_until="networkidle", timeout=30000)
                
                if not response.ok:
                    raise Exception(f"Failed to load page: {response.status}")
                
                # Wait for dynamic content and trigger lazy loading
                log_progress("⏳ Waiting for dynamic content...")
                page.wait_for_timeout(3000)
                
                # Enhanced but simpler dynamic content loading
                log_progress("📜 Triggering lazy loading and dynamic content...")
                page.evaluate("""
                    () => {
                        return new Promise((resolve) => {
                            let totalHeight = 0;
                            let distance = 150;
                            let timer = setInterval(() => {
                                let scrollHeight = document.body.scrollHeight;
                                window.scrollBy(0, distance);
                                totalHeight += distance;
                                if(totalHeight >= scrollHeight || totalHeight > 15000) {
                                    clearInterval(timer);
                                    window.scrollTo(0, 0);
                                    setTimeout(resolve, 2000);
                                }
                            }, 200);
                        });
                    }
                """)
                
                # Additional wait for dynamic content and intersection observers
                log_progress("⏳ Waiting for dynamic content to render...")
                page.wait_for_timeout(4000)
                
                # Scroll to trigger section-based content
                log_progress("🎯 Triggering section-based content...")
                page.evaluate("""
                    () => {
                        // Scroll to bottom and back to top to trigger all content
                        window.scrollTo(0, document.body.scrollHeight);
                    }
                """)
                page.wait_for_timeout(2000)
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(2000)
                
                # Take screenshot
                log_progress("📸 Taking screenshot...")
                screenshot_path = capture_dir / "screenshot.png"
                page.screenshot(path=str(screenshot_path), full_page=True)
                
                # Get final HTML
                log_progress("🔍 Extracting HTML...")
                html_content = page.content()
                
                # Get current URL (in case of redirects)
                final_url = page.url
                
                browser.close()
                
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Track assets
            assets = {
                'css': [],
                'js': [],
                'images': [],
                'fonts': [],
                'videos': [],
                'audio': [],
                'documents': []
            }
            
            # Find all assets
            log_progress("🔍 Discovering assets...")
            self._discover_assets(soup, final_url, assets)
            
            # Download assets
            log_progress("⬇️ Downloading assets...")
            self._download_assets(assets, capture_dir, progress_callback)
            
            # Rewrite HTML
            log_progress("✏️ Rewriting HTML...")
            self._rewrite_html(soup, assets, capture_dir)
            
            # Save metadata
            metadata = {
                'original_url': url,
                'final_url': final_url,
                'capture_time': datetime.now().isoformat(),
                'assets': {k: len(v) for k, v in assets.items()},
                'folder_name': capture_dir.name
            }
            
            with open(capture_dir / "metadata.json", 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Create analysis package
            log_progress("📊 Creating analysis package...")
            self._create_analysis_package(capture_dir, assets, metadata)
                
            log_progress("✅ Capture completed successfully!")
            return capture_dir.name
            
        except Exception as e:
            log_progress(f"❌ Error: {str(e)}")
            raise
            
    def _discover_assets(self, soup, base_url, assets):
        """Discover all assets in the page"""
        
        # CSS files
        for link in soup.find_all('link', rel='stylesheet'):
            href = link.get('href')
            if href:
                full_url = urljoin(base_url, href)
                assets['css'].append({
                    'url': full_url,
                    'element': link,
                    'original_url': href
                })
        
        # JavaScript files
        for script in soup.find_all('script', src=True):
            src = script.get('src')
            if src:
                full_url = urljoin(base_url, src)
                assets['js'].append({
                    'url': full_url,
                    'element': script,
                    'original_url': src
                })
        
        # Images (regular img tags)
        for img in soup.find_all('img'):
            # Check src attribute
            src = img.get('src')
            if src and not src.startswith('data:'):
                # Parse Next.js image optimization URLs
                actual_url = self.parse_nextjs_image_url(src)
                full_url = urljoin(base_url, actual_url)
                assets['images'].append({
                    'url': full_url,
                    'element': img,
                    'original_url': src,
                    'actual_url': actual_url,
                    'attribute': 'src',
                    'is_nextjs_image': '/_next/image?' in src
                })
            
            # Check data-src for lazy loading
            data_src = img.get('data-src')
            if data_src and not data_src.startswith('data:'):
                # Parse Next.js image optimization URLs
                actual_url = self.parse_nextjs_image_url(data_src)
                full_url = urljoin(base_url, actual_url)
                assets['images'].append({
                    'url': full_url,
                    'element': img,
                    'original_url': data_src,
                    'actual_url': actual_url,
                    'attribute': 'data-src',
                    'is_nextjs_image': '/_next/image?' in data_src
                })
            
            # Check srcset for responsive images
            srcset = img.get('srcset')
            if srcset:
                for src_item in srcset.split(','):
                    src_url = src_item.strip().split()[0]
                    if not src_url.startswith('data:'):
                        # Parse Next.js image optimization URLs
                        actual_url = self.parse_nextjs_image_url(src_url)
                        full_url = urljoin(base_url, actual_url)
                        assets['images'].append({
                            'url': full_url,
                            'element': img,
                            'original_url': src_url,
                            'actual_url': actual_url,
                            'attribute': 'srcset',
                            'is_nextjs_image': '/_next/image?' in src_url
                        })
        
        # Picture elements
        for picture in soup.find_all('picture'):
            for source in picture.find_all('source'):
                srcset = source.get('srcset')
                if srcset:
                    for src_item in srcset.split(','):
                        src_url = src_item.strip().split()[0]
                        if not src_url.startswith('data:'):
                            # Parse Next.js image optimization URLs
                            actual_url = self.parse_nextjs_image_url(src_url)
                            full_url = urljoin(base_url, actual_url)
                            assets['images'].append({
                                'url': full_url,
                                'element': source,
                                'original_url': src_url,
                                'actual_url': actual_url,
                                'attribute': 'srcset',
                                'is_nextjs_image': '/_next/image?' in src_url
                            })
        
        # Video elements
        for video in soup.find_all('video'):
            # Check src attribute
            src = video.get('src')
            if src:
                full_url = urljoin(base_url, src)
                assets['videos'].append({
                    'url': full_url,
                    'element': video,
                    'original_url': src,
                    'attribute': 'src'
                })
            
            # Check source elements within video
            for source in video.find_all('source'):
                src = source.get('src')
                if src:
                    full_url = urljoin(base_url, src)
                    assets['videos'].append({
                        'url': full_url,
                        'element': source,
                        'original_url': src,
                        'attribute': 'src'
                    })
        
        # Audio elements
        for audio in soup.find_all('audio'):
            # Check src attribute
            src = audio.get('src')
            if src:
                full_url = urljoin(base_url, src)
                assets['audio'].append({
                    'url': full_url,
                    'element': audio,
                    'original_url': src,
                    'attribute': 'src'
                })
            
            # Check source elements within audio
            for source in audio.find_all('source'):
                src = source.get('src')
                if src:
                    full_url = urljoin(base_url, src)
                    assets['audio'].append({
                        'url': full_url,
                        'element': source,
                        'original_url': src,
                        'attribute': 'src'
                    })
        
        # Favicon and icons
        for link in soup.find_all('link', rel=['icon', 'shortcut icon', 'apple-touch-icon']):
            href = link.get('href')
            if href:
                full_url = urljoin(base_url, href)
                assets['images'].append({
                    'url': full_url,
                    'element': link,
                    'original_url': href,
                    'attribute': 'href'
                })
        
        # Background images in CSS
        for element in soup.find_all(style=True):
            style = element.get('style', '')
            bg_matches = re.findall(r'background-image:\s*url\(["\']?([^"\']+)["\']?\)', style)
            for bg_url in bg_matches:
                if not bg_url.startswith('data:'):
                    full_url = urljoin(base_url, bg_url)
                    assets['images'].append({
                        'url': full_url,
                        'element': element,
                        'original_url': bg_url,
                        'is_background': True
                    })
        
        # Documents (PDFs, etc.)
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            if href and any(href.lower().endswith(ext) for ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']):
                full_url = urljoin(base_url, href)
                assets['documents'].append({
                    'url': full_url,
                    'element': link,
                    'original_url': href,
                    'attribute': 'href'
                })
        
        # Fonts
        for link in soup.find_all('link', rel='preload'):
            if link.get('as') == 'font':
                href = link.get('href')
                if href:
                    full_url = urljoin(base_url, href)
                    assets['fonts'].append({
                        'url': full_url,
                        'element': link,
                        'original_url': href,
                        'attribute': 'href'
                    })
        
        # CSS @font-face and other URL references (parse existing CSS)
        for style in soup.find_all('style'):
            css_content = style.string
            if css_content:
                # Find font URLs
                font_matches = re.findall(r'url\(["\']?([^"\']+\.(woff2?|eot|ttf|otf))["\']?\)', css_content)
                for font_url, _ in font_matches:
                    if not font_url.startswith('data:'):
                        full_url = urljoin(base_url, font_url)
                        assets['fonts'].append({
                            'url': full_url,
                            'element': style,
                            'original_url': font_url,
                            'is_css_font': True
                        })
                
                # Find other asset URLs in CSS
                url_matches = re.findall(r'url\(["\']?([^"\']+)["\']?\)', css_content)
                for asset_url in url_matches:
                    if not asset_url.startswith('data:') and not any(asset_url.endswith(ext) for ext in ['.woff', '.woff2', '.eot', '.ttf', '.otf']):
                        full_url = urljoin(base_url, asset_url)
                        if any(asset_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp']):
                            assets['images'].append({
                                'url': full_url,
                                'element': style,
                                'original_url': asset_url,
                                'is_css_image': True
                            })
                    
    def _download_assets(self, assets, capture_dir, progress_callback=None):
        """Download all discovered assets"""
        total_assets = sum(len(asset_list) for asset_list in assets.values())
        downloaded = 0
        
        for asset_type, asset_list in assets.items():
            for asset in asset_list:
                try:
                    downloaded += 1
                    if progress_callback:
                        progress_callback(f"📥 Downloading {asset_type} ({downloaded}/{total_assets})")
                    
                    response = self.session.get(asset['url'], timeout=10)
                    response.raise_for_status()
                    
                    # Generate filename - use actual URL for Next.js images to get better filenames
                    url_for_filename = asset.get('actual_url', asset['url'])
                    parsed_url = urlparse(url_for_filename)
                    filename = os.path.basename(parsed_url.path) or 'index'
                    filename = self.sanitize_filename(filename)
                    
                    # Add extension if missing
                    common_extensions = {
                        'css': ['.css'],
                        'js': ['.js'],
                        'images': ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp', '.avif'],
                        'videos': ['.mp4', '.webm', '.ogg', '.mov', '.avi'],
                        'audio': ['.mp3', '.wav', '.ogg', '.m4a', '.flac'],
                        'fonts': ['.woff', '.woff2', '.eot', '.ttf', '.otf'],
                        'documents': ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']
                    }
                    
                    # Check if filename already has appropriate extension
                    has_extension = any(filename.lower().endswith(ext) for ext in common_extensions.get(asset_type, []))
                    
                    if not has_extension:
                        # Add default extension based on asset type
                        if asset_type == 'css':
                            filename += '.css'
                        elif asset_type == 'js':
                            filename += '.js'
                        elif asset_type == 'images':
                            filename += '.png'
                        elif asset_type == 'videos':
                            filename += '.mp4'
                        elif asset_type == 'audio':
                            filename += '.mp3'
                        elif asset_type == 'fonts':
                            filename += '.woff'
                        elif asset_type == 'documents':
                            filename += '.pdf'
                    
                    # Ensure unique filename
                    counter = 1
                    original_filename = filename
                    while (capture_dir / "assets" / asset_type / filename).exists():
                        name, ext = os.path.splitext(original_filename)
                        filename = f"{name}_{counter}{ext}"
                        counter += 1
                    
                    filepath = capture_dir / "assets" / asset_type / filename
                    
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    
                    asset['local_path'] = f"assets/{asset_type}/{filename}"
                    
                except Exception as e:
                    print(f"Failed to download {asset['url']}: {e}")
                    asset['local_path'] = None
                    
    def _rewrite_images_statically(self, soup, assets, url_mapping):
        """Rewrite image URLs in static HTML (the approach that worked before)"""
        
        try:
            # Group image assets by element and attribute for complex rewriting
            element_assets = {}
            for asset in assets['images']:
                if asset.get('local_path') and asset.get('element'):
                    element_id = id(asset['element'])
                    attribute = asset.get('attribute', 'src')
                    
                    if element_id not in element_assets:
                        element_assets[element_id] = {'element': asset['element'], 'assets': {}}
                    
                    if attribute not in element_assets[element_id]['assets']:
                        element_assets[element_id]['assets'][attribute] = []
                    
                    element_assets[element_id]['assets'][attribute].append(asset)
            
            # Process each element's assets
            for element_id, element_data in element_assets.items():
                element = element_data['element']
                assets_by_attr = element_data['assets']
                
                for attribute, element_assets_list in assets_by_attr.items():
                    if attribute == 'srcset':
                        # Rebuild srcset completely
                        self._rebuild_srcset(element, element_assets_list, url_mapping)
                    elif any(asset.get('is_background') for asset in element_assets_list):
                        # Handle background images
                        self._rebuild_background_style(element, element_assets_list, url_mapping)
                    elif any(asset.get('is_css_image') for asset in element_assets_list):
                        # Handle CSS image references
                        self._rebuild_css_images(element, element_assets_list, url_mapping)
                    else:
                        # Handle simple src/href attributes
                        if element_assets_list:
                            # Use the first (or only) asset for simple attributes
                            asset = element_assets_list[0]
                            if asset.get('local_path') and element is not None:
                                try:
                                    element[attribute] = asset['local_path']
                                except Exception as e:
                                    print(f"Warning: Failed to update {attribute} on element: {e}")
            
            print(f"Static image rewriting completed for {len(element_assets)} elements")
            
        except Exception as e:
            print(f"Warning: Error in static image rewriting: {e}")

    def _inject_minimal_nextjs_override(self, soup, assets):
        """Inject minimal Next.js Image loader override that preserves all other JavaScript"""
        
        try:
            # Create mapping of original URLs to local paths
            url_mapping = {}
            for asset in assets.get('images', []):
                if asset.get('local_path') and asset.get('original_url'):
                    original_url = asset['original_url']
                    local_path = asset['local_path']
                    
                    # Handle Next.js image optimization URLs - extract actual URL
                    if '/_next/image?' in original_url:
                        actual_url = self.parse_nextjs_image_url(original_url)
                        if actual_url and not actual_url.startswith('/_next/'):
                            url_mapping[actual_url] = local_path
                    elif not original_url.startswith('/_next/'):
                        url_mapping[original_url] = local_path
            
            if not url_mapping:
                print("No image URL mappings for minimal Next.js override")
                return
            
            # Create minimal override script that only touches image loading
            minimal_script = f"""
            <script>
            (function() {{
                console.log('🎯 Minimal Next.js Image override loaded');
                
                // URL mappings for local assets
                const imageUrlMapping = {json.dumps(url_mapping)};
                
                // Override Image src property only when it would use /_next/image
                function overrideImageSrc() {{
                    const images = document.querySelectorAll('img');
                    images.forEach(img => {{
                        const originalSrc = img.getAttribute('src');
                        if (originalSrc && originalSrc.includes('/_next/image?')) {{
                            try {{
                                const url = new URL(originalSrc, window.location.origin);
                                const actualUrl = decodeURIComponent(url.searchParams.get('url') || '');
                                
                                if (imageUrlMapping[actualUrl]) {{
                                    console.log('🔧 Fixing Next.js image:', actualUrl, '->', imageUrlMapping[actualUrl]);
                                    img.src = imageUrlMapping[actualUrl];
                                    img.setAttribute('src', imageUrlMapping[actualUrl]);
                                }}
                            }} catch (e) {{
                                // Ignore URL parsing errors
                            }}
                        }}
                    }});
                }}
                
                // Run immediately and after DOM changes
                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', overrideImageSrc);
                }} else {{
                    overrideImageSrc();
                }}
                
                // Watch for new images (but don't interfere with other React functionality)
                const observer = new MutationObserver(() => {{
                    overrideImageSrc();
                }});
                
                observer.observe(document.body, {{
                    childList: true,
                    subtree: true
                }});
                
                // Additional safety check after React hydration
                setTimeout(overrideImageSrc, 1000);
                setTimeout(overrideImageSrc, 3000);
                
                console.log('✅ Minimal Next.js Image override active');
            }})();
            </script>
            """
            
            # Insert at the end of head to run after other scripts load
            head = soup.find('head')
            if head:
                script_tag = BeautifulSoup(minimal_script, 'html.parser')
                head.append(script_tag)
                print(f"Injected minimal Next.js override script with {len(url_mapping)} mappings")
            else:
                print("Warning: No head tag found, could not inject minimal override")
                
        except Exception as e:
            print(f"Warning: Error injecting minimal Next.js override: {e}")

    def _inject_react_protection_script(self, soup, assets):
        """Inject aggressive multi-layer script to bulletproof images against React interference"""
        
        try:
            # Create clean mapping for protection script (exclude Next.js URLs to prevent React interference)
            url_mapping = {}
            for asset in assets.get('images', []):
                if asset.get('local_path') and asset.get('original_url'):
                    original_url = asset['original_url']
                    local_path = asset['local_path']
                    
                    # Handle Next.js image optimization URLs - extract actual URL but don't include Next.js URLs in mapping
                    if '/_next/image?' in original_url:
                        actual_url = self.parse_nextjs_image_url(original_url)
                        # Only include the clean actual URL, not the Next.js URL
                        if actual_url and not actual_url.startswith('/_next/'):
                            url_mapping[actual_url] = local_path
                    elif not original_url.startswith('/_next/'):
                        # Only include URLs that don't start with /_next/
                        url_mapping[original_url] = local_path
            
            if not url_mapping:
                print("No image URL mappings for protection script")
                return
            
            # Create aggressive bulletproof protection script
            protection_script = f"""
            <script>
            (function() {{
                console.log('🛡️ AGGRESSIVE React image protection loaded');
                
                // URL mappings to protect
                const imageUrlMapping = {json.dumps(url_mapping)};
                
                // Track protected images
                const protectedImages = new WeakSet();
                
                // Fix image URL function - Enhanced to handle Next.js patterns
                function getCorrectImageUrl(url) {{
                    if (imageUrlMapping[url]) {{
                        return imageUrlMapping[url];
                    }}
                    
                    // Handle Next.js image optimization URLs pattern
                    if (url && url.includes('/_next/image?')) {{
                        const urlParams = new URLSearchParams(url.split('?')[1]);
                        const actualUrl = decodeURIComponent(urlParams.get('url') || '');
                        
                        // Pattern matching for common static media files
                        if (actualUrl.includes('.png') || actualUrl.includes('.jpg') || actualUrl.includes('.webp') || actualUrl.includes('.svg')) {{
                            // Try to find a matching asset based on filename
                            const filename = actualUrl.split('/').pop();
                            if (filename) {{
                                for (const [mappedUrl, localPath] of Object.entries(imageUrlMapping)) {{
                                    if (localPath.includes(filename.split('.')[0])) {{
                                        return localPath;
                                    }}
                                }}
                            }}
                        }}
                        
                        // Check clean mapping after decoding
                        if (imageUrlMapping[actualUrl]) {{
                            return imageUrlMapping[actualUrl];
                        }}
                    }}
                    
                    // Handle direct Next.js static media URLs
                    if (url && url.includes('/_next/static/media/')) {{
                        const filename = url.split('/').pop().split('?')[0];
                        if (filename) {{
                            for (const [mappedUrl, localPath] of Object.entries(imageUrlMapping)) {{
                                if (localPath.includes(filename.split('.')[0])) {{
                                    return localPath;
                                }}
                            }}
                        }}
                    }}
                    
                    return url;
                }}
                
                // Check if URL should be fixed
                function shouldFixUrl(url) {{
                    return url && (
                        url.includes('/_next/image?') || 
                        url.includes('/_next/static/') ||
                        imageUrlMapping[url]
                    );
                }}
                
                // Aggressively fix image element
                function aggressivelyFixImage(img) {{
                    if (!img || img.tagName !== 'IMG') return;
                    
                    const currentSrc = img.src || img.getAttribute('src');
                    const correctSrc = getCorrectImageUrl(currentSrc);
                    
                    if (currentSrc !== correctSrc && correctSrc) {{
                        console.log('🔧 Fixing image:', currentSrc, '->', correctSrc);
                        img.src = correctSrc;
                        img.setAttribute('src', correctSrc);
                    }}
                    
                    // Fix srcset too
                    const currentSrcset = img.srcset || img.getAttribute('srcset');
                    if (currentSrcset) {{
                        const newSrcset = currentSrcset.split(',').map(item => {{
                            const parts = item.trim().split(' ');
                            if (parts.length > 0) {{
                                const fixedUrl = getCorrectImageUrl(parts[0]);
                                if (fixedUrl !== parts[0]) {{
                                    parts[0] = fixedUrl;
                                }}
                            }}
                            return parts.join(' ');
                        }}).join(', ');
                        
                        if (newSrcset !== currentSrcset) {{
                            img.srcset = newSrcset;
                            img.setAttribute('srcset', newSrcset);
                        }}
                    }}
                    
                    // Mark as protected
                    protectedImages.add(img);
                }}
                
                // Override setAttribute to prevent React from breaking images
                const originalSetAttribute = HTMLImageElement.prototype.setAttribute;
                HTMLImageElement.prototype.setAttribute = function(name, value) {{
                    if (name === 'src' && shouldFixUrl(value)) {{
                        const correctUrl = getCorrectImageUrl(value);
                        console.log('⚡ Intercepted setAttribute src:', value, '->', correctUrl);
                        return originalSetAttribute.call(this, name, correctUrl);
                    }}
                    if (name === 'srcset' && value) {{
                        const fixedSrcset = value.split(',').map(item => {{
                            const parts = item.trim().split(' ');
                            if (parts.length > 0 && shouldFixUrl(parts[0])) {{
                                parts[0] = getCorrectImageUrl(parts[0]);
                            }}
                            return parts.join(' ');
                        }}).join(', ');
                        return originalSetAttribute.call(this, name, fixedSrcset);
                    }}
                    return originalSetAttribute.call(this, name, value);
                }};
                
                // Override src property setter
                const originalSrcDescriptor = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src') || 
                                            Object.getOwnPropertyDescriptor(Element.prototype, 'src');
                if (originalSrcDescriptor && originalSrcDescriptor.set) {{
                    Object.defineProperty(HTMLImageElement.prototype, 'src', {{
                        get: originalSrcDescriptor.get,
                        set: function(value) {{
                            if (shouldFixUrl(value)) {{
                                const correctUrl = getCorrectImageUrl(value);
                                console.log('⚡ Intercepted src property:', value, '->', correctUrl);
                                return originalSrcDescriptor.set.call(this, correctUrl);
                            }}
                            return originalSrcDescriptor.set.call(this, value);
                        }},
                        configurable: true
                    }});
                }}
                
                // Aggressive MutationObserver to catch ALL changes
                const aggressiveObserver = new MutationObserver(mutations => {{
                    mutations.forEach(mutation => {{
                        // Check attribute changes
                        if (mutation.type === 'attributes' && mutation.target.tagName === 'IMG') {{
                            if (mutation.attributeName === 'src' || mutation.attributeName === 'srcset') {{
                                setTimeout(() => aggressivelyFixImage(mutation.target), 0);
                            }}
                        }}
                        
                        // Check new nodes
                        if (mutation.type === 'childList') {{
                            mutation.addedNodes.forEach(node => {{
                                if (node.nodeType === 1) {{
                                    if (node.tagName === 'IMG') {{
                                        setTimeout(() => aggressivelyFixImage(node), 0);
                                    }} else if (node.querySelectorAll) {{
                                        node.querySelectorAll('img').forEach(img => {{
                                            setTimeout(() => aggressivelyFixImage(img), 0);
                                        }});
                                    }}
                                }}
                            }});
                        }}
                    }});
                }});
                
                // Start aggressive monitoring
                aggressiveObserver.observe(document.body, {{
                    attributes: true,
                    childList: true,
                    subtree: true,
                    attributeFilter: ['src', 'srcset']
                }});
                
                // Continuous polling recovery (bulletproof backup)
                let pollCount = 0;
                const maxIntensivePolls = 100; // 10 seconds of intensive polling
                
                function continuousImageRecovery() {{
                    document.querySelectorAll('img').forEach(aggressivelyFixImage);
                    
                    pollCount++;
                    if (pollCount < maxIntensivePolls) {{
                        // Intensive polling for first 10 seconds
                        setTimeout(continuousImageRecovery, 100);
                    }} else {{
                        // Then poll every 2 seconds forever
                        setInterval(() => {{
                            document.querySelectorAll('img').forEach(aggressivelyFixImage);
                        }}, 2000);
                    }}
                }}
                
                // Start protection immediately
                function startProtection() {{
                    console.log('🚀 Starting aggressive image protection');
                    document.querySelectorAll('img').forEach(aggressivelyFixImage);
                    continuousImageRecovery();
                }}
                
                // Multiple triggers to ensure we catch everything
                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', startProtection);
                }} else {{
                    startProtection();
                }}
                
                // Additional triggers for React hydration
                setTimeout(startProtection, 100);
                setTimeout(startProtection, 500);
                setTimeout(startProtection, 1000);
                setTimeout(startProtection, 2000);
                setTimeout(startProtection, 5000);
                
                console.log('🛡️ Bulletproof image protection system activated!');
                
            }})();
            </script>
            """
            
            # Inject the script at the very beginning of head for early execution
            head = soup.find('head')
            if head:
                script_tag = BeautifulSoup(protection_script, 'html.parser')
                # Insert at the beginning of head to run before React
                head.insert(0, script_tag)
                print(f"Injected aggressive React protection script with {len(url_mapping)} mappings")
            else:
                print("Warning: No head tag found, could not inject protection script")
                
        except Exception as e:
            print(f"Warning: Error injecting aggressive React protection script: {e}")

    def _inject_image_url_fixer(self, soup, assets):
        """Inject runtime script to fix Next.js image URLs without removing any JavaScript"""
        
        try:
            # Create mapping from Next.js URLs to local paths
            url_mapping = {}
            for asset in assets.get('images', []):
                if asset.get('local_path') and asset.get('original_url'):
                    original_url = asset['original_url']
                    local_path = asset['local_path']
                    
                    # Handle Next.js image optimization URLs
                    if '/_next/image?' in original_url:
                        # Parse the actual image URL from Next.js optimization
                        actual_url = self.parse_nextjs_image_url(original_url)
                        url_mapping[original_url] = local_path
                        url_mapping[actual_url] = local_path
                    else:
                        url_mapping[original_url] = local_path
            
            if not url_mapping:
                print("No image URL mappings to inject")
                return
            
            # Create the runtime image fixer script
            image_fixer_script = f"""
            <script>
            (function() {{
                // URL mapping from original URLs to local paths
                const imageUrlMapping = {json.dumps(url_mapping)};
                
                function fixImageUrl(url) {{
                    // Check direct mapping first
                    if (imageUrlMapping[url]) {{
                        return imageUrlMapping[url];
                    }}
                    
                    // Handle Next.js image optimization URLs
                    if (url.includes('/_next/image?')) {{
                        const urlParams = new URLSearchParams(url.split('?')[1]);
                        const actualUrl = decodeURIComponent(urlParams.get('url') || '');
                        if (imageUrlMapping[actualUrl]) {{
                            return imageUrlMapping[actualUrl];
                        }}
                    }}
                    
                    return url; // Return original if no mapping found
                }}
                
                function fixImageElement(img) {{
                    if (img.src && img.src !== fixImageUrl(img.src)) {{
                        img.src = fixImageUrl(img.src);
                    }}
                    
                    if (img.srcset) {{
                        const newSrcset = img.srcset.split(',').map(item => {{
                            const parts = item.trim().split(' ');
                            if (parts.length > 0) {{
                                parts[0] = fixImageUrl(parts[0]);
                            }}
                            return parts.join(' ');
                        }}).join(', ');
                        img.srcset = newSrcset;
                    }}
                }}
                
                function fixAllImages() {{
                    // Fix existing images
                    document.querySelectorAll('img').forEach(fixImageElement);
                    
                    // Fix picture source elements
                    document.querySelectorAll('picture source').forEach(source => {{
                        if (source.srcset) {{
                            const newSrcset = source.srcset.split(',').map(item => {{
                                const parts = item.trim().split(' ');
                                if (parts.length > 0) {{
                                    parts[0] = fixImageUrl(parts[0]);
                                }}
                                return parts.join(' ');
                            }}).join(', ');
                            source.srcset = newSrcset;
                        }}
                    }});
                }}
                
                // Fix images immediately
                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', fixAllImages);
                }} else {{
                    fixAllImages();
                }}
                
                // Watch for dynamically added images
                const observer = new MutationObserver(mutations => {{
                    mutations.forEach(mutation => {{
                        mutation.addedNodes.forEach(node => {{
                            if (node.nodeType === 1) {{ // Element node
                                if (node.tagName === 'IMG') {{
                                    fixImageElement(node);
                                }} else if (node.querySelectorAll) {{
                                    node.querySelectorAll('img').forEach(fixImageElement);
                                    node.querySelectorAll('picture source').forEach(source => {{
                                        if (source.srcset) {{
                                            const newSrcset = source.srcset.split(',').map(item => {{
                                                const parts = item.trim().split(' ');
                                                if (parts.length > 0) {{
                                                    parts[0] = fixImageUrl(parts[0]);
                                                }}
                                                return parts.join(' ');
                                            }}).join(', ');
                                            source.srcset = newSrcset;
                                        }}
                                    }});
                                }}
                            }}
                        }});
                    }});
                }});
                
                observer.observe(document.body, {{
                    childList: true,
                    subtree: true
                }});
                
                console.log('Image URL fixer injected successfully');
            }})();
            </script>
            """
            
            # Inject the script into the head
            head = soup.find('head')
            if head:
                script_tag = BeautifulSoup(image_fixer_script, 'html.parser')
                head.append(script_tag)
                print(f"Injected image URL fixer with {len(url_mapping)} mappings")
            else:
                print("Warning: No head tag found, could not inject image fixer script")
                
        except Exception as e:
            print(f"Warning: Error injecting image URL fixer: {e}")
            # Continue without script injection if there's an error

    def _modify_nextjs_loader_in_js_files(self, assets, capture_dir):
        """Modify Next.js Image loader function directly in JavaScript files"""
        
        try:
            # Create URL mapping for images
            url_mapping = {}
            for asset in assets.get('images', []):
                if asset.get('local_path') and asset.get('original_url'):
                    original_url = asset['original_url']
                    local_path = asset['local_path']
                    
                    # Handle Next.js image optimization URLs - extract actual URL
                    if '/_next/image?' in original_url:
                        actual_url = self.parse_nextjs_image_url(original_url)
                        if actual_url and not actual_url.startswith('/_next/'):
                            url_mapping[actual_url] = local_path
                    elif not original_url.startswith('/_next/'):
                        url_mapping[original_url] = local_path
            
            if not url_mapping:
                print("No image URL mappings for JS modification")
                return
            
            # Look for JavaScript files that might contain Next.js Image loader
            modified_files = 0
            for asset in assets.get('js', []):
                if asset.get('local_path'):
                    js_file_path = capture_dir / asset['local_path']
                    
                    try:
                        # Read the JavaScript file
                        with open(js_file_path, 'r', encoding='utf-8') as f:
                            js_content = f.read()
                        
                        # Check if this file contains the Next.js Image loader pattern
                        # Look for the specific loader function signature
                        if ('e.path+"?url="+encodeURIComponent(n)+"&w="+r+"&q="' in js_content or
                            'return e.path+"?url="+encodeURIComponent(n)+"&w="+r+"&q="+(i||75)' in js_content):
                            
                            print(f"Found Next.js Image loader in {asset['local_path']}")
                            
                            # Create the replacement loader function
                            url_mapping_js = json.dumps(url_mapping)
                            replacement_function = f'''function n(t){{
                                const imageMapping = {url_mapping_js};
                                const originalSrc = t.src;
                                
                                // Return local path if we have a mapping
                                if (imageMapping[originalSrc]) {{
                                    console.log('🎯 Using local asset:', originalSrc, '->', imageMapping[originalSrc]);
                                    return imageMapping[originalSrc];
                                }}
                                
                                // For any other URLs, return as-is (don't create /_next/image URLs)
                                return originalSrc;
                            }}'''
                            
                            # Replace the original loader function
                            # Pattern: function n(t){let{config:e,src:n,width:r,quality:i}=t;return e.path+"?url="+encodeURIComponent(n)+"&w="+r+"&q="+(i||75)}
                            import re
                            pattern = r'function n\(t\)\{let\{config:e,src:n,width:r,quality:i\}=t;return e\.path\+"\?url="\+encodeURIComponent\(n\)\+"\&w="\+r\+"\&q="\+\(i\|\|75\)\}'
                            
                            if re.search(pattern, js_content):
                                modified_content = re.sub(pattern, replacement_function, js_content)
                                
                                # Write the modified content back
                                with open(js_file_path, 'w', encoding='utf-8') as f:
                                    f.write(modified_content)
                                
                                modified_files += 1
                                print(f"✅ Modified Next.js loader in {asset['local_path']}")
                            else:
                                # Try alternative pattern matching
                                alt_pattern = r'return e\.path\+"\?url="\+encodeURIComponent\(n\)\+"\&w="\+r\+"\&q="\+\(i\|\|75\)'
                                if re.search(alt_pattern, js_content):
                                    # Replace just the return statement
                                    replacement_return = f'''const imageMapping = {url_mapping_js};
                                    const originalSrc = n;
                                    if (imageMapping[originalSrc]) {{
                                        console.log('🎯 Using local asset:', originalSrc, '->', imageMapping[originalSrc]);
                                        return imageMapping[originalSrc];
                                    }}
                                    return originalSrc'''
                                    
                                    modified_content = re.sub(alt_pattern, replacement_return, js_content)
                                    
                                    with open(js_file_path, 'w', encoding='utf-8') as f:
                                        f.write(modified_content)
                                    
                                    modified_files += 1
                                    print(f"✅ Modified Next.js loader (alt pattern) in {asset['local_path']}")
                                
                    except Exception as e:
                        print(f"Warning: Failed to modify JS file {asset['local_path']}: {e}")
            
            if modified_files > 0:
                print(f"Modified Next.js loader in {modified_files} JavaScript files with {len(url_mapping)} URL mappings")
            else:
                print("No JavaScript files with Next.js Image loader found to modify")
                
        except Exception as e:
            print(f"Warning: Error modifying Next.js loader in JS files: {e}")

    def _rewrite_html(self, soup, assets, capture_dir):
        """Rewrite HTML to use local paths"""
        
        # Simple approach: Static rewriting + minimal Next.js image loader override
        # This preserves all JavaScript functionality while fixing only image loading
        
        # Create URL mapping for static rewriting
        url_mapping = self.create_url_mapping(assets)
        
        # Do static image rewriting (this works and doesn't interfere with React)
        self._rewrite_images_statically(soup, assets, url_mapping)
        
        # Add minimal Next.js image loader override (surgical fix)
        self._inject_minimal_nextjs_override(soup, assets)
        
        # Update CSS links
        for asset in assets['css']:
            if asset.get('local_path') and asset.get('element') is not None:
                try:
                    asset['element']['href'] = asset['local_path']
                except Exception as e:
                    print(f"Warning: Failed to update CSS element: {e}")
        
        # Update JS scripts
        for asset in assets['js']:
            if asset.get('local_path') and asset.get('element') is not None:
                try:
                    asset['element']['src'] = asset['local_path']
                except Exception as e:
                    print(f"Warning: Failed to update JS element: {e}")
        
        # Update videos
        for asset in assets['videos']:
            if asset.get('local_path') and asset.get('element') is not None:
                try:
                    attribute = asset.get('attribute', 'src')
                    asset['element'][attribute] = asset['local_path']
                except Exception as e:
                    print(f"Warning: Failed to update video element: {e}")
        
        # Update audio
        for asset in assets['audio']:
            if asset.get('local_path') and asset.get('element') is not None:
                try:
                    attribute = asset.get('attribute', 'src')
                    asset['element'][attribute] = asset['local_path']
                except Exception as e:
                    print(f"Warning: Failed to update audio element: {e}")
        
        # Update fonts
        for asset in assets['fonts']:
            if asset.get('local_path') and asset.get('element') is not None:
                try:
                    if asset.get('is_css_font'):
                        # Update font references in CSS
                        css_content = asset['element'].string
                        if css_content:
                            new_css = re.sub(
                                re.escape(asset['original_url']),
                                asset['local_path'],
                                css_content
                            )
                            asset['element'].string = new_css
                    else:
                        attribute = asset.get('attribute', 'href')
                        asset['element'][attribute] = asset['local_path']
                except Exception as e:
                    print(f"Warning: Failed to update font element: {e}")
        
        # Update documents
        for asset in assets['documents']:
            if asset.get('local_path') and asset.get('element') is not None:
                try:
                    attribute = asset.get('attribute', 'href')
                    asset['element'][attribute] = asset['local_path']
                except Exception as e:
                    print(f"Warning: Failed to update document element: {e}")
        
        print("Simplified approach: Static rewriting + minimal Next.js override completed")
        
        # Save HTML
        html_path = capture_dir / "index.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(str(soup))
    
    def _rebuild_srcset(self, element, assets, url_mapping):
        """Rebuild srcset attribute completely using local paths"""
        current_srcset = element.get('srcset', '')
        if not current_srcset:
            return
        
        # Parse current srcset to preserve descriptors (1x, 2x, width descriptors)
        srcset_items = []
        for item in current_srcset.split(','):
            item = item.strip()
            if not item:
                continue
            
            parts = item.split()
            if not parts:
                continue
            
            original_url = parts[0]
            descriptor = ' '.join(parts[1:]) if len(parts) > 1 else ''
            
            # Find matching local path using URL mapping
            local_path = None
            
            # Try direct match first
            if original_url in url_mapping:
                local_path = url_mapping[original_url]
            else:
                # Try normalized version
                normalized_url = self.normalize_url_for_matching(original_url)
                if normalized_url in url_mapping:
                    local_path = url_mapping[normalized_url]
                else:
                    # Try to find by matching against asset original URLs
                    for asset in assets:
                        if (asset['original_url'] == original_url or 
                            self.normalize_url_for_matching(asset['original_url']) == normalized_url):
                            local_path = asset['local_path']
                            break
            
            if local_path:
                if descriptor:
                    srcset_items.append(f"{local_path} {descriptor}")
                else:
                    srcset_items.append(local_path)
        
        # Set the rebuilt srcset
        if srcset_items:
            element['srcset'] = ', '.join(srcset_items)
    
    def _rebuild_background_style(self, element, assets, url_mapping):
        """Rebuild background-image style property"""
        style = element.get('style', '')
        for asset in assets:
            if asset.get('is_background'):
                # Replace background image URL in style
                new_style = re.sub(
                    r'background-image:\s*url\(["\']?[^"\']+["\']?\)',
                    f'background-image: url("{asset["local_path"]}")',
                    style
                )
                element['style'] = new_style
                break
    
    def _rebuild_css_images(self, element, assets, url_mapping):
        """Rebuild CSS image references"""
        for asset in assets:
            if asset.get('is_css_image'):
                css_content = element.string
                if css_content:
                    # Use both original and normalized URL for replacement
                    original_url = asset['original_url']
                    normalized_url = self.normalize_url_for_matching(original_url)
                    
                    new_css = css_content
                    new_css = re.sub(re.escape(original_url), asset['local_path'], new_css)
                    new_css = re.sub(re.escape(normalized_url), asset['local_path'], new_css)
                    
                    element.string = new_css
            
    def get_all_captures(self):
        """Get list of all captures"""
        captures = []
        if not self.base_dir.exists():
            return captures
            
        for folder in self.base_dir.iterdir():
            if folder.is_dir():
                metadata_path = folder / "metadata.json"
                if metadata_path.exists():
                    try:
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                        captures.append(metadata)
                    except:
                        pass
        
        # Sort by capture time (newest first)
        captures.sort(key=lambda x: x.get('capture_time', ''), reverse=True)
        return captures
        
    def create_zip(self, folder_name):
        """Create ZIP file of capture"""
        capture_dir = self.base_dir / folder_name
        zip_path = capture_dir.with_suffix('.zip')
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in capture_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(capture_dir)
                    zipf.write(file_path, arcname)
                    
        return zip_path


if __name__ == "__main__":
    cloner = WebsiteCloner()
    
    # Test with slideshots.com
    url = "https://www.slideshots.com/"
    print(f"Capturing {url}...")
    try:
        result = cloner.capture_page(url)
        print(f"Capture completed: {result}")
    except Exception as e:
        print(f"Error: {e}")