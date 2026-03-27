from flask import Flask
import requests
import datetime
import os
import threading

# Cache settings
CACHE_TTL_SECONDS = int(os.getenv('OCTOPUSCACHE_TTL', '300'))  # default 5 minutes
api_cache = {}
cache_lock = threading.Lock()

# Config items
try:
    apikey = os.environ['OCTOPUSAPIKEY']
except:
    print('APIKEY Environment Variable Not Set')
    exit
try:    
    apiurl = os.environ['OCTOPUSAPIURL']
except:
    print('APIURL Environment Variable Not Set')
    exit

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


def _cache_get(key):
    with cache_lock:
        entry = api_cache.get(key)
        if not entry:
            return None
        age = (datetime.datetime.utcnow() - entry['fetched']).total_seconds()
        if age >= CACHE_TTL_SECONDS:
            api_cache.pop(key, None)
            return None
        return entry['data']


def _cache_set(key, data):
    with cache_lock:
        api_cache[key] = {
            'fetched': datetime.datetime.utcnow(),
            'data': data,
        }


def get_rates_from_api(period_from, period_to):
    key = f"{period_from}|{period_to}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    getratesurl = f"{apiurl}?period_from={period_from}&period_to={period_to}"
    headers = {'Authorization': apikey}
    res = requests.get(getratesurl, headers=headers, timeout=10)
    res.raise_for_status()
    data = res.json()

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
    getdatefrom = get_period_start_of_hour()
    getdateto = get_period_now()
    data = get_rates_from_api(getdatefrom, getdateto)

    value_inc_vat = [x['value_inc_vat'] for x in data.get('results', [])]
    if not value_inc_vat:
        return 'No data available', 500

    return str(round((value_inc_vat[0] / 100), 4))

if __name__ == '__main__':
    print("tomatogod/octopusagileflask app starting...")
    port = int(os.getenv('PORT', '5000'))
    app.run(debug=False, host='0.0.0.0', port=port)