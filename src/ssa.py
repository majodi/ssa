# RSSI Analyzer

import os, sys, time, threading, logging, socket, pickle
from flask import Flask, request
import matplotlib.pyplot as plt

app = Flask(__name__)

startFrequency = 868000000
endFrequency = 869000000
stepSize = 100000
powerLevel = 17
masterIP = 'not found'
masterUp = False
slaveIP = 'not found'
slaveUp = False
mFrequencies = []
mRssiValues = []
sFrequencies = []
sRssiValues = []
dataReady = False
pendingSwitch = 0
acquisition = False

def thread_srv():
    app = Flask(__name__)

    @app.route('/getInit')
    def getInit():
        global masterIP, masterUp, slaveIP, slaveUp, pendingSwitch
        if (not masterUp or request.remote_addr == masterIP):
            if (pendingSwitch):
                pendingSwitch -= 1
            else:
                masterIP = request.remote_addr
            masterUp = True
        else:
            if (not slaveUp or request.remote_addr == slaveIP):
                if (pendingSwitch):
                    pendingSwitch -= 1
                else:
                    slaveIP = request.remote_addr
                slaveUp = True
            else:
                print('\n\nmaster and slave already registered, received additional register request')
                print('\nEnter to continue...:')
                return 'refused, two devices already registered'
        print('\n\nCurrent settings uploaded to LoRa device: ' + request.remote_addr + ' (use refresh if needed)')
        print('\nEnter to continue...:')
        return 'init=[' + str(startFrequency) + ',' + str(endFrequency) + ',' + str(stepSize) + ',' + str(powerLevel) + ',' + masterIP + ',' + slaveIP + ']'

    @app.route('/error')
    def error():
        e = request.args.get('e', 'general error')
        print('\n\nan error occurred on one of the LoRa devices, check serial console!')
        print('device: ' + request.remote_addr + ', error: ' + e)
        print('\nEnter to continue...:')
        return 'reported'

    @app.route('/end')
    def end():
        global dataReady, acquisition
        print('end request')
        print(mFrequencies)
        print(mRssiValues)
        print(sFrequencies)
        print(sRssiValues)
        if mFrequencies and mRssiValues and sFrequencies and sRssiValues:
            dataReady = True
        acquisition = False
        return 'ended!'
    
    @app.route('/addReading')
    def addReading():
        global mFrequencies, mRssiValues, sFrequencies, sRssiValues
        frequency = int(request.args.get('f', 0))
        rssiValue = int(request.args.get('rssi', 0))
        print(request.remote_addr + ': ' + str(frequency) + ', ' + str(rssiValue))
        if request.remote_addr == masterIP:
            mFrequencies.append(frequency)
            mRssiValues.append(rssiValue)
        else:
            sFrequencies.append(frequency)
            sRssiValues.append(rssiValue)
        return 'added'

    app.run(host='0.0.0.0', debug=False, use_reloader=False)

def signalStateChange():
    input('Update devices, enter to continue')
    device = socket.socket()
    device.connect((masterIP, 80))
    device.send(bytes([1]))
    device.close()
    time.sleep(0.2)
    device = socket.socket()
    device.connect((slaveIP, 80))
    device.send(bytes([1]))
    device.close()
    time.sleep(0.2)
    return

def acquireData():
    global mFrequencies, mRssiValues, sFrequencies, sRssiValues
    mFrequencies = []
    mRssiValues = []
    sFrequencies = []
    sRssiValues = []
    device = socket.socket()
    device.connect((masterIP, 80))
    device.send(bytes([2]))
    device.close()
    time.sleep(0.2)
    return

