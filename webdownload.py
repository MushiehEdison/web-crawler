from flask import Flask, render_template_string, request, jsonify, send_file
from flask_cors import CORS
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, urlunparse, urlencode
from concurrent.futures import ThreadPoolExecutor
import hashlib
import time
from collections import deque
import zipfile
from threading import Lock, Thread
import uuid
import xml.etree.ElementTree as ET
import re

app = Flask(__name__)
CORS(app)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ultimate Website Cloner</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gradient-to-br from-gray-900 via-black to-gray-900 min-h-screen text-white">
    <div class="container mx-auto px-4 py-12 max-w-5xl">
        <div class="text-center mb-12">
            <h1 class="text-5xl font-bold mb-4 bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">
                Ultimate Website Cloner
            </h1>
            <p class="text-gray-400 text-lg">ALL pages, smart filtering, with login support</p>
        </div>

        <div class="bg-gray-800 rounded-2xl shadow-2xl border border-gray-700 p-8 mb-8">
            <div id="inputSection">
                <label class="block text-sm font-medium text-gray-300 mb-3">Website URL</label>
                <div class="flex gap-3 mb-4">
                    <input type="url" id="urlInput" placeholder="https://example.com"
                        class="flex-1 bg-gray-900 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-white focus:border-transparent transition"/>
                    <button onclick="startCloning()"
                        class="bg-white text-black px-8 py-3 rounded-lg font-semibold hover:bg-gray-200 transition-all transform hover:scale-105 active:scale-95">
                        Clone
                    </button>
                </div>
                
                <div class="grid md:grid-cols-2 gap-6 mb-4">
                    <div class="bg-gray-900 rounded-lg p-4 border border-gray-700">
                        <h3 class="font-semibold mb-3 text-white">Discovery Methods</h3>
                        <div class="space-y-2">
                            <label class="flex items-center gap-2 cursor-pointer">
                                <input type="checkbox" id="useSitemap" checked class="w-4 h-4">
                                <span class="text-sm text-gray-300">Sitemap.xml (Fast)</span>
                            </label>
                            <label class="flex items-center gap-2 cursor-pointer">
                                <input type="checkbox" id="crawlLinks" checked class="w-4 h-4">
                                <span class="text-sm text-gray-300">Follow Links (Deep)</span>
                            </label>
                            <label class="flex items-center gap-2 cursor-pointer">
                                <input type="checkbox" id="scanJs" class="w-4 h-4">
                                <span class="text-sm text-gray-300">Scan JavaScript</span>
                            </label>
                        </div>
                    </div>
                    
                    <div class="bg-gray-900 rounded-lg p-4 border border-gray-700">
                        <h3 class="font-semibold mb-3 text-white">Filtering Mode</h3>
                        <div class="space-y-2">
                            <label class="flex items-center gap-2 cursor-pointer">
                                <input type="radio" name="filterMode" value="smart" checked class="w-4 h-4">
                                <span class="text-sm text-gray-300">Smart (Skip APIs/login)</span>
                            </label>
                            <label class="flex items-center gap-2 cursor-pointer">
                                <input type="radio" name="filterMode" value="aggressive" class="w-4 h-4">
                                <span class="text-sm text-gray-300">Aggressive (HTML only)</span>
                            </label>
                            <label class="flex items-center gap-2 cursor-pointer">
                                <input type="radio" name="filterMode" value="greedy" class="w-4 h-4">
                                <span class="text-sm text-gray-300">Greedy (Everything)</span>
                            </label>
                        </div>
                    </div>
                </div>

                <div class="bg-gray-900 rounded-lg p-4 border border-gray-700 mb-4">
                    <h3 class="font-semibold mb-3 text-white">Authentication (Optional)</h3>
                    <div class="grid md:grid-cols-2 gap-3">
                        <input type="text" id="authCookie" placeholder="Cookie: session=xyz123..."
                            class="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm placeholder-gray-500"/>
                        <input type="text" id="authToken" placeholder="Authorization: Bearer token..."
                            class="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm placeholder-gray-500"/>
                    </div>
                    <p class="text-xs text-gray-500 mt-2">💡 Use browser DevTools → Network → Copy cookies/headers</p>
                </div>
                
                <div class="flex gap-3">
                    <div class="flex-1">
                        <label class="block text-xs text-gray-400 mb-1">Max Pages (0 = unlimited)</label>
                        <input type="number" id="maxPages" value="100" min="0" max="10000"
                            class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-white"/>
                    </div>
                    <div class="flex-1">
                        <label class="block text-xs text-gray-400 mb-1">Threads</label>
                        <input type="number" id="threads" value="10" min="1" max="50"
                            class="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-white"/>
                    </div>
                </div>
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
                        <div id="statusText" class="text-gray-400 text-sm leading-relaxed font-mono"></div>
                    </div>

                    <div class="grid grid-cols-4 gap-4">
                        <div class="bg-gray-900 rounded-lg p-4 border border-gray-700 text-center">
                            <div class="text-2xl font-bold text-white" id="pagesCount">0</div>
                            <div class="text-xs text-gray-500 mt-1">Pages</div>
                        </div>
                        <div class="bg-gray-900 rounded-lg p-4 border border-gray-700 text-center">
                            <div class="text-2xl font-bold text-white" id="assetsCount">0</div>
                            <div class="text-xs text-gray-500 mt-1">Assets</div>
                        </div>
                        <div class="bg-gray-900 rounded-lg p-4 border border-gray-700 text-center">
                            <div class="text-2xl font-bold text-white" id="queueCount">0</div>
                            <div class="text-xs text-gray-500 mt-1">Queue</div>
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
                    <p class="text-gray-400" id="finalStats"></p>
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

            const filterMode = document.querySelector('input[name="filterMode"]:checked').value;

            const options = {
                url: url,
                use_sitemap: document.getElementById('useSitemap').checked,
                crawl_links: document.getElementById('crawlLinks').checked,
                scan_js: document.getElementById('scanJs').checked,
                filter_mode: filterMode,
                max_pages: parseInt(document.getElementById('maxPages').value) || 0,
                threads: parseInt(document.getElementById('threads').value) || 10,
                auth_cookie: document.getElementById('authCookie').value.trim(),
                auth_token: document.getElementById('authToken').value.trim()
            };

            document.getElementById('inputSection').classList.add('hidden');
            document.getElementById('progressSection').classList.remove('hidden');
            startTime = Date.now();

            fetch('/api/clone', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(options)
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
                        document.getElementById('queueCount').textContent = data.queue || 0;
                        document.getElementById('statusText').textContent = data.status;

                        if (data.complete) {
                            clearInterval(pollInterval);
                            document.getElementById('finalStats').textContent = 
                                `Downloaded ${data.pages} pages and ${data.assets} assets`;
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

jobs = {}
jobs_lock = Lock()

def create_session(auth_cookie=None, auth_token=None):
    """Create session with optional auth"""
    sess = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=40, max_retries=2)
    sess.mount('http://', adapter)
    sess.mount('https://', adapter)
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    
    if auth_cookie:
        headers['Cookie'] = auth_cookie
    if auth_token:
        headers['Authorization'] = auth_token
    
    sess.headers.update(headers)
    return sess

def normalize_url(url):
    """Normalize URL - keep important query params"""
    parsed = urlparse(url)
    
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)
        keep_params = ['page', 'id', 'cat', 'category', 'product', 'post', 'article', 'p', 'q', 'search', 'tag', 's']
        filtered = {k: v for k, v in params.items() if any(keep in k.lower() for keep in keep_params)}
        
        if filtered:
            new_query = urlencode(filtered, doseq=True)
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', new_query, ''))
    
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))

