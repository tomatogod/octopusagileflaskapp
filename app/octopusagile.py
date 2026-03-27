from flask import Flask
import requests
import datetime
import os
import threading
import signal
import sys

# Cache settings
CACHE_TTL_SECONDS = int(os.getenv('OCTOPUSCACHE_TTL', '300'))  # default 5 minutes
api_cache = {}
cache_lock = threading.Lock()
fetch_lock = threading.Lock()
stop_event = threading.Event()
cache_refresher_thread = None

# Config items
apikey = os.getenv('OCTOPUSAPIKEY', '').strip()
apiurl = os.getenv(
    'OCTOPUSAPIURL',
    'https://api.octopus.energy/v1/products/AGILE-24-10-01/electricity-tariffs/E-1R-AGILE-24-10-01-D/standard-unit-rates/'
).strip()

if not apikey:
    raise RuntimeError('OCTOPUSAPIKEY environment variable is required')
if not apiurl:
    raise RuntimeError('OCTOPUSAPIURL environment variable is required')
if not apiurl.startswith(('http://', 'https://')):
    raise RuntimeError('OCTOPUSAPIURL must start with http:// or https://')

# time period definitions
def get_period_from():
    getdate = str(datetime.datetime.now().strftime("%Y-%m-%d"))
    gethour = str(datetime.datetime.now().strftime("%H"))
    if int(gethour) >= 18:
        period = str(getdate) + "T17:00:00Z"
        return period
    else:
        period = datetime.datetime.today() - datetime.timedelta(days=1)
        period = period.strftime("%Y-%m-%d")
        period = period + "T17:00:00Z"
        return period

def get_period_to():
    getdate = str(datetime.datetime.now().strftime("%Y-%m-%d"))
    gethour = str(datetime.datetime.now().strftime("%H"))
    if int(gethour) < 18:
        period = str(getdate) + "T17:00:00Z"
        return period
    else:
        period = datetime.datetime.today() - datetime.timedelta(days=-1)
        period = period.strftime("%Y-%m-%d")
        period = period + "T17:00:00Z"
        return period

def get_period_start_of_hour():
    getdate = str(datetime.datetime.now().strftime("%Y-%m-%d"))
    gethour = str(datetime.datetime.now().strftime("%H:00:00"))
    period = str(getdate + 'T' + gethour + 'Z')
    return period

def get_period_now():
    getdate = str(datetime.datetime.now().strftime("%Y-%m-%d"))
    gethour = str(datetime.datetime.now().strftime("%H:%M:%S"))
    period = str(getdate + 'T' + gethour + 'Z')
    return period

def get_period_end_of_hour():
    getdate = str(datetime.datetime.now().strftime("%Y-%m-%d"))
    gethour = str(datetime.datetime.now().strftime("%H"))
    period = str(getdate + 'T' + gethour + ':59:59Z')
    return period