def menu(menu = 'm'):
    global masterIP, masterUp, slaveIP, slaveUp, startFrequency, endFrequency, stepSize, dataReady, mFrequencies, mRssiValues, sFrequencies, sRssiValues, pendingSwitch, acquisition, powerLevel
    quit = False
    message = ''
    while (not quit):
        os.system('cls||clear')
        if (message):
            print(message)
            print()
            message = ''
        if (menu == 'm'):
            print('master LoRa device: ' + (masterIP if (masterUp) else 'pending'))
            print('slave  Lora device: ' + (slaveIP if (slaveUp) else 'pending'))
            if (masterUp and slaveUp):
                print('([s] switch master/slave)')
                print()
                print('[c] configure')
                print('[a] acquire data')
                print('[l] load data from file')
                if (dataReady):
                    print('[p] plot data')
                    print('[w] write data to file')
            else:
                print()
                print('need two LoRa devices to perform data acqisition')
                print('check if devices are up with the right settings, reset them and then refresh')
                print()
                print('[r] refresh')
                print()

            print('[q] quit')
        if (menu == 'c'):
            print('[b] begin frequency (Hz): ' + str(startFrequency))
            print('[e] end frequency (Hz): ' + str(endFrequency))
            print('[s] step size (Hz): ' + str(stepSize))
            print('[p] power level: ' + str(powerLevel))
            print()
            print('[r] return to main')
        print()
        if acquisition:
            input('acquiring, enter to continue')
        else:
            command = input('Command:')
            if (menu == 'm'):
                if (command == 's'):
                    if (masterUp and slaveUp):
                        tmp = masterIP
                        masterIP = slaveIP
                        slaveIP = tmp
                        pendingSwitch = 2
                        masterUp = False
                        slaveUp = False
                        signalStateChange()
                        continue
                if (command == 'c'):
                    menu = 'c'
                    continue
                if (command == 'a'):
                    print('acquire')
                    dataReady = False
                    acquisition = True
                    acquireData()
                    message = 'data acquisition command sent, waiting for end of acquisition'
                    continue
                if (command == 'l'):
                    print('load data from file')
                    fileName = input('file name:')
                    try:
                        with open (fileName, 'rb') as fp:
                            mFrequencies = pickle.load(fp)
                            mRssiValues = pickle.load(fp)
                            sFrequencies = pickle.load(fp)
                            sRssiValues = pickle.load(fp)
                            if mFrequencies and mRssiValues and sFrequencies and sRssiValues:
                                dataReady = True
                    except Exception as e:
                        message = e
                    continue
                if (command == 'p' and dataReady):
                    print('plot')
                    plt.plot(mFrequencies, mRssiValues, 'r')
                    plt.plot(sFrequencies, sRssiValues, 'g')
                    plt.show()
                    continue
                if (command == 'w' and dataReady):
                    print('write data to file')
                    fileName = input('file name:')
                    try:
                        with open(fileName, 'wb') as fp:
                            pickle.dump(mFrequencies, fp)
                            pickle.dump(mRssiValues, fp)
                            pickle.dump(sFrequencies, fp)
                            pickle.dump(sRssiValues, fp)
                    except Exception as e:
                        message = e
                    continue
                if (command == 'r'):
                    print('resfresh')
                    continue
                if (command == 'q'):
                    quit = True
                    continue
                if (command == '!'):
                    print('Debug mode')
                    mFrequencies = [868000000, 868100000, 868200000]
                    mRssiValues = [-55, -63, -60]
                    sFrequencies = [868000000, 868100000, 868200000]
                    sRssiValues = [-57, -66, -61]
                    dataReady = True
                    masterUp = True
                    slaveUp = True
                    message = 'debug values loaded'
                    continue
                if (command == ''):
                    continue
                message = 'invalid command'
            if (menu == 'c'):
                if (command == 'b'):
                    value = input('begin frequency (Hz):')
                    startFrequency = int(value) if value.isdigit() else startFrequency
                    nothingChanged = False
                    continue
                if (command == 'e'):
                    value = input('end frequency (Hz):')
                    endFrequency = int(value) if value.isdigit() else endFrequency
                    nothingChanged = False
                    continue
                if (command == 's'):
                    value = input('step size (Hz):')
                    stepSize = int(value) if value.isdigit() else stepSize
                    nothingChanged = False
                    continue
                if (command == 'p'):
                    value = input('power level:')
                    powerLevel = int(value) if value.isdigit() else powerLevel
                    nothingChanged = False
                    continue
                if (command == 'r'):
                    if nothingChanged:
                        menu = 'm'
                    else:
                        nothingChanged = True
                        if ((startFrequency > 0 and endFrequency > 0 and stepSize > 0) and\
                            (endFrequency > startFrequency) and\
                            ((endFrequency - startFrequency) > stepSize)):
                            signalStateChange()
                            menu = 'm'
                            input()
                        else:
                            message = 'Invalid parameters, check that end is larger then begin and that there is room for at least one step in between'
                            menu = 'c'
                    continue
                if (command == ''):
                    continue
                message = 'invalid command'

if __name__ == '__main__':
    log = logging.getLogger('werkzeug')
    log.disabled = True
    os.environ['WERKZEUG_RUN_MAIN'] = 'true'
    t_srv = threading.Thread(name='ssa server', target=thread_srv)
    t_srv.setDaemon(True)
    t_srv.start()
    menu()
    print('bye...')
    exit(0)
