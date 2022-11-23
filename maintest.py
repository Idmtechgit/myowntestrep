from flask import Flask
from flask import render_template, request,jsonify,Response
from subprocess import Popen, PIPE
import os
import urllib
import logging
import ast
from os import chmod
from Crypto.PublicKey import RSA

logger = logging.getLogger(__name__)
from version import __version__
from functools import wraps
from fractions import Fraction

BASE_DIR='/home/pi/domoticsClient'
from resolutions import resolutions
from outResolutions import outResolutions


netModes =['static', 'dhcp']
app = Flask(__name__)

def generatePanelURL():
    conf = getConf()
    url = "%s:%s" % (conf['panelURL'].replace(' ','_').rstrip('\n'), conf['panelPort'].replace(' ','_').rstrip('\n'))
    return url


def getConf():
    conf = {}
    fd=open('deviceName.conf','r')
    conf['deviceName']=fd.readline()
    fd.close()
    fd=open('deviceHttpPort.conf','r')
    conf['deviceHttpPort']=fd.readline()
    fd.close()
    fd=open('deviceSshPort.conf','r')
    conf['deviceSshPort']=fd.readline()
    fd.close()
    conf['version'] = __version__
    fd=open('panelURL.conf','r')
    conf['panelURL']=fd.readline()
    fd.close()
    fd=open('panelPort.conf','r')
    conf['panelPort']=fd.readline()
    fd.close()
    return conf

def setConf(conf):
    fd=open('deviceName.conf','w')
    fd.write('%s\n' % conf['deviceName'])
    fd.close()
    fd=open('panelURL.conf','w')
    fd.write('%s\n' % conf['panelURL'])
    fd.close()
    fd=open('panelPort.conf','w')
    fd.write('%s\n' % conf['panelPort'])
    fd.close()
    return conf

def registerDevice(deviceName):
    devicePublicKey=generateKeys()
    devicePublicKey=urllib.quote_plus(devicePublicKey)
    url = generatePanelURL()
    f = urllib.urlopen("%s/register?deviceName=%s&devicePublicKey=%s" % (url, deviceName,devicePublicKey))
    res = f.read()
    if res != "Device already exist":
        res = ast.literal_eval(res)
        f.close()
        fd=open('deviceHttpPort.conf','w')
        fd.write('%s\n' %res['HTTP_PORT'])
        fd.close()
        fd=open('deviceSshPort.conf','w')
        fd.write('%s\n' % res['SSH_PORT'])
        fd.close()

def checkIfRegistered(deviceName):
    url = generatePanelURL()
    f = urllib.urlopen("%s/checkIfRegistered?deviceName=%s" % (url, deviceName))
    res = ast.literal_eval(f.read())
    return res


def generateKeys():
    key = RSA.generate(2048)
    f = open(".private.key", "wb")
    f.write(key.exportKey('PEM'))
    f.close()
    os.system("chmod 400 .private.key")
    pubkey = key.publickey().exportKey('OpenSSH')
    f = open(".public.key", "wb")
    f.write(pubkey)
    f.close()
    return pubkey


def setSWVersion(deviceName):
    url = generatePanelURL()
    f = urllib.urlopen("%s/setswversion?deviceName=%s&SWVersion=%s" % (url ,deviceName, __version__))
    f.close(    )

def getSysConf():

    try:
        fd=open('/etc/network/interfaces.d/eth0.cfg','r')
    except:
        logger.info('Error on opening /etc/network/interfaces.d/eth0.cfg')
        return

    rows=fd.readlines()
    conf = {}
    fd.close()

    if rows[1].split()[3]=="static":
        conf['netMode'] = str(0)
    else:
        conf['netMode'] = str(1)

    try:
        conf['ipAddress'] = rows[2].split()[1]
    except:
        pass
    try:
        conf['netMask']= rows[3].split()[1]
    except:
        pass

    try:
        conf['gateWay']=rows[4].split()[1]
    except:
        pass


