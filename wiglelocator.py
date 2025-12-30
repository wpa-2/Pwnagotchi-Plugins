import requests
import os
import logging
import json
import threading
import time
import re
import secrets
from datetime import datetime
from pwnagotchi.plugins import Plugin
from flask import send_from_directory, Response, request

class WigleLocator(Plugin):
    __author__ = 'WPA2'
    __version__ = '2.2.1'
    __license__ = 'GPL3'
    __description__ = 'Async WiGLE locator with proper 429 handling and rate limiting'

    def __init__(self):
        self.api_key = None
        self.data_dir = '/home/pi/wigle_locator_data'
        self.cache_file = os.path.join(self.data_dir, 'wigle_cache.json')
        self.queue_file = os.path.join(self.data_dir, 'pending_queue.json')
        self.status_file = os.path.join(self.data_dir, 'api_status.json')
        self.cache = {}
        self.pending_queue = []
        self.lock = threading.Lock()
        self._processing = False
        self.last_queue_process_time = 0
        self.last_api_call_time = 0
        self._api_limit_hit = False
        self._api_limit_reset_time = 0
        self.csrf_token = secrets.token_urlsafe(32)
        self.max_cache_size = 10000
        self.min_request_interval = 2  # Minimum seconds between API calls
        self.daily_request_count = 0
        self.daily_request_limit = 1000  # Conservative limit
        self.request_count_reset_time = 0

    @property
    def processing(self):
        with self.lock:
            return self._processing
    
    @processing.setter
    def processing(self, value):
        with self.lock:
            self._processing = value

    @property
    def api_limit_hit(self):
        with self.lock:
            return self._api_limit_hit
    
    @api_limit_hit.setter
    def api_limit_hit(self, value):
        with self.lock:
            self._api_limit_hit = value

    @property
    def api_limit_reset_time(self):
        with self.lock:
            return self._api_limit_reset_time
    
    @api_limit_reset_time.setter
    def api_limit_reset_time(self, value):
        with self.lock:
            self._api_limit_reset_time = value

    def on_loaded(self):
        if not os.path.exists(self.data_dir):
            try:
                os.makedirs(self.data_dir, mode=0o755)
                os.chown(self.data_dir, 1000, 1000) 
            except Exception as e:
                logging.warning(f"[WigleLocator] Could not set folder permissions: {e}")
            
        self._load_data()
        
        # Check cooldown on load
        if self.api_limit_hit and time.time() < self.api_limit_reset_time:
            remaining = int((self.api_limit_reset_time - time.time()) / 60)
            logging.warning(f"[WigleLocator] ⚠️ API is in cooldown for {remaining} more minutes. Pausing all requests.")
        else:
            # Reset if cooldown expired while plugin was off
            if self.api_limit_hit:
                self.api_limit_hit = False
                self.api_limit_reset_time = 0
                self._save_status()

        # Clean old cache entries if too large
        self._trim_cache()

        # Regenerate map on load
        self._generate_outputs()
        logging.info(f"[WigleLocator] Plugin loaded. Cache: {len(self.cache)}, Queue: {len(self.pending_queue)}, Cooldown: {self.api_limit_hit}")

    def on_config_changed(self, config):
        if 'main' in config and 'plugins' in config['main'] and 'wiglelocator' in config['main']['plugins']:
            api_key = config['main']['plugins']['wiglelocator'].get('api_key')
            if api_key and self._validate_api_key(api_key):
                self.api_key = api_key
            elif api_key:
                logging.error('[WigleLocator] Invalid API key format in config.toml!')
        
        if not self.api_key:
            logging.error('[WigleLocator] No valid API key set in config.toml!')

    def on_webhook(self, path, request_obj):
        try:
            if not path:
                path = ''
            path = path.strip('/')

            # Serve Map (Root)
            if path == '' or path == 'index.html':
                return send_from_directory(self.data_dir, 'wigle_map.html')
            
            # Serve Data Files
            elif path == 'kml':
                return send_from_directory(self.data_dir, 'wigle_locations.kml', as_attachment=True)
            elif path == 'csv':
                return send_from_directory(self.data_dir, 'locations.csv', as_attachment=True)
            elif path == 'json':
                return send_from_directory(self.data_dir, 'wigle_cache.json', as_attachment=True)
            
            # Flush Command with CSRF protection
            elif path == 'flush':
                provided_token = request_obj.args.get('token', '')
                if not secrets.compare_digest(provided_token, self.csrf_token):
                    logging.warning("[WigleLocator] Invalid CSRF token on flush attempt")
                    return "Invalid security token", 403
                
                with self.lock:
                    count = len(self.pending_queue)
                    self.pending_queue = []
                    self._save_data()
                
                # Reset 429 status
                self.api_limit_hit = False
                self.api_limit_reset_time = 0
                self.daily_request_count = 0
                self._save_status()
                
                logging.info(f"[WigleLocator] ✅ Queue flushed by user. Removed {count} items. Rate limits reset.")
                return f"Queue flushed! Removed {count} items. Rate limits reset.", 200
            
            # Get CSRF token endpoint
            elif path == 'token':
                return json.dumps({'token': self.csrf_token}), 200, {'Content-Type': 'application/json'}
            
            # Status endpoint for debugging
            elif path == 'status':
                status_info = {
                    'cache_size': len(self.cache),
                    'queue_size': len(self.pending_queue),
                    'api_limit_hit': self.api_limit_hit,
                    'cooldown_minutes_remaining': max(0, int((self.api_limit_reset_time - time.time()) / 60)) if self.api_limit_hit else 0,
                    'daily_requests': self.daily_request_count,
                    'processing': self.processing
                }
                return json.dumps(status_info), 200, {'Content-Type': 'application/json'}
                
            return "File not found", 404
        except Exception as e:
            logging.error(f"[WigleLocator] Webhook error: {e}")
            return f"Error: {e}", 500

    def on_handshake(self, agent, filename, access_point, client_station):
        if not self.api_key:
            return
        
        # CRITICAL: Check if we're in cooldown BEFORE doing anything
        if self.api_limit_hit:
            if time.time() < self.api_limit_reset_time:
                # Still in cooldown, do nothing
                return
            else:
                # Cooldown expired, reset
                self.api_limit_hit = False
                self.api_limit_reset_time = 0
                self._save_status()
                logging.info("[WigleLocator] ✅ Cooldown expired. Resuming operations.")

        bssid = access_point["mac"]
        essid = access_point["hostname"]
        
        # Validate BSSID format
        if not self._validate_bssid(bssid):
            logging.debug(f"[WigleLocator] Invalid BSSID format: {bssid}")
            return
        
        # Check if already cached
        with self.lock:
            if bssid in self.cache:
                return
        
        # Add to queue instead of immediate processing
        self._add_to_queue(bssid, essid)

    def on_internet_available(self, agent):
        now = time.time()
        
        # CRITICAL: Strict cooldown check
        if self.api_limit_hit:
            if now < self.api_limit_reset_time:
                # Log occasionally but not every time
                if int(now) % 300 == 0:  # Every 5 minutes
                    remaining = int((self.api_limit_reset_time - now) / 60)
                    logging.info(f"[WigleLocator] ⏳ Still in cooldown. {remaining} minutes remaining.")
                return
            else:
                # Cooldown expired
                self.api_limit_hit = False
                self.api_limit_reset_time = 0
                self.daily_request_count = 0
                self._save_status()
                logging.info("[WigleLocator] ✅ Cooldown expired. Resuming operations.")

        # Check daily limit reset (midnight Pacific = 8am UTC)
        if self.request_count_reset_time > 0 and now > self.request_count_reset_time:
            self.daily_request_count = 0
            self._save_status()
            logging.info("[WigleLocator] Daily request counter reset.")

        # Don't start new processing if already processing or approaching daily limit
        if self.pending_queue and not self.processing:
            if self.daily_request_count >= self.daily_request_limit:
                logging.warning(f"[WigleLocator] ⚠️ Daily request limit ({self.daily_request_limit}) reached. Pausing until reset.")
                return
                
            if now - self.last_queue_process_time > 600:  # 10 minutes between batches (was 5)
                logging.info(f"[WigleLocator] 🔄 Processing {len(self.pending_queue)} queued items... (Daily: {self.daily_request_count}/{self.daily_request_limit})")
                threading.Thread(target=self._process_queue, args=(agent,), daemon=True).start()

    def _process_queue(self, agent):
        self.processing = True
        self.last_queue_process_time = time.time()
        
        with self.lock:
            queue_copy = list(self.pending_queue)
        
        processed = 0
        max_batch_size = 20  # Process max 20 items per batch to be conservative
        
        for item in queue_copy[:max_batch_size]:
            # CRITICAL: Check cooldown before EVERY request
            if self.api_limit_hit:
                logging.warning("[WigleLocator] ⚠️ 429 detected during processing. Stopping immediately.")
                break

            # Check daily limit
            if self.daily_request_count >= self.daily_request_limit:
                logging.warning(f"[WigleLocator] ⚠️ Daily limit reached during processing. Stopping.")
                break

            bssid = item['bssid']
            essid = item['essid']
            retries = item.get('retries', 0)
            
            # Check cache again
            with self.lock:
                if bssid in self.cache:
                    self._remove_from_queue(bssid)
                    continue

            # Rate limiting: enforce minimum time between requests
            time_since_last = time.time() - self.last_api_call_time
            if time_since_last < self.min_request_interval:
                time.sleep(self.min_request_interval - time_since_last)

            result = self._fetch_wigle_location(bssid)
            processed += 1
            
            if isinstance(result, dict):
                self._handle_success(agent, bssid, essid, result)
                self._remove_from_queue(bssid)
                time.sleep(self.min_request_interval)  # Be polite
            elif result == 'LIMIT_EXCEEDED':
                # 429 hit - stop everything immediately
                logging.error("[WigleLocator] 🛑 RATE LIMIT HIT. All processing stopped.")
                break 
            elif result is False:
                # Permanent failure (404, auth error, etc)
                self._cache_failure(bssid, essid)
                self._remove_from_queue(bssid)
                time.sleep(1)
            else:
                # Temporary failure (timeout, network error)
                retries += 1
                if retries >= 5:
                    logging.warning(f"[WigleLocator] Max retries for {essid} ({bssid}). Dropping.")
                    self._remove_from_queue(bssid)
                else:
                    with self.lock:
                        for q_item in self.pending_queue:
                            if q_item['bssid'] == bssid:
                                q_item['retries'] = retries
                                break
                        self._save_data()
                    time.sleep(min(2 ** retries, 30))  # Exponential backoff
        
        self.processing = False
        logging.info(f"[WigleLocator] Batch complete. Processed {processed} items. Queue remaining: {len(self.pending_queue)}")

    def _handle_success(self, agent, bssid, essid, location):
        logging.info(f"[WigleLocator] ✅ Located {essid}: {location['lat']:.6f}, {location['lon']:.6f}")
        
        if agent:
            try:
                view = agent.view()
                view.set("status", f"Loc: {location['lat']:.4f},{location['lon']:.4f}")
            except Exception:
                pass

        with self.lock:
            self.cache[bssid] = {
                'essid': essid,
                'lat': location['lat'],
                'lon': location['lon'],
                'timestamp': datetime.now().isoformat()
            }
            self._save_data()
            
        self._generate_outputs()

    def _cache_failure(self, bssid, essid):
        with self.lock:
            self.cache[bssid] = {
                'essid': essid,
                'lat': None,
                'lon': None,
                'timestamp': datetime.now().isoformat()
            }
            self._save_data()

    def _fetch_wigle_location(self, bssid):
        # CRITICAL: Final check before making request
        if self.api_limit_hit:
            return 'LIMIT_EXCEEDED'

        headers = {'Authorization': 'Basic ' + self.api_key}
        params = {'netid': bssid}

        try:
            self.last_api_call_time = time.time()
            self.daily_request_count += 1
            
            response = requests.get(
                'https://api.wigle.net/api/v2/network/detail', 
                headers=headers, 
                params=params, 
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('results'):
                    result = data['results'][0]
                    lat = result.get('trilat')
                    lon = result.get('trilong')
                    if lat is not None and lon is not None:
                        return {'lat': lat, 'lon': lon}
                return False
            elif response.status_code == 404:
                return False
            elif response.status_code == 429:
                logging.error("[WigleLocator] 🚨 429 TOO MANY REQUESTS - PAUSING FOR 24 HOURS")
                logging.error("[WigleLocator] This means you've exceeded WiGLE's daily API limit.")
                logging.error("[WigleLocator] The plugin will automatically resume tomorrow at midnight Pacific time.")
                
                # Set 24 hour cooldown (until next midnight Pacific = 8am UTC next day)
                self.api_limit_hit = True
                self.api_limit_reset_time = time.time() + (3600 * 24)
                self._save_status()
                return 'LIMIT_EXCEEDED'
            elif response.status_code == 401:
                logging.error("[WigleLocator] ❌ WiGLE Auth failed. Check your API key in config.toml")
                return False
            else:
                logging.warning(f"[WigleLocator] Unexpected HTTP {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            logging.debug(f"[WigleLocator] Timeout for {bssid}")
            return None
        except Exception as e:
            logging.debug(f"[WigleLocator] Request error: {e}")
            return None

    def _add_to_queue(self, bssid, essid):
        with self.lock:
            # Don't add if already queued or cached
            if bssid in self.cache:
                return
            if any(x['bssid'] == bssid for x in self.pending_queue):
                return
                
            self.pending_queue.append({
                'bssid': bssid, 
                'essid': essid,
                'retries': 0,
                'added': datetime.now().isoformat()
            })
            self._save_data()

    def _remove_from_queue(self, bssid):
        with self.lock:
            self.pending_queue = [x for x in self.pending_queue if x['bssid'] != bssid]
            self._save_data()

    def _load_data(self):
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    self.cache = json.load(f)
            if os.path.exists(self.queue_file):
                with open(self.queue_file, 'r') as f:
                    self.pending_queue = json.load(f)
            if os.path.exists(self.status_file):
                with open(self.status_file, 'r') as f:
                    status = json.load(f)
                    self._api_limit_hit = status.get('limit_hit', False)
                    self._api_limit_reset_time = status.get('reset_time', 0)
                    self.daily_request_count = status.get('daily_count', 0)
                    self.request_count_reset_time = status.get('count_reset_time', 0)
        except Exception as e:
            logging.error(f"[WigleLocator] Error loading data: {e}")

    def _save_data(self):
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
            with open(self.queue_file, 'w') as f:
                json.dump(self.pending_queue, f, indent=2)
            
            try:
                os.chmod(self.cache_file, 0o644)
                os.chmod(self.queue_file, 0o644)
            except (OSError, PermissionError):
                pass
        except Exception as e:
            logging.error(f"[WigleLocator] Error saving data: {e}")

    def _save_status(self):
        try:
            with open(self.status_file, 'w') as f:
                json.dump({
                    'limit_hit': self.api_limit_hit,
                    'reset_time': self.api_limit_reset_time,
                    'daily_count': self.daily_request_count,
                    'count_reset_time': self.request_count_reset_time
                }, f, indent=2)
            try:
                os.chmod(self.status_file, 0o644)
            except (OSError, PermissionError):
                pass
        except Exception as e:
            logging.error(f"[WigleLocator] Error saving status: {e}")

    def _trim_cache(self):
        """Remove oldest entries if cache exceeds max size"""
        with self.lock:
            if len(self.cache) > self.max_cache_size:
                sorted_items = sorted(
                    self.cache.items(),
                    key=lambda x: x[1].get('timestamp', ''),
                    reverse=True
                )
                self.cache = dict(sorted_items[:self.max_cache_size])
                self._save_data()
                logging.info(f"[WigleLocator] Trimmed cache to {self.max_cache_size} entries")

    def _validate_bssid(self, bssid):
        """Validate BSSID format (MAC address)"""
        pattern = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
        return bool(pattern.match(bssid))

    def _validate_api_key(self, api_key):
        """Basic API key validation"""
        return isinstance(api_key, str) and len(api_key) > 10

    def _sanitize_html(self, text):
        """Sanitize text for HTML output"""
        if not isinstance(text, str):
            return str(text)
        return (text.replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace('"', '&quot;')
                   .replace("'", '&#x27;'))

    def _generate_outputs(self):
        try:
            self._generate_kml()
            self._generate_html_map()
            self._generate_csv()
        except Exception as e:
            logging.error(f"[WigleLocator] Map generation error: {e}")

    def _generate_csv(self):
        csv_file = os.path.join(self.data_dir, 'locations.csv')
        try:
            with open(csv_file, 'w') as f:
                f.write("BSSID,ESSID,Latitude,Longitude,Timestamp\n")
                for bssid, data in self.cache.items():
                    if data.get('lat') is not None:
                        essid = data['essid'].replace('"', '""')
                        f.write(f'"{bssid}","{essid}",{data["lat"]},{data["lon"]},"{data["timestamp"]}"\n')
            try:
                os.chmod(csv_file, 0o644)
            except (OSError, PermissionError):
                pass
        except Exception as e:
            logging.error(f"[WigleLocator] Error generating CSV: {e}")

    def _generate_kml(self):
        kml_file = os.path.join(self.data_dir, 'wigle_locations.kml')
        try:
            kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Pwnagotchi WiGLE Locations</name>
"""
            for bssid, data in self.cache.items():
                if data.get('lat') is not None:
                    safe_essid = self._sanitize_html(data['essid'])
                    safe_bssid = self._sanitize_html(bssid)
                    kml_content += f"""    <Placemark>
      <name>{safe_essid}</name>
      <description>BSSID: {safe_bssid}</description>
      <Point>
        <coordinates>{data['lon']},{data['lat']},0</coordinates>
      </Point>
    </Placemark>
"""
            kml_content += "  </Document>\n</kml>"
            with open(kml_file, 'w') as f:
                f.write(kml_content)
            try:
                os.chmod(kml_file, 0o644)
            except (OSError, PermissionError):
                pass
        except Exception as e:
            logging.error(f"[WigleLocator] Error generating KML: {e}")

    def _generate_html_map(self):
        html_file = os.path.join(self.data_dir, 'wigle_map.html')
        try:
            lats = [d['lat'] for d in self.cache.values() if d.get('lat') is not None]
            lons = [d['lon'] for d in self.cache.values() if d.get('lon') is not None]
            
            if lats:
                center_lat = sum(lats) / len(lats)
                center_lon = sum(lons) / len(lons)
            else:
                center_lat, center_lon = 0, 0

            markers_js = "var locations = [\n"
            for bssid, data in self.cache.items():
                if data.get('lat') is not None:
                    safe_essid = json.dumps(data['essid'])
                    safe_bssid = json.dumps(bssid)
                    markers_js += f"  [{safe_essid} + ' (' + {safe_bssid} + ')', {data['lat']}, {data['lon']}],\n"
            markers_js += "];"

            # Status display
            cooldown_status = ""
            if self.api_limit_hit and time.time() < self.api_limit_reset_time:
                remaining = int((self.api_limit_reset_time - time.time()) / 60)
                cooldown_status = f'<div class="alert">⚠️ API Cooldown: {remaining} min remaining</div>'

            html_content = f"""<!DOCTYPE html>
<html>
<head>
  <title>Pwnagotchi WiGLE Map</title>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" 
    integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
  <style>
    body {{ margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
    #map {{ position: absolute; top: 0; bottom: 0; width: 100%; z-index: 1; }}
    #controls {{ position: absolute; top: 10px; right: 10px; z-index: 1000; background: white; 
                 padding: 15px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.2); 
                 max-width: 280px; }}
    #controls h3 {{ margin: 0 0 10px 0; font-size: 16px; color: #333; }}
    #controls a {{ display: block; margin: 8px 0; color: #0066cc; text-decoration: none; 
                   font-size: 14px; padding: 5px; border-radius: 4px; transition: background 0.2s; }}
    #controls a:hover {{ background: #f0f0f0; text-decoration: underline; }}
    #controls button {{ color: white; border: none; padding: 8px 12px; 
                        cursor: pointer; font-weight: bold; width: 100%; margin-top: 8px; 
                        border-radius: 4px; font-size: 14px; transition: background 0.2s; }}
    #controls button.primary {{ background: #007bff; }}
    #controls button.primary:hover {{ background: #0056b3; }}
    #controls button.danger {{ background: #dc3545; }}
    #controls button.danger:hover {{ background: #c82333; }}
    #controls hr {{ border: none; border-top: 1px solid #ddd; margin: 10px 0; }}
    .stats {{ font-size: 12px; color: #666; margin: 5px 0; }}
    .stats.live {{ display: flex; justify-content: space-between; align-items: center; }}
    .stats.live .refresh-icon {{ cursor: pointer; opacity: 0.6; transition: opacity 0.2s; }}
    .stats.live .refresh-icon:hover {{ opacity: 1; }}
    .alert {{ background: #fff3cd; color: #856404; padding: 8px; border-radius: 4px; 
              font-size: 12px; margin: 10px 0; border: 1px solid #ffeaa7; }}
    .success-alert {{ background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
    #statusModal {{ display: none; position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
                     background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                     z-index: 2000; min-width: 300px; }}
    #statusModal h4 {{ margin: 0 0 15px 0; color: #333; }}
    #statusModal .status-row {{ display: flex; justify-content: space-between; padding: 8px 0;
                                 border-bottom: 1px solid #eee; }}
    #statusModal .status-row:last-child {{ border-bottom: none; }}
    #statusModal .status-label {{ color: #666; }}
    #statusModal .status-value {{ font-weight: bold; color: #333; }}
    #statusModal button {{ margin-top: 15px; }}
    #overlay {{ display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(0,0,0,0.5); z-index: 1999; }}
  </style>
</head>
<body>
  <div id="overlay" onclick="closeStatus()"></div>
  <div id="statusModal">
    <h4>📊 Plugin Status</h4>
    <div class="status-row">
      <span class="status-label">📌 Cached Locations:</span>
      <span class="status-value" id="stat-cache">{len(lats)}</span>
    </div>
    <div class="status-row">
      <span class="status-label">📋 Queue Size:</span>
      <span class="status-value" id="stat-queue">{len(self.pending_queue)}</span>
    </div>
    <div class="status-row">
      <span class="status-label">📊 Daily Requests:</span>
      <span class="status-value" id="stat-daily">{self.daily_request_count}</span>
    </div>
    <div class="status-row">
      <span class="status-label">🔄 Processing:</span>
      <span class="status-value" id="stat-processing">No</span>
    </div>
    <div class="status-row">
      <span class="status-label">⚠️ Rate Limited:</span>
      <span class="status-value" id="stat-limited">No</span>
    </div>
    <div class="status-row">
      <span class="status-label">⏱️ Cooldown Remaining:</span>
      <span class="status-value" id="stat-cooldown">0 min</span>
    </div>
    <button class="primary" onclick="closeStatus()">Close</button>
  </div>
  
  <div id="controls">
    <h3>📍 WiGLE Map</h3>
    <div class="stats live">
      <span>📌 Locations: <strong id="live-cache">{len(lats)}</strong></span>
      <span class="refresh-icon" onclick="refreshStats()" title="Refresh stats">🔄</span>
    </div>
    <div class="stats">📋 Queue: <strong id="live-queue">{len(self.pending_queue)}</strong></div>
    <div class="stats">📊 Daily Requests: <strong id="live-daily">{self.daily_request_count}</strong></div>
    {cooldown_status}
    <button class="primary" onclick="showStatus()">📊 View Full Status</button>
    <hr>
    <a href="kml" download>📥 Download KML</a>
    <a href="csv" download>📥 Download CSV</a>
    <a href="json" download>📥 Download JSON</a>
    <hr>
    <button class="danger" onclick="flushQueue()">🗑️ Flush Queue & Reset</button>
  </div>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
  <script>
    var map = L.map('map').setView([{center_lat}, {center_lon}], 13);
    
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 19
    }}).addTo(map);

    {markers_js}

    for (var i = 0; i < locations.length; i++) {{
      L.marker([locations[i][1], locations[i][2]])
        .bindPopup('<strong>' + locations[i][0] + '</strong>')
        .addTo(map);
    }}

    if (locations.length > 0) {{
        var bounds = L.latLngBounds(locations.map(loc => [loc[1], loc[2]]));
        map.fitBounds(bounds, {{padding: [50, 50]}});
    }}

    async function refreshStats() {{
        try {{
            const response = await fetch(window.location.pathname.replace(/\\/+$/, '').replace(/\\/index\\.html$/, '') + '/status');
            if (!response.ok) throw new Error('Failed to fetch status');
            
            const data = await response.json();
            
            // Update live stats in sidebar
            document.getElementById('live-cache').textContent = data.cache_size;
            document.getElementById('live-queue').textContent = data.queue_size;
            document.getElementById('live-daily').textContent = data.daily_requests;
            
            // Update modal if open
            if (document.getElementById('statusModal').style.display === 'block') {{
                updateModalStatus(data);
            }}
            
            // Show brief success indicator
            const refreshIcon = document.querySelector('.refresh-icon');
            refreshIcon.textContent = '✅';
            setTimeout(() => {{ refreshIcon.textContent = '🔄'; }}, 1000);
        }} catch(err) {{
            console.error('Status refresh error:', err);
            const refreshIcon = document.querySelector('.refresh-icon');
            refreshIcon.textContent = '❌';
            setTimeout(() => {{ refreshIcon.textContent = '🔄'; }}, 1000);
        }}
    }}

    function updateModalStatus(data) {{
        document.getElementById('stat-cache').textContent = data.cache_size;
        document.getElementById('stat-queue').textContent = data.queue_size;
        document.getElementById('stat-daily').textContent = data.daily_requests;
        document.getElementById('stat-processing').textContent = data.processing ? 'Yes ⚙️' : 'No';
        document.getElementById('stat-limited').textContent = data.api_limit_hit ? 'Yes ⚠️' : 'No';
        document.getElementById('stat-cooldown').textContent = data.cooldown_minutes_remaining + ' min';
        
        // Update limited status style
        const limitedEl = document.getElementById('stat-limited');
        limitedEl.style.color = data.api_limit_hit ? '#dc3545' : '#28a745';
    }}

    async function showStatus() {{
        try {{
            const response = await fetch(window.location.pathname.replace(/\\/+$/, '').replace(/\\/index\\.html$/, '') + '/status');
            if (!response.ok) throw new Error('Failed to fetch status');
            
            const data = await response.json();
            updateModalStatus(data);
            
            document.getElementById('statusModal').style.display = 'block';
            document.getElementById('overlay').style.display = 'block';
        }} catch(err) {{
            alert('❌ Error fetching status: ' + err.message);
        }}
    }}

    function closeStatus() {{
        document.getElementById('statusModal').style.display = 'none';
        document.getElementById('overlay').style.display = 'none';
    }}

    // Auto-refresh stats every 30 seconds
    setInterval(refreshStats, 30000);

    async function flushQueue() {{
        if(!confirm('⚠️ Are you sure?\\n\\nThis will:\\n• Clear all pending queue items\\n• Reset the 429 rate limit cooldown\\n• Reset daily request counter\\n• Stop all retry loops\\n\\nThis is useful if you hit the rate limit.')) {{
            return;
        }}
        
        try {{
            const tokenResp = await fetch(window.location.pathname.replace(/\\/+$/, '') + '/token');
            if (!tokenResp.ok) throw new Error('Could not get security token');
            
            const tokenData = await tokenResp.json();
            const token = tokenData.token;
            
            const flushUrl = window.location.pathname.replace(/\\/+$/, '').replace(/\\/index\\.html$/, '') + '/flush?token=' + encodeURIComponent(token);
            const response = await fetch(flushUrl);
            
            if (response.ok) {{
                const text = await response.text();
                alert('✅ ' + text + '\\n\\nRefreshing page...');
                location.reload(); 
            }} else {{
                throw new Error(response.statusText);
            }}
        }} catch(err) {{
            alert('❌ Error: ' + err.message);
            console.error('Flush error:', err);
        }}
    }}
  </script>
</body>
</html>"""
            with open(html_file, 'w') as f:
                f.write(html_content)
            try:
                os.chmod(html_file, 0o644)
            except (OSError, PermissionError):
                pass
        except Exception as e:
            logging.error(f"[WigleLocator] Error generating HTML map: {e}")
