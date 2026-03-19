from flask import Flask
import requests
import datetime
import os

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


# flask endpoints

app = Flask(__name__)

@app.route('/<NumberOfSlots>')
def getlowestrates(NumberOfSlots):
    slots = int(NumberOfSlots)
    getdatefrom = get_period_from()
    print ("hello")
    getdateto = get_period_to()
    periodfrom = f"?period_from={getdatefrom}"
    periodto = f"&period_to={getdateto}"
    getratesurl = f"{apiurl}{periodfrom}{periodto}"
    headers = {'Authorization': apikey}
    res = requests.get(getratesurl, headers=headers)
    data = res.json()
    value_inc_vat = [x['value_inc_vat'] for x in data['results']]
    prices = sorted(value_inc_vat)
    return str(round((prices[slots] / 100),4))

@app.route('/currentelectric')
def getcurrentrate():
    getdatefrom = get_period_start_of_hour()
    getdateto = get_period_now()
    periodfrom = f"?period_from={getdatefrom}"
    periodto = f"&period_to={getdateto}"
    getratesurl = f"{apiurl}{periodfrom}{periodto}"
    headers = {'Authorization': apikey}
    res = requests.get(getratesurl, headers=headers)
    data = res.json()
    value_inc_vat = [x['value_inc_vat'] for x in data['results']]
    return str(round((value_inc_vat[0] / 100), 4))

if __name__ == '__main__':
    print("tomatogod/octopusagileflask app starting...")
    app.run(debug=True, host='0.0.0.0', port=5000)