#Section wireless
    conf['enableWireless']=str(cmd(' if [ -f  /etc/network/interfaces.d/wlan0.cfg ];  then  echo 1; else echo  0; fi'))[0]
    if int(conf['enableWireless']):
        try:
            fd=open('/etc/network/interfaces.d/wlan0.cfg','r')


            rows=fd.readlines()
            fd.close()

            if rows[1].split()[3]=="dhcp":
                conf['netModeWlan'] = str(1)
                try:
                    conf['essidWlan']=conf['essidWlan']=rows[2].split()[1]
                    if len(rows[2].split())>2:
                        for i in rows[2].split()[2:]:
                            conf['essidWlan']=conf['essidWlan']+" " + i

                except:
                    conf['essidWlan']= ""

                try:
                    conf['passwordWlan']=rows[3].split()[1]
                except:
                    conf['passwordWlan']= ""

            else:
                conf['netModeWlan'] = str(0)

                try:
                    conf['ipAddressWlan'] = rows[2].split()[1]
                except:
                    pass
                try:
                    conf['netMaskWlan']= rows[3].split()[1]
                except:
                    pass

                try:
                    conf['gateWayWlan']=rows[4].split()[1]
                except:
                    pass
                try:
                    conf['essidWlan']=rows[5].split()[1]
                except:
                    pass

                try:
                    conf['passwordWlan']=rows[6].split()[1]
                except:
                    pass

        except:
            logger.info('Error on opening /etc/network/interfaces.d/eth0.cfg')

#Section dns
    fd=open('/etc/resolv.conf','r')
    rows=fd.readlines()
    numRows=len(rows)
    for i in range(1,numRows+1):
        conf['dns%s'%i]=rows[i-1].split()[1]
    return(conf)

def needDebianPckUpdate (packagename):
    subProc = Popen(["dpkg-query", "--showformat=${Version}", "--show"] + [packagename],  stdout=PIPE)
    versionInstalled=subProc.stdout.read()
    url = generatePanelURL()
    f = urllib.urlopen("%s/getPckVersions?packagename=%s" % (url, packagename))
    versionAvailable = f.read()
    if versionInstalled != versionAvailable:
        return True
    else:
        return False

def getDebianVersion():
    fd=open('/etc/debian_version','r')
    debianversion=fd.readline()
    fd.close()
    return int(debianversion.split('.')[0])



def setSysConf(conf,interface,wlanExtension):
    fd=open('/etc/network/interfaces.d/%s.cfg' %interface,'w')
    if conf['netMode'] == 0:
        fd.write('auto %s\n' % interface)
        fd.write('iface %s inet static\n' % interface)
        fd.write('address %s\n' % conf['ipAddress'])
        fd.write('netmask %s\n' % conf['netMask'])

        if conf['gateWay']:
            fd.write('gateway %s\n' % conf['gateWay'])
    else:
        fd.write('auto %s\n' % interface)
        fd.write('iface %s inet dhcp\n' % interface)

    if wlanExtension:
        if conf['passwordWlan']:
            fd.write('wpa-ssid %s\n' % conf['essidWlan'])
            fd.write('wpa-psk  %s\n' % conf['passwordWlan'])
        else:
            fd.write('wireless-essid %s\n' % conf['essidWlan'])


    fd.close()

