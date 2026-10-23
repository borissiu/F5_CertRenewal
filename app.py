#app.py
from flask import Flask, flash, request, redirect, url_for, render_template
import json, requests
import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'sslcert/'

app = Flask(__name__)
app.secret_key = "secret key"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

username = 'admin'; password = 'Removed'
vsInfo = {'items':[]}
poolInfo = {'items':[]}

@app.route('/start', methods=['GET'])
def start():
  return render_template('start.html')

@app.route('/', methods=['GET', 'POST'])
def home():
  if request.method=='POST' or request.method=='GET':
    vsInfo = getVsInfo()
  return render_template('index.html', vsInfo=vsInfo, poolInfo=poolInfo)

@app.route('/get_member/<partitionName>/<vsName>/<poolName>', methods=['GET', 'POST'])
def get_member(partitionName, vsName, poolName):
  poolInfo = {'items':[]}
  response = requests.get('https://IP-Removed/mgmt/tm/ltm/pool/~' + partitionName + '~' + poolName+'/members', auth=(username, password), verify=False)
  data = response.json()['items']
  for api_data in data:
    if api_data['session'] == "user-disabled" : api_data['state'] = 'disabled' 
    poolInfo['items'].append({'Member Status':api_data['state'], 'Member':api_data['name'], 'Address':api_data['address'], 'Port':api_data['fullPath'].split(':')[1], 'Partition':api_data['partition'], 'Edit Member':'Disable'})        
  for i in range(len(poolInfo['items'])):
    if poolInfo['items'][i]['Member Status'] == "disabled": poolInfo['items'][i]['Edit Member'] = "Enable"
  vsInfo = getVsInfo()
  return render_template('index.html', vsInfo=vsInfo, poolInfo=poolInfo, poolName=poolName, vsName=vsName)

@app.route('/edit_vs/<partitionName>/<vsName>/<action>', methods=['POST'])
def edit_vs(partitionName, vsName, action):
  editVsUrl = 'https://IP-Removed/mgmt/tm/ltm/virtual/~' + partitionName + '~' + vsName
  data = { "disabled": True } if action == "Enable" else { "enabled": True }
  response = requests.patch(url=editVsUrl, json=data, auth=(username, password), verify=False)
  vsInfo = getVsInfo()
  return render_template('index.html', vsInfo=vsInfo, poolInfo=poolInfo)

@app.route('/edit_member/<partitionName>/<vsName>/<poolName>/<memberName>/<action>', methods=['POST'])
def edit_member(partitionName, vsName, poolName, memberName, action):
  editMemberUrl = 'https://IP-Removed/mgmt/tm/ltm/pool/~' + partitionName + '~' + poolName + '/members/~' + partitionName + '~' + memberName
  data = { "session": "user-enabled" } if action == 'Enable' else { "session": "user-disabled" }
  response = requests.patch(url=editMemberUrl, json=data, auth=(username, password), verify=False)
  vsInfo = getVsInfo()
  return redirect('/get_member/' + partitionName + '/' + vsName + '/' + poolName)


