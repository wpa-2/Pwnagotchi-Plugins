import requests
import os
import logging
import json
import threading
import time
from datetime import datetime
from pwnagotchi.plugins import Plugin
from flask import send_from_directory, Response

class WigleLocator(Plugin):
    __author__ = 'WPA2'
    __version__ = '2.1.6'
    __license__ = 'GPL3'
    __description__ = 'Async WiGLE locator with max retries and strict 429 backoff'

    def __init__(self):
        self.api_key = None
        self.data_dir = '/home/pi/wigle_locator_data'
        self.cache_file = os.path.join(self.data_dir, 'wigle_cache.json')
        self.queue_file = os.path.join(self.data_dir, 'pending_queue.json')
        self.cache = {}
        self.pending_queue = []
        self.lock = threading.Lock()
        self.processing = False
        self.last_queue_process_time = 0
        self.api_limit_hit = False
        self.api_limit_reset_time = 0

    def on_loaded(self):
        if not os.path.exists(self.data_dir):
            try:
                os.makedirs(self.data_dir)
                os.chown(self.data_dir, 1000, 1000) 
            except Exception as e:
                logging.warning(f"[WigleLocator] Could not set folder permissions: {e}")
            
        self._load_data()
        logging.info(f"[WigleLocator] Plugin loaded. Cache: {len(self.cache)}, Queue: {len(self.pending_queue)}")

    def on_config_changed(self, config):
        if 'main' in config and 'plugins' in config['main'] and 'wiglelocator' in config['main']['plugins']:
            self.api_key = config['main']['plugins']['wiglelocator'].get('api_key')

        if not self.api_key:
            logging.error('[WigleLocator] No API key set in config.toml!')

    def on_webhook(self, path, request):
        try:
            if not path or path == '/':
                return send_from_directory(self.data_dir, 'wigle_map.html')
            elif path == 'kml':
                return send_from_directory(self.data_dir, 'wigle_locations.kml', as_attachment=True)
            elif path == 'csv':
                return send_from_directory(self.data_dir, 'locations.csv', as_attachment=True)
            elif path == 'json':
                return send_from_directory(self.data_dir, 'wigle_cache.json', as_attachment=True)
            return "File not found", 404
        except Exception as e:
            logging.error(f"[WigleLocator] Webhook error: {e}")
            return f"Error: {e}", 500

    def on_handshake(self, agent, filename, access_point, client_station):
        if not self.api_key:
            return
            
        # Don't even try if we are in penalty box
        if self.api_limit_hit and time.time() < self.api_limit_reset_time:
            return

        bssid = access_point["mac"]
        essid = access_point["hostname"]
        
        threading.Thread(target=self._process_candidate, args=(agent, bssid, essid)).start()

    def on_internet_available(self, agent):
        now = time.time()
        
        # CHECK 1: Are we in 429 penalty box?
        if self.api_limit_hit:
            if now > self.api_limit_reset_time:
                self.api_limit_hit = False
                logging.info("[WigleLocator] API limit cooldown expired. Resuming operations.")
            else:
                return # Still in timeout, do nothing.

        # CHECK 2: Standard batch cooldown (5 mins)
        if self.pending_queue and not self.processing:
            if now - self.last_queue_process_time > 300:
                logging.info(f"[WigleLocator] Internet available. Processing {len(self.pending_queue)} pending items...")
                threading.Thread(target=self._process_queue, args=(agent,)).start()

    def _process_candidate(self, agent, bssid, essid):
        with self.lock:
            if bssid in self.cache:
                if self.cache[bssid].get('lat') is None:
                    return
                return

        result = self._fetch_wigle_location(bssid)

        if isinstance(result, dict):
            self._handle_success(agent, bssid, essid, result)
        elif result == 'LIMIT_EXCEEDED':
            # Stop immediately, handled inside _fetch
            pass
        elif result is False:
            self._cache_failure(bssid, essid)
        else:
            self._add_to_queue(bssid, essid)

    def _process_queue(self, agent):
        self.processing = True
        self.last_queue_process_time = time.time()
        
        queue_copy = list(self.pending_queue)
        
        for item in queue_copy:
            # Emergency Stop Check
            if self.api_limit_hit:
                logging.warning("[WigleLocator] 429 Limit Hit - Aborting Queue Processing immediately.")
                break

            bssid = item['bssid']
            essid = item['essid']
            retries = item.get('retries', 0)
            
            if bssid in self.cache:
                self._remove_from_queue(bssid)
                continue

            result = self._fetch_wigle_location(bssid)
            
            if isinstance(result, dict):
                # Success
                self._handle_success(agent, bssid, essid, result)
                self._remove_from_queue(bssid)
                time.sleep(5) # Increased safety delay
            elif result == 'LIMIT_EXCEEDED':
                # Critical Stop
                break 
            elif result is False:
                # Not Found - Remove
                self._cache_failure(bssid, essid)
                self._remove_from_queue(bssid)
                time.sleep(1)
            else:
                # Other Error (Network/Server)
                retries += 1
                if retries >= 3:
                    logging.warning(f"[WigleLocator] Max retries reached for {essid}. Dropping from queue.")
                    self._remove_from_queue(bssid)
                else:
                    item['retries'] = retries
                    self._save_data()
                    time.sleep(1)
        
        self.processing = False

    def _handle_success(self, agent, bssid, essid, location):
        logging.info(f"[WigleLocator] Located {essid}: {location['lat']}, {location['lon']}")
        
        if agent:
            try:
                view = agent.view()
                view.set("status", f"Loc: {location['lat']},{location['lon']}")
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
        """
        Returns:
          dict: {'lat': ..., 'lon': ...}
          False: Definitive Not Found (404/No Results)
          'LIMIT_EXCEEDED': 429 Error (Stop everything)
          None: Generic Error (Retry later)
        """
        # Double check before making request
        if self.api_limit_hit and time.time() < self.api_limit_reset_time:
            return 'LIMIT_EXCEEDED'

        headers = {'Authorization': 'Basic ' + self.api_key}
        params = {'netid': bssid}

        try:
            response = requests.get(
                'https://api.wigle.net/api/v2/network/detail', 
                headers=headers, 
                params=params, 
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('results'):
                    result = data['results'][0]
                    return {'lat': result.get('trilat'), 'lon': result.get('trilong')}
                else:
                    return False
            elif response.status_code == 404:
                return False
            elif response.status_code == 429:
                logging.error("[WigleLocator] ⚠️ 429 TOO MANY REQUESTS. Pausing WiGLE API for 1 hour.")
                self.api_limit_hit = True
                self.api_limit_reset_time = time.time() + 3600 # 1 Hour Penalty
                return 'LIMIT_EXCEEDED'
            elif response.status_code == 401:
                logging.error("[WigleLocator] WiGLE Auth failed.")
                return False
                
        except Exception as e:
            logging.debug(f"[WigleLocator] API request failed: {e}")
            
        return None

    def _add_to_queue(self, bssid, essid):
        with self.lock:
            if not any(x['bssid'] == bssid for x in self.pending_queue):
                # Don't log spam the queue additions
                self.pending_queue.append({
                    'bssid': bssid, 
                    'essid': essid,
                    'retries': 0
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
        except Exception as e:
            logging.error(f"[WigleLocator] Error loading data: {e}")

    def _save_data(self):
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f)
            with open(self.queue_file, 'w') as f:
                json.dump(self.pending_queue, f)
            os.chmod(self.cache_file, 0o666)
            os.chmod(self.queue_file, 0o666)
        except Exception:
            pass

    def _generate_outputs(self):
        try:
            self._generate_kml()
            self._generate_html_map()
            self._generate_csv()
        except Exception as e:
            logging.error(f"[WigleLocator] Map generation error: {e}")

    def _generate_csv(self):
        csv_file = os.path.join(self.data_dir, 'locations.csv')
        with open(csv_file, 'w') as f:
            f.write("BSSID,ESSID,Latitude,Longitude,Timestamp\n")
            for bssid, data in self.cache.items():
                if data.get('lat') is not None:
                    f.write(f"{bssid},{data['essid']},{data['lat']},{data['lon']},{data['timestamp']}\n")
        try: os.chmod(csv_file, 0o666)
        except: pass

    def _generate_kml(self):
        kml_file = os.path.join(self.data_dir, 'wigle_locations.kml')
        kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Pwnagotchi WiGLE Locations</name>
"""
        for bssid, data in self.cache.items():
            if data.get('lat') is not None:
                kml_content += f"""    <Placemark>
      <name>{data['essid']}</name>
      <description>BSSID: {bssid}</description>
      <Point>
        <coordinates>{data['lon']},{data['lat']},0</coordinates>
      </Point>
    </Placemark>
"""
        kml_content += "  </Document>\n</kml>"
        with open(kml_file, 'w') as f: f.write(kml_content)
        try: os.chmod(kml_file, 0o666)
        except: pass

    def _generate_html_map(self):
        html_file = os.path.join(self.data_dir, 'wigle_map.html')
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
                safe_essid = data['essid'].replace("'", "\\'")
                markers_js += f"  ['{safe_essid} ({bssid})', {data['lat']}, {data['lon']}],\n"
        markers_js += "];"

        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <title>Pwnagotchi WiGLE Map</title>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
  <style>
    body {{ margin: 0; padding: 0; font-family: sans-serif; }}
    #map {{ position: absolute; top: 0; bottom: 0; width: 100%; z-index: 1; }}
    #controls {{ position: absolute; top: 10px; right: 10px; z-index: 1000; background: white; padding: 10px; border-radius: 5px; box-shadow: 0 0 5px rgba(0,0,0,0.3); }}
    a {{ display: block; margin: 5px 0; color: #333; text-decoration: none; font-weight: bold; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div id="controls">
    <h3>Data Export</h3>
    <a href="kml">Download .KML (Google Earth)</a>
    <a href="csv">Download .CSV (Excel)</a>
    <a href="json">Download .JSON (Raw)</a>
  </div>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
  <script>
    var map = L.map('map').setView([{center_lat}, {center_lon}], 13);
    
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }}).addTo(map);

    {markers_js}

    for (var i = 0; i < locations.length; i++) {{
      L.marker([locations[i][1], locations[i][2]])
        .bindPopup(locations[i][0])
        .addTo(map);
    }}
  </script>
</body>
</html>"""
        with open(html_file, 'w') as f: f.write(html_content)
        try: os.chmod(html_file, 0o666)
        except: pass
