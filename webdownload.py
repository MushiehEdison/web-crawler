from flask import Flask, render_template_string, request, jsonify, send_file
from flask_cors import CORS
import os
import sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import hashlib
import time
from collections import deque
import shutil
import zipfile
from threading import Lock
import uuid

app = Flask(__name__)
CORS(app)

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Website Cloner</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gradient-to-br from-gray-900 via-black to-gray-900 min-h-screen text-white">
    <div class="container mx-auto px-4 py-12 max-w-4xl">
        <div class="text-center mb-12">
            <h1 class="text-5xl font-bold mb-4 bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">
                Website Cloner
            </h1>
            <p class="text-gray-400 text-lg">Clone any website with full assets and structure preserved</p>
        </div>

        <div class="bg-gray-800 rounded-2xl shadow-2xl border border-gray-700 p-8 mb-8">
            <div id="inputSection">
                <label class="block text-sm font-medium text-gray-300 mb-3">Website URL</label>
                <div class="flex gap-3">
                    <input type="url" id="urlInput" placeholder="https://example.com"
                        class="flex-1 bg-gray-900 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-white focus:border-transparent transition"/>
                    <button onclick="startCloning()"
                        class="bg-white text-black px-8 py-3 rounded-lg font-semibold hover:bg-gray-200 transition-all transform hover:scale-105 active:scale-95">
                        Clone
                    </button>
                </div>
                <p class="text-gray-500 text-sm mt-3">Enter the full URL of the website you want to clone</p>
            </div>

            <div id="progressSection" class="hidden">
                <div class="space-y-6">
                    <div>
                        <div class="flex justify-between text-sm text-gray-400 mb-2">
                            <span>Progress</span>
                            <span id="progressPercent">0%</span>
                        </div>
                        <div class="bg-gray-900 rounded-full h-3 overflow-hidden">
                            <div id="progressBar" class="bg-gradient-to-r from-white to-gray-400 h-full transition-all duration-500" style="width: 0%"></div>
                        </div>
                    </div>

                    <div class="bg-gray-900 rounded-lg p-6 border border-gray-700">
                        <div class="flex items-center gap-3 mb-4">
                            <div class="animate-spin">
                                <svg class="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24">
                                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                            </div>
                            <span class="text-lg font-semibold">Processing...</span>
                        </div>
                        <div id="statusText" class="text-gray-400 text-sm leading-relaxed"></div>
                    </div>

                    <div class="grid grid-cols-3 gap-4">
                        <div class="bg-gray-900 rounded-lg p-4 border border-gray-700 text-center">
                            <div class="text-2xl font-bold text-white" id="pagesCount">0</div>
                            <div class="text-xs text-gray-500 mt-1">Pages</div>
                        </div>
                        <div class="bg-gray-900 rounded-lg p-4 border border-gray-700 text-center">
                            <div class="text-2xl font-bold text-white" id="assetsCount">0</div>
                            <div class="text-xs text-gray-500 mt-1">Assets</div>
                        </div>
                        <div class="bg-gray-900 rounded-lg p-4 border border-gray-700 text-center">
                            <div class="text-2xl font-bold text-white" id="timeElapsed">0s</div>
                            <div class="text-xs text-gray-500 mt-1">Elapsed</div>
                        </div>
                    </div>
                </div>
            </div>

            <div id="completeSection" class="hidden text-center">
                <div class="mb-6">
                    <svg class="w-20 h-20 mx-auto text-white mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <h2 class="text-2xl font-bold mb-2">Cloning Complete!</h2>
                    <p class="text-gray-400">Your website has been successfully cloned</p>
                </div>
                <button onclick="downloadZip()"
                    class="bg-white text-black px-8 py-4 rounded-lg font-semibold hover:bg-gray-200 transition-all transform hover:scale-105 active:scale-95 inline-flex items-center gap-2">
                    <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    Download ZIP
                </button>
                <button onclick="resetApp()"
                    class="ml-3 bg-gray-700 text-white px-6 py-4 rounded-lg font-semibold hover:bg-gray-600 transition-all">
                    Clone Another
                </button>
            </div>
        </div>

        <div class="grid md:grid-cols-3 gap-6 text-center">
            <div class="bg-gray-800 rounded-xl p-6 border border-gray-700">
                <div class="text-3xl mb-2">⚡</div>
                <h3 class="font-semibold mb-1">Fast Cloning</h3>
                <p class="text-gray-400 text-sm">Multi-threaded downloads</p>
            </div>
            <div class="bg-gray-800 rounded-xl p-6 border border-gray-700">
                <div class="text-3xl mb-2">📁</div>
                <h3 class="font-semibold mb-1">Structure Preserved</h3>
                <p class="text-gray-400 text-sm">Original paths maintained</p>
            </div>
            <div class="bg-gray-800 rounded-xl p-6 border border-gray-700">
                <div class="text-3xl mb-2">🎨</div>
                <h3 class="font-semibold mb-1">Full Assets</h3>
                <p class="text-gray-400 text-sm">CSS, JS, and images included</p>
            </div>
        </div>
    </div>

    <script>
        let jobId = null;
        let pollInterval = null;
        let startTime;

        function startCloning() {
            const url = document.getElementById('urlInput').value.trim();
            if (!url || (!url.startsWith('http://') && !url.startsWith('https://'))) {
                alert('Please enter a valid URL starting with http:// or https://');
                return;
            }

            document.getElementById('inputSection').classList.add('hidden');
            document.getElementById('progressSection').classList.remove('hidden');
            startTime = Date.now();

            fetch('/api/clone', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url: url})
            })
            .then(res => res.json())
            .then(data => {
                if (data.job_id) {
                    jobId = data.job_id;
                    startPolling();
                } else {
                    alert('Error: ' + (data.error || 'Unknown error'));
                    resetApp();
                }
            })
            .catch(err => {
                alert('Error starting clone: ' + err);
                resetApp();
            });
        }

        function startPolling() {
            pollInterval = setInterval(() => {
                fetch('/api/status/' + jobId)
                    .then(res => res.json())
                    .then(data => {
                        const elapsed = Math.floor((Date.now() - startTime) / 1000);
                        document.getElementById('timeElapsed').textContent = elapsed + 's';
                        document.getElementById('progressPercent').textContent = data.progress + '%';
                        document.getElementById('progressBar').style.width = data.progress + '%';
                        document.getElementById('pagesCount').textContent = data.pages;
                        document.getElementById('assetsCount').textContent = data.assets;
                        document.getElementById('statusText').textContent = data.status;

                        if (data.complete) {
                            clearInterval(pollInterval);
                            finishCloning();
                        }
                    });
            }, 500);
        }

        function finishCloning() {
            document.getElementById('progressSection').classList.add('hidden');
            document.getElementById('completeSection').classList.remove('hidden');
        }

        function downloadZip() {
            window.location.href = '/api/download/' + jobId;
        }

        function resetApp() {
            if (pollInterval) clearInterval(pollInterval);
            document.getElementById('completeSection').classList.add('hidden');
            document.getElementById('progressSection').classList.add('hidden');
            document.getElementById('inputSection').classList.remove('hidden');
            document.getElementById('urlInput').value = '';
            jobId = null;
        }
    </script>