def should_skip_url(url, filter_mode):
    """Determine if URL should be skipped based on filter mode"""
    parsed = urlparse(url)
    path = parsed.path.lower()
    
    # Always skip binary files
    always_skip = ['.pdf', '.zip', '.exe', '.dmg', '.apk', '.mp4', '.avi', '.mov', '.mp3', '.doc', '.docx', '.xls', '.xlsx']
    if any(path.endswith(ext) for ext in always_skip):
        return True
    
    if filter_mode == 'greedy':
        return False
    
    # Aggressive - only .html/.htm or no extension
    if filter_mode == 'aggressive':
        if path and not path.endswith(('/','html', '.htm')):
            has_ext = '.' in path.split('/')[-1]
            if has_ext:
                return True
    
    # Smart - skip server files and APIs
    if filter_mode in ['smart', 'aggressive']:
        server_exts = ['.php', '.asp', '.aspx', '.ashx', '.jsp', '.cgi']
        if any(path.endswith(ext) for ext in server_exts):
            return True
        
        skip_paths = ['/api/', '/ajax/', '/service/', '/handler/', '/login', '/logout', '/signin', '/signout', 
                     '/register', '/signup', '/admin/', '/wp-admin/', '/auth/']
        if any(p in path for p in skip_paths):
            return True
    
    return False