def get_period_now_rounded():
    now = datetime.datetime.now(datetime.timezone.utc)  # Timezone-aware UTC
    # Round down to nearest CACHE_TTL_SECONDS
    rounded_seconds = (now.timestamp() // CACHE_TTL_SECONDS) * CACHE_TTL_SECONDS
    rounded_time = datetime.datetime.fromtimestamp(rounded_seconds, tz=datetime.timezone.utc)
    period = rounded_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    return period

def get_period_now_rounded_plus_ttl():
    now = datetime.datetime.now(datetime.timezone.utc)
    # Round down to nearest CACHE_TTL_SECONDS, then add CACHE_TTL_SECONDS
    rounded_seconds = ((now.timestamp() // CACHE_TTL_SECONDS) * CACHE_TTL_SECONDS) + CACHE_TTL_SECONDS
    rounded_time = datetime.datetime.fromtimestamp(rounded_seconds, tz=datetime.timezone.utc)
    period = rounded_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    return period


def _parse_octopus_time(ts: str):
    if not ts:
        raise ValueError('Invalid timestamp')
    if ts.endswith('Z'):
        ts = ts[:-1] + '+00:00'
    return datetime.datetime.fromisoformat(ts)


def _get_current_rate_from_day(data):
    now = datetime.datetime.now(datetime.timezone.utc)
    for item in data.get('results', []):
        try:
            valid_from = _parse_octopus_time(item.get('valid_from') or item.get('from'))
            valid_to = _parse_octopus_time(item.get('valid_to') or item.get('to'))
        except Exception:
            continue
        if valid_from <= now < valid_to:
            print(f"currentelectric: found active slot {valid_from} - {valid_to} (now={now})")
            return item.get('value_inc_vat')

    if data.get('results'):
        fallback = data['results'][-1].get('value_inc_vat')
        print(f"currentelectric: no active slot; fallback to latest slot value at {now}")
        return fallback

    print(f"currentelectric: no data at all to determine current rate at {now}")
    return None


def _cache_get(key):
    with cache_lock:
        entry = api_cache.get(key)
        if not entry:
            return None
        age = (datetime.datetime.now(datetime.timezone.utc) - entry['fetched']).total_seconds()
        if age >= CACHE_TTL_SECONDS:
            api_cache.pop(key, None)
            return None
        return entry['data']


def _cache_set(key, data):
    with cache_lock:
        api_cache[key] = {
            'fetched': datetime.datetime.now(datetime.timezone.utc),
            'data': data,
        }


def get_rates_from_api(period_from, period_to):
    key = f"{period_from}|{period_to}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    with fetch_lock:
        cached = _cache_get(key)
        if cached is not None:
            return cached

        if not apiurl:
            raise RuntimeError('Invalid OCTOPUSAPIURL (empty)')

        headers = {'Authorization': apikey}
        res = requests.get(
            apiurl,
            headers=headers,
            params={'period_from': period_from, 'period_to': period_to},
            timeout=10,
        )
        res.raise_for_status()
        data = res.json()

        print(f"Cache refresh: fetched {len(data.get('results', []))} rates for {period_from} to {period_to}")
        _cache_set(key, data)
        return data


# flask endpoints

app = Flask(__name__)

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/<NumberOfSlots>')
def getlowestrates(NumberOfSlots):
    slots = int(NumberOfSlots)
    getdatefrom = get_period_from()
    getdateto = get_period_to()
    data = get_rates_from_api(getdatefrom, getdateto)

    value_inc_vat = [x['value_inc_vat'] for x in data.get('results', [])]
    if not value_inc_vat or slots < 0 or slots >= len(value_inc_vat):
        return 'Invalid slot index', 400

    prices = sorted(value_inc_vat)
    return str(round((prices[slots] / 100), 4))


@app.route('/currentelectric')
def getcurrentrate():
    getdatefrom = get_period_from()
    getdateto = get_period_to()
    data = get_rates_from_api(getdatefrom, getdateto)

    current_value = _get_current_rate_from_day(data)
    if current_value is None:
        return 'No data available', 500

    return str(round((current_value / 100), 4))  # Current active half-hour rate


@app.before_first_request
def start_cache_refresher():
    global cache_refresher_thread
    if cache_refresher_thread is None or not cache_refresher_thread.is_alive():
        def _refresher():
            while not stop_event.is_set():
                try:
                    get_rates_from_api(get_period_from(), get_period_to())
                    get_rates_from_api(get_period_start_of_hour(), get_period_now_rounded_plus_ttl())
                except Exception as ex:
                    print(f"Cache refresher error: {ex}")
                stop_event.wait(CACHE_TTL_SECONDS)

        cache_refresher_thread = threading.Thread(target=_refresher, daemon=True)
        cache_refresher_thread.start()


def _graceful_shutdown(signum, frame):
    print(f"Received shutdown signal ({signum}); exiting gracefully...")
    stop_event.set()
    if cache_refresher_thread is not None and cache_refresher_thread.is_alive():
        cache_refresher_thread.join(timeout=5)
    sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, _graceful_shutdown)
    signal.signal(signal.SIGINT, _graceful_shutdown)

    print("tomatogod/octopusagileflask app starting...")
    port = int(os.getenv('PORT', '5000'))
    app.run(debug=False, host='0.0.0.0', port=port)