</body>
</html>
"""

# Global storage
jobs = {}
jobs_lock = Lock()

# Setup session
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=10,
    pool_maxsize=20,
    max_retries=3
)
session.mount('http://', adapter)
session.mount('https://', adapter)
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

def normalize_url(url):
    clean = url.split('#')[0]
    if '?' in clean:
        clean = clean.split('?')[0]
    if clean and not clean.endswith('.html') and not clean.endswith('/'):
        clean += '/'
    return clean.rstrip('/')

def is_internal_link(url, base_url):
    parsed = urlparse(url)
    base_parsed = urlparse(base_url)
    if parsed.netloc != base_parsed.netloc:
        return False
    skip_extensions = ['.pdf', '.jpg', '.png', '.gif', '.zip', '.exe', '.dmg']
    if any(url.lower().endswith(ext) for ext in skip_extensions):
        return False
    return True

def get_file_extension(url):
    path = urlparse(url).path
    ext = os.path.splitext(path)[1]
    return ext if ext else '.dat'

def generate_filename(url, asset_type):
    url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
    ext = get_file_extension(url)
    if asset_type == 'css' and ext not in ['.css']:
        ext = '.css'
    elif asset_type == 'js' and ext not in ['.js']:
        ext = '.js'
    elif asset_type == 'image':
        if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp']:
            ext = '.jpg'
    return f"{url_hash}{ext}"

def download_asset(url, asset_type, output_dir, downloaded_assets, assets_lock):
    with assets_lock:
        if url in downloaded_assets:
            return downloaded_assets[url]
    try:
        response = session.get(url, timeout=20)
        if response.status_code != 200:
            return None
        filename = generate_filename(url, asset_type)
        local_path = os.path.join("assets", asset_type if asset_type != 'image' else 'images', filename)
        full_path = os.path.join(output_dir, local_path)
        with open(full_path, 'wb') as f:
            f.write(response.content)
        with assets_lock:
            downloaded_assets[url] = local_path
        return local_path
    except:
        return None

def update_html_references(soup, base_url, output_dir, downloaded_assets, assets_lock):
    for link in soup.find_all('link', href=True):
        if link.get('rel') and 'stylesheet' in link.get('rel'):
            css_url = urljoin(base_url, link['href'])
            local_path = download_asset(css_url, 'css', output_dir, downloaded_assets, assets_lock)
            if local_path:
                link['href'] = local_path.replace('\\', '/')
    
    for script in soup.find_all('script', src=True):
        js_url = urljoin(base_url, script['src'])
        local_path = download_asset(js_url, 'js', output_dir, downloaded_assets, assets_lock)
        if local_path:
            script['src'] = local_path.replace('\\', '/')
    
    for img in soup.find_all('img', src=True):
        img_url = urljoin(base_url, img['src'])
        local_path = download_asset(img_url, 'image', output_dir, downloaded_assets, assets_lock)
        if local_path:
            img['src'] = local_path.replace('\\', '/')
    
    for img in soup.find_all('img', attrs={'srcset': True}):
        srcset_parts = []
        for src in img['srcset'].split(','):
            parts = src.strip().split()
            if parts:
                img_url = urljoin(base_url, parts[0])
                local_path = download_asset(img_url, 'image', output_dir, downloaded_assets, assets_lock)
                if local_path:
                    parts[0] = local_path.replace('\\', '/')
                srcset_parts.append(' '.join(parts))
        if srcset_parts:
            img['srcset'] = ', '.join(srcset_parts)
    
    import re
    for elem in soup.find_all(style=True):
        style = elem['style']
        urls = re.findall(r'url\(["\']?([^"\')]+)["\']?\)', style)
        for bg_url in urls:
            full_url = urljoin(base_url, bg_url)
            local_path = download_asset(full_url, 'image', output_dir, downloaded_assets, assets_lock)
            if local_path:
                style = style.replace(bg_url, local_path.replace('\\', '/'))
        elem['style'] = style
    return soup

def extract_links_from_page(soup, base_url, main_base_url):
    links = []
    for a in soup.find_all('a', href=True):
        href = a.get('href', '').strip()
        if not href or href.startswith('javascript:') or href.startswith('mailto:'):
            continue
        full_url = urljoin(base_url, href)
        if is_internal_link(full_url, main_base_url):
            normalized = normalize_url(full_url)
            if normalized:
                links.append(normalized)
    return links

def download_page(url, base_url, output_dir, visited_pages, downloaded_assets, visited_lock, assets_lock, job_id):
    try:
        response = session.get(url, timeout=20)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        links = extract_links_from_page(soup, url, base_url)
        new_links = []
        
        with visited_lock:
            for link in links:
                if link not in visited_pages:
                    new_links.append(link)
        
        soup = update_html_references(soup, url, output_dir, downloaded_assets, assets_lock)
        
        parsed = urlparse(url)
        path = parsed.path
        if path == '/' or path == '':
            filename = 'index.html'
        else:
            filename = path.strip('/').replace('/', '_') + '.html'
            if not filename.endswith('.html'):
                filename += '.html'
        
        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(str(soup.prettify()))
        
        return new_links
    except Exception as e:
        return None

def crawl_website(base_url, job_id, max_pages=100):
    output_dir = f"temp/{job_id}"
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "assets", "css"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "assets", "js"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "assets", "images"), exist_ok=True)
    
    visited_pages = set()
    to_visit = deque([base_url])
    downloaded_assets = {}
    visited_lock = Lock()
    assets_lock = Lock()
    
    def update_status(status, pages, assets, progress):
        with jobs_lock:
            jobs[job_id].update({
                'status': status,
                'pages': pages,
                'assets': assets,
                'progress': min(progress, 100)
            })
    
    update_status("Discovering pages...", 0, 0, 5)
    page_count = 0
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {}
        
        while (to_visit or futures) and page_count < max_pages:
            while to_visit and len(futures) < 5 and page_count < max_pages:
                url = to_visit.popleft()
                with visited_lock:
                    if url in visited_pages:
                        continue
                    visited_pages.add(url)
                
                page_count += 1
                progress = int((page_count / max_pages) * 80) + 10
                update_status(f"Crawling {page_count}/{max_pages} pages...", 
                            len(visited_pages), len(downloaded_assets), progress)
                
                future = executor.submit(download_page, url, base_url, output_dir, 
                                       visited_pages, downloaded_assets, visited_lock, assets_lock, job_id)
                futures[future] = url
                time.sleep(0.05)
            
            for future in list(futures.keys()):
                if future.done():
                    futures.pop(future)
                    try:
                        new_links = future.result()
                        if new_links:
                            for link in new_links:
                                with visited_lock:
                                    if link not in visited_pages:
                                        to_visit.append(link)
                    except:
                        pass
    
    update_status("Creating ZIP archive...", len(visited_pages), len(downloaded_assets), 90)
    zip_path = f"temp/{job_id}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, output_dir)
                zipf.write(file_path, arcname)
    
    update_status("Complete!", len(visited_pages), len(downloaded_assets), 100)
    with jobs_lock:
        jobs[job_id]['complete'] = True
        jobs[job_id]['zip_path'] = zip_path

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/clone', methods=['POST'])
def clone_website():
    data = request.get_json()
    url = data.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    
    job_id = str(uuid.uuid4())
    with jobs_lock:
        jobs[job_id] = {
            'status': 'Starting...',
            'progress': 0,
            'pages': 0,
            'assets': 0,
            'complete': False
        }
    
    def run_crawler():
        crawl_website(url, job_id)
    
    from threading import Thread
    Thread(target=run_crawler, daemon=True).start()
    return jsonify({'job_id': job_id})

@app.route('/api/status/<job_id>')
def get_status(job_id):
    with jobs_lock:
        if job_id not in jobs:
            return jsonify({'error': 'Job not found'}), 404
        return jsonify(jobs[job_id])

@app.route('/api/download/<job_id>')
def download_zip(job_id):
    with jobs_lock:
        if job_id not in jobs or not jobs[job_id].get('complete'):
            return jsonify({'error': 'Job not complete'}), 404
        zip_path = jobs[job_id].get('zip_path')
    
    if not zip_path or not os.path.exists(zip_path):
        return jsonify({'error': 'File not found'}), 404
    
    return send_file(zip_path, as_attachment=True, download_name='website_clone.zip')

if __name__ == '__main__':
    os.makedirs('temp', exist_ok=True)
    print("\n" + "="*50)
    print("🚀 Website Cloner Server Starting...")
    print("="*50)
    print("📍 Open your browser to: http://localhost:5000")
    print("="*50 + "\n")
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=False, host='0.0.0.0', port=port)