def is_internal_link(url, base_url):
    """Check if URL is internal to the base domain"""
    parsed = urlparse(url)
    base_parsed = urlparse(base_url)
    return parsed.netloc == base_parsed.netloc

def parse_sitemap(sitemap_url, session):
    """Parse XML sitemap"""
    urls = []
    try:
        response = session.get(sitemap_url, timeout=10)
        if response.status_code != 200:
            return urls
        
        root = ET.fromstring(response.content)
        # Sitemap index
        for sitemap in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap'):
            loc = sitemap.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
            if loc is not None and loc.text:
                urls.extend(parse_sitemap(loc.text, session))
        
        # Regular sitemap
        for url in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
            loc = url.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
            if loc is not None and loc.text:
                urls.append(loc.text)
    except:
        pass
    return urls

def discover_sitemaps(base_url, session):
    """Find sitemaps from robots.txt and common paths"""
    sitemaps = []
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    
    # Check robots.txt
    try:
        response = session.get(f"{base}/robots.txt", timeout=5)
        if response.status_code == 200:
            for line in response.text.split('\n'):
                if line.lower().startswith('sitemap:'):
                    sitemaps.append(line.split(':', 1)[1].strip())
    except:
        pass
    
    # Common locations
    for path in ['/sitemap.xml', '/sitemap_index.xml', '/sitemap-index.xml', '/sitemap1.xml']:
        url = base + path
        if url not in sitemaps:
            try:
                if session.head(url, timeout=3).status_code == 200:
                    sitemaps.append(url)
            except:
                pass
    
    return sitemaps

def extract_js_urls(content, base_url):
    """Extract URLs from JavaScript"""
    urls = set()
    patterns = [
        r'["\']([/][a-zA-Z0-9_/\-\.]+)["\']',
        r'href:\s*["\']([^"\']+)["\']',
        r'url:\s*["\']([^"\']+)["\']',
    ]
    
    for pattern in patterns:
        for match in re.findall(pattern, content):
            try:
                full_url = urljoin(base_url, match)
                if is_internal_link(full_url, base_url):
                    urls.add(normalize_url(full_url))
            except:
                pass
    return list(urls)

def generate_filename(url, asset_type):
    """Generate unique filename for asset"""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    ext = os.path.splitext(urlparse(url).path)[1] or '.dat'
    
    if asset_type == 'css' and ext not in ['.css']:
        ext = '.css'
    elif asset_type == 'js' and ext not in ['.js']:
        ext = '.js'
    elif asset_type == 'image' and ext not in ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp']:
        ext = '.jpg'
    
    return f"{url_hash}{ext}"

def download_asset(url, asset_type, output_dir, downloaded_assets, assets_lock, session):
    """Download and save asset"""
    with assets_lock:
        if url in downloaded_assets:
            return downloaded_assets[url]
    
    try:
        response = session.get(url, timeout=15)
        if response.status_code != 200:
            return None
        
        filename = generate_filename(url, asset_type)
        folder = 'images' if asset_type == 'image' else asset_type
        local_path = os.path.join("assets", folder, filename)
        full_path = os.path.join(output_dir, local_path)
        
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'wb') as f:
            f.write(response.content)
        
        with assets_lock:
            downloaded_assets[url] = local_path
        return local_path
    except:
        return None