def cmd(cmd):
    return subprocess.Popen(
    cmd, shell=True,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.read()


@app.route("/")

def main():
    conf = getConf()
    return render_template('main.html', conf=conf,resolutions=resolutions,outResolutions=outResolutions)

@app.route("/save", methods=["POST"])

def save():
    conf = {}
    if (request.form.get('save')):
        conf['deviceName'] = request.form['deviceName']
        conf['panelURL'] = request.form['panelURL']
        conf['panelPort'] = request.form['panelPort']
        setConf(conf)
    if (request.form.get('cancel')):
        pass
    return main()
#    return render_template('main.html', conf=conf)



@app.route("/power")

def power():
    conf = getSysConf()
    return render_template('power.html', conf=conf, netModes=netModes)

@app.route("/powerSystem", methods=["POST"])

def powerSystem():
    conf = {}
    if (request.form.get('Halt')):
        logger.info('Halt')
        os.system('halt &')
    if (request.form.get('Reboot')):
        logger.info('Reboot')
        os.system('reboot &')
    return system()

@app.route("/remote")

def remote():
    conf = getConf()
    if conf['deviceName'] == 'New Webcam\n':
        disabled = True
    else:
        disabled = False

    return render_template('remote.html', conf=conf, disabled=disabled, registered=checkIfRegistered(conf['deviceName']))

@app.route("/remoteAction", methods=["POST"])

def remoteAction():
    conf = getConf()
    registerDevice(conf['deviceName'].replace(' ','_').rstrip('\n'))
    return remote()


@app.route("/update")

def update():
    conf = getConf()
    if conf['deviceName'] == 'New Webcam\n':
        disabledDomoticsUpgrade = True
    else:
        disabledDomoticsUpgrade = not needDebianPckUpdate('domotics-qbus')
    return render_template('update.html', conf=conf, disabledDomoticsUpgrade=disabledDomoticsUpgrade)

@app.route("/updateAction", methods=["POST"])

def updateAction():
    logger.info('Sofware Update request')
    url = generatePanelURL()
    os.system('cd /tmp/;rm *.deb; wget %s/domotics-qbus.deb; dpkg -i *.deb' % url)
    logger.info('Sofware Update finished')
    logger.info('Rebooting')
    os.system('reboot &')
    return update()

@app.route("/updateActionOs", methods=["POST"])

def updateActionOs():
    logger.info('Sofware Update request')
    cmd='cd /tmp/;rm *.deb; wget %s/dolomitiLiveCamUpdate-osapps-debian%s.deb; dpkg -i *.deb' % (url, getDebianVersion())
    os.system(cmd)
    logger.info('Sofware Update finished')
    logger.info('Rebooting')
    os.system('reboot &')
    return update()

@app.route("/wirelessSelection")

def wirelessSelection():
    wlan=networks()
    wlan.scanNetworks()
    return jsonify(wlan=wlan.netList)


def getSysConfOld():
    try:
        # da rimuovere nella prossima release serve solo per riprendere la configurazione dalla rete dal file system.conf. Viene chiamata da  if __name__ == "__main__":
        fd=open('system.conf','r')
        rows=fd.readlines()
        conf = {}
        fd.close()
        if len(rows)>1:
            conf['netMode'] = 0
        else:
            conf['netMode'] = 1

        try:
            conf['ipAddress'] = rows[0].split()[2]
        except:
            conf['ipAddress'] = "192.168.1.1"
        try:
            conf['netMask']= rows[0].split()[4]
        except:
            conf['netMask']= "255.255.255.0"

        try:
            conf['gateWay']=rows[1].split()[4]
        except:
            conf['gateWay']= "192.168.1.254"

        try:
            conf['dns1']=rows[2].split()[2]
        except:
            conf['dns1']= "192.168.1.254"

        try:
            conf['dns2']=rows[3].split()[2]
        except:
            conf['dns2']= "192.168.1.253"
        conf['enableWireless'] = 0
        setSysConf(conf,'eth0',False)
        cmd('rm system.conf')
        try:
            if conf['dns1']:
                cmd('echo nameserver %s > /etc/resolv.conf' % conf['dns1'])
            if conf['dns2']:
                cmd('echo nameserver %s >> /etc/resolv.conf' % conf['dns2'])
        except:
            pass
    except:
        pass


if __name__ == "__main__":
  import setupLog, subprocess
  from wirelessDlc import networks
  setupLog.standardProfile()
  logger.info('Webserver Started')
  os.chdir(BASE_DIR)
  getSysConfOld()


remoteAction()