@app.route('/edit_cert/<clientsslProfileName>/<partitionName>/<certName>', methods=['GET', 'POST'])
def edit_cert(clientsslProfileName, partitionName, certName):
  if request.method=='GET':
    return render_template('table_sslcert.html', clientsslProfileName=clientsslProfileName, partitionName=partitionName, certName=certName)
  if request.method=='POST':
    if request.form['action'] == 'Update Cert':
      sslcert = request.files['sslcert']
      sslkey = request.files['sslkey']
      sslchain = request.files['sslchain']

      if sslchain.filename != '':
        filename = secure_filename(sslchain.filename)
        sslcert.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

      if sslcert.filename != '':
        filename = secure_filename(sslcert.filename)
        sslcert.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        with open("./sslcert/"+filename, "rb") as f:
          data = f.read()        
        headers = {
            "Content-Type": "application/octet-stream",
            "Content-Range": "0-" + str(len(data)-1) + "/" + str(len(data))
        }
        editCertUrl = "https://IP-Removed:443/mgmt/shared/file-transfer/uploads/" + filename
        response = requests.post(editCertUrl, headers=headers, data=data, auth=(username, password), verify=False)
        
        installCertUrl = "https://IP-Removed:443/mgmt/tm/sys/crypto/cert"  
        headers = { "Content-Type: application/json" }
        data = {
            "command": "install",
            "name": filename,
            "from-local-file": "/var/config/rest/downloads/" + filename
        }
        response = requests.post(installCertUrl, json=data, auth=(username, password), verify=False)

      if sslkey.filename != '':
        filename = secure_filename(sslkey.filename)
        sslkey.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        with open("./sslcert/"+filename, "rb") as f:
          data = f.read()        
        headers = {
            "Content-Type": "application/octet-stream",
            "Content-Range": "0-" + str(len(data)-1) + "/" + str(len(data))
        }
        editCertUrl = "https://IP-Removed:443/mgmt/shared/file-transfer/uploads/" + filename
        response = requests.post(editCertUrl, headers=headers, data=data, auth=(username, password), verify=False)

        installKeyUrl = "https://IP-Removed:443/mgmt/tm/sys/crypto/key"  
        data = {
            "command": "install",
            "name": filename,
            "from-local-file": "/var/config/rest/downloads/" + filename
        }
        response = requests.post(installKeyUrl, json=data, auth=(username, password), verify=False)

      editClientSslProfile = "https://IP-Removed:443/mgmt/tm/ltm/profile/client-ssl/" + clientsslProfileName
      data = {
        "certKeyChain": [{
          "name": "cert_config_via_api", 
          "appService": "none", 
          "cert": "/Common/" + sslcert.filename, 
          "chain": "none", 
          "key": "/Common/" + sslkey.filename, 
          "usage": "SERVER"}]
          }
      response = requests.patch(editClientSslProfile, json=data, auth=(username, password), verify=False)
    return render_template('table_sslcert.html', clientsslProfileName=clientsslProfileName, partitionName=partitionName, certName=certName, result=response.status_code)

if __name__ == "__main__":
  app.run()


def getVsInfo():
  vsInfo = {'items':[]}
  response = requests.get('https://IP-Removed/mgmt/tm/ltm/virtual', auth=(username, password), verify=False)
  data = response.json()['items']
  for api_data in data:
    if "description" in api_data and "pool" in api_data: ###Do Not display VS without description and pool (need to work on iRules later on)
      if "enabled" in api_data:
        vsInfo['items'].append({'VS Status':'enabled', 'Edit VS': '', 'Name':api_data['name'], 'Description':api_data['description'], 'Destination':api_data['destination'].split(':')[0].split('/')[2], 'Port':api_data['destination'].split(':')[1], 'SSL_Cert': 'none', 'Protocol':api_data['ipProtocol'], 'Pool':api_data['pool'].split('/')[2], 'Partition':api_data['partition'], 'Edit Pool':'xxx'})
      else:
        vsInfo['items'].append({'VS Status':'disabled', 'Edit VS': '', 'Name':api_data['name'], 'Description':api_data['description'], 'Destination':api_data['destination'].split(':')[0].split('/')[2], 'Port':api_data['destination'].split(':')[1], 'SSL_Cert': 'none', 'Protocol':api_data['ipProtocol'], 'Pool':api_data['pool'].split('/')[2], 'Partition':api_data['partition'], 'Edit Pool':'xxx'})
  
  getVsProfiles(vsInfo)
  return vsInfo

def getVsProfiles(vsInfo):
  for vsItem in vsInfo['items']:
    response = requests.get('https://IP-Removed/mgmt/tm/ltm/virtual/'+vsItem['Name']+'/profiles', auth=(username, password), verify=False)
    data = response.json()['items']
    for profilesItem in data:
      if profilesItem['context'] == "clientside":
        sslProfileName = profilesItem['name']
        response = requests.get('https://IP-Removed/mgmt/tm/ltm/profile/client-ssl/'+sslProfileName, auth=(username, password), verify=False)
        sslCertName = response.json()['certKeyChain'][0]['cert']
        vsItem['SSL_Cert'] = sslProfileName+sslCertName
  return