def update_html_references(soup, base_url, output_dir, downloaded_assets, assets_lock, session):
    """Update all asset references in HTML"""
    # CSS
    for link in soup.find_all('link', href=True):
        if link.get('rel') and 'stylesheet' in link.get('rel'):
            css_url = urljoin(base_url, link['href'])
            local_path = download_asset(css_url, 'css', output_dir, downloaded_assets, assets_lock, session)
            if local_path:
                link['href'] = local_path.replace('\\', '/')
    
    # JS
    for script in soup.find_all('script', src=True):
        js_url = urljoin(base_url, script['src'])
        local_path = download_asset(js_url, 'js', output_dir, downloaded_assets, assets_lock, session)
        if local_path:
            script['src'] = local_path.replace('\\', '/')
    
    # Images
    for img in soup.find_all('img', src=True):
        img_url = urljoin(base_url, img['src'])
        local_path = download_asset(img_url, 'image', output_dir, downloaded_assets, assets_lock, session)
        if local_path:
            img['src'] = local_path.replace('\\', '/')
    
    # Srcset
    for img in soup.find_all('img', attrs={'srcset': True}):
        parts = []
        for src in img['srcset'].split(','):
            tokens = src.strip().split()
            if tokens:
                img_url = urljoin(base_url, tokens[0])
                local_path = download_asset(img_url, 'image', output_dir, downloaded_assets, assets_lock, session)
                if local_path:
                    tokens[0] = local_path.replace('\\', '/')
                parts.append(' '.join(tokens))
        if parts:
            img['srcset'] = ', '.join(parts)
    
    return soup

def extract_links(soup, base_url):
    """Extract all internal links from page"""
    links = []
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        if href and not href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
            full_url = urljoin(base_url, href)
            if is_internal_link(full_url, base_url):
                links.append(normalize_url(full_url))
    return links

def download_page(url, base_url, output_dir, visited, downloaded_assets, visited_lock, 
                 assets_lock, session, crawl_links, scan_js, filter_mode):
    """Download a single page and return discovered links"""
    try:
        response = session.get(url, timeout=20)
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        new_links = []
        
        # Extract links if crawling enabled
        if crawl_links:
            links = extract_links(soup, base_url)
            with visited_lock:
                for link in links:
                    if link not in visited and not should_skip_url(link, filter_mode):
                        new_links.append(link)
        
        # Extract JS URLs if enabled
        if scan_js:
            for script in soup.find_all('script'):
                if script.string:
                    js_urls = extract_js_urls(script.string, base_url)
                    with visited_lock:
                        for link in js_urls:
                            if link not in visited and not should_skip_url(link, filter_mode):
                                new_links.append(link)
        
        # Update asset references
        soup = update_html_references(soup, url, output_dir, downloaded_assets, assets_lock, session)
        
        # Generate filename
        parsed = urlparse(url)
        if parsed.path in ['/', '']:
            filename = 'index.html'
        else:
            filename = parsed.path.strip('/').replace('/', '_')
            if parsed.query:
                query_hash = hashlib.md5(parsed.query.encode()).hexdigest()[:8]
                filename += f"_{query_hash}"
            if not filename.endswith('.html'):
                filename += '.html'
        
        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'w', encoding='utf-8', errors='ignore') as f:
            f.write(str(soup.prettify()))
        
        return new_links
    except:
        return []

def crawl_website(base_url, job_id, use_sitemap, crawl_links, scan_js, filter_mode, 
                 max_pages, threads, auth_cookie, auth_token):
    """Main crawling function"""
    output_dir = f"temp/{job_id}"
    for folder in ['', 'assets/css', 'assets/js', 'assets/images']:
        os.makedirs(os.path.join(output_dir, folder), exist_ok=True)
    
    session = create_session(auth_cookie, auth_token)
    
    visited = set()
    to_visit = deque([normalize_url(base_url)])
    downloaded_assets = {}
    visited_lock = Lock()
    assets_lock = Lock()
    
    def update_status(status, pages, assets, progress, queue=0):
        with jobs_lock:
            jobs[job_id].update({
                'status': status,
                'pages': pages,
                'assets': assets,
                'progress': min(progress, 100),
                'queue': queue
            })
    
    # Discover from sitemaps
    if use_sitemap:
        update_status("🗺️ Discovering sitemaps...", 0, 0, 5)
        sitemaps = discover_sitemaps(base_url, session)
        for sitemap_url in sitemaps:
            update_status(f"📄 Parsing {sitemap_url}...", 0, 0, 10)
            sitemap_urls = parse_sitemap(sitemap_url, session)
            for url in sitemap_urls:
                norm = normalize_url(url)
                if is_internal_link(norm, base_url) and not should_skip_url(norm, filter_mode):
                    to_visit.append(norm)
        
        update_status(f"✅ Found {len(to_visit)} URLs", 0, 0, 15, len(to_visit))
        time.sleep(0.5)
    
    page_count = 0
    max_pages = max_pages if max_pages > 0 else float('inf')
    
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {}
        
        while (to_visit or futures) and page_count < max_pages:
            # Submit new tasks
            while to_visit and len(futures) < threads and page_count < max_pages:
                url = to_visit.popleft()
                
                with visited_lock:
                    if url in visited:
                        continue
                    visited.add(url)
                
                page_count += 1
                progress = min(15 + int((page_count / max_pages) * 80), 95)
                
                update_status(f"⬇️ Downloading {page_count}/{int(max_pages) if max_pages != float('inf') else '∞'}...", 
                            len(visited), len(downloaded_assets), progress, len(to_visit))
                
                future = executor.submit(download_page, url, base_url, output_dir, visited, 
                                       downloaded_assets, visited_lock, assets_lock, session,
                                       crawl_links, scan_js, filter_mode)
                futures[future] = url
                time.sleep(0.01)
            
            # Process completed
            done = [f for f in futures if f.done()]
            for future in done:
                futures.pop(future)
                try:
                    new_links = future.result()
                    for link in new_links:
                        with visited_lock:
                            if link not in visited:
                                to_visit.append(link)
                except:
                    pass
            
            if not done and futures:
                time.sleep(0.1)
    
    # Create ZIP
    update_status("📦 Creating ZIP...", len(visited), len(downloaded_assets), 95)
    zip_path = f"temp/{job_id}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, output_dir)
                zipf.write(file_path, arcname)
    
    update_status("✅ Complete!", len(visited), len(downloaded_assets), 100)
    with jobs_lock:
        jobs[job_id]['complete'] = True
        jobs[job_id]['zip_path'] = zip_path

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/clone', methods=['POST'])
def clone_website_api():
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
            'queue': 0,
            'complete': False
        }
    
    def run():
        crawl_website(
            url, job_id,
            use_sitemap=data.get('use_sitemap', True),
            crawl_links=data.get('crawl_links', True),
            scan_js=data.get('scan_js', False),
            filter_mode=data.get('filter_mode', 'smart'),
            max_pages=data.get('max_pages', 100),
            threads=data.get('threads', 10),
            auth_cookie=data.get('auth_cookie', ''),
            auth_token=data.get('auth_token', '')
        )
    
    Thread(target=run, daemon=True).start()
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
    print("\n" + "="*70)
    print("🚀 ULTIMATE WEBSITE CLONER")
    print("="*70)
    print("📍 URL: http://localhost:5000")
    print("="*70)
    print("\n🔥 Features:")
    print("  ✅ Sitemap discovery (finds ALL listed pages)")
    print("  ✅ Deep link crawling (follows every link)")
    print("  ✅ JavaScript URL extraction")
    print("  ✅ 3 Filter modes: Smart / Aggressive / Greedy")
    print("  ✅ Authentication support (cookies/tokens)")
    print("  ✅ Configurable threads & page limits")
    print("\n💡 For login-protected sites:")
    print("  1. Login in your browser")
    print("  2. Open DevTools → Network tab")
    print("  3. Copy Cookie header from any request")
    print("  4. Paste into 'Authentication' field")
    print("="*70 + "\n")
    
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)