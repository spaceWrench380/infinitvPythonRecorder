#!/usr/bin/python3

import requests
import sys
from sys import argv
from bs4 import BeautifulSoup as bs
from time import sleep
import calendar
import time
import xml.etree.ElementTree as et
import subprocess
from datetime import datetime
import builtins
import getpass

#Parameter 1 will be the action for the program to take: channelRequest, initializeTuners, stopTuner
#Parameter 2 will be the channel requested if applicable
#Parameter 3 will be the tuner to take the action of, only applies to stopping the RTP server, starting and channel changing will be determined by active tuners

r = ""
tunerStatusFile = open('.cetonTunerStatus','w')
#print(tunerStatusFile)
tunerInstance = 0
tunerInUse = False
channel = ""
xmlFile = "/mnt/primary-backup-drive/Backup/Movies/Development/data/xmltv.xml"
root = ""
channelId = ""
channel = 0
channelName = ""

def tuneChannel(tchannel, *episode):
	tuned = False
	for tunerInstance in range(4):
		c = requests.get("http://192.168.200.1/get_var?i="+str(tunerInstance)+"&s=cas&v=VirtualChannelNumber")
		result_chan = bs(c.text, 'html.parser')
		channel = result_chan.get_text()
		if (tchannel == channel):
			print("Tuner ("+str(tunerInstance)+") is already tuned to channel ("+str(channel)+") will not continue tuning process...")
			break
		else:
			if (channel != "0"):
				tuned = True
				tunerInUse = True
			else:
				tuned = False
				tunerInUse = False
			if (tunerInUse == False & tuned == False):
				my_channel = {"instance_id":str(tunerInstance),"channel":tchannel}
				r = requests.post("http://192.168.200.1/channel_request.cgi", data=my_channel)
				c = requests.get("http://192.168.200.1/get_var?i="+str(tunerInstance)+"&s=cas&v=VirtualChannelNumber")
				result_chan = bs(c.text, 'html.parser')
				channel = result_chan.get_text()
				print("Tuned tuner instance "+str(tunerInstance)+" to channel "+channel+" requested channel "+str(argv[2]))
				tuned = True
				break
			else:
				print("Tuner instance "+str(tunerInstance)+" is in use or channel has already been tuned, not tuning so skipping...")
				if(tunerInstance == 3):
					print("All tuners are currently in use...")
					r = ":-(..."
		sleep(1)
	return tunerInstance

def startRecording(channel, start, length, episode, show):
	tunerInstance = tuneChannel(channel)
	sched_cmd = ['at', '-t', start]
	command = 'ffmpeg -i /dev/ceton/ctn91xx_mpeg0_%s -c copy -t %s /mnt/primary-backup-drive/Backup/Recordings/%s-%s-%s.mp4' % (tunerInstance, length, show, episode, channel)
	p = subprocess.Popen(sched_cmd, stdin=subprocess.PIPE)
	p.communicate(command)



def tunerStatus(tunerInstance):
	global tunerInUse
	c = requests.get("http://192.168.200.1/get_var?i="+str(tunerInstance)+"&s=cas&v=VirtualChannelNumber")
	result_chan = bs(c.text, 'html.parser')
	channel = result_chan.get_text()
	if (channel == "0"):
		tunerInUse = False
		print("Tuner ("+str(tunerInstance)+") is in STOPPED state")
	else:
		tunerInUse = True
		print("Tuner ("+str(tunerInstance)+") is in RUNNING state")
		print("Tuner ("+str(tunerInstance)+") is tuned to channel ("+result_chan.get_text()+")")
	return tunerInUse

def tunerStop(tunerInstance):
	global tunerInUse
	c = requests.get("http://192.168.200.1/get_var?i="+str(tunerInstance)+"&s=cas&v=VirtualChannelNumber")
	result_chan = bs(c.text, 'html.parser')
	channel = result_chan.get_text()
	if (channel == "0"):
		print("Tuner not in use, skipping")
	else:
		my_channel = {"instance_id":str(tunerInstance),"channel":0}
		r = requests.post("http://192.168.200.1/channel_request.cgi", data=my_channel)
		sleep(1/100)
		c = requests.get("http://192.168.200.1/get_var?i="+str(tunerInstance)+"&s=cas&v=VirtualChannelNumber")
		result_chan = bs(c.text, 'html.parser')
		channel = result_chan.get_text()
		print("Tuned tuner instance "+str(tunerInstance)+" to channel "+channel)

def tunersInitialize():
	global tunerInUse
	for tunerInstance in range(4):
		tunerStatus(tunerInstance)
		tunerStop(tunerInstance)
		tunerStatus(tunerInstance)

def RTPServerStatus(tunerInstance):
	state = requests.get("http://192.168.200.1/get_var?i="+str(tunerInstance)+"&s=av&v=TransportState")
	resultState = bs(state.text, 'html.parser')
	rtpState = resultState.get_text()
	print("RTP server for tuner("+str(tunerInstance)+") is: "+str(rtpState))

def enableRTPServer(tunerInstance):
	print("Instance number: "+str(tunerInstance))
	targetPort = 8000 + int(tunerInstance)
	params = {"instance_id":str(tunerInstance),"dest_id":"192.168.200.2","dest_port":str(targetPort),"protocol":"0","start":"1"}
	r = requests.post("http://192.168.200.1/stream_request.cgi", data=params)
	print(r)
	RTPServerStatus(tunerInstance)

def disableRTPServer(tunerInstance):
	targetPort = 8000 + int(tunerInstance)
	portString = str(targetPort)
	tunerString = str(tunerInstance)
	params = {"instance_id":tunerString,"dest_id":"192.168.200.2","dest_port":portString,"protocol":"0","start":"0"}
	r = requests.post("http://192.168.200.1/stream_request.cgi", data=params)
	print(r)
	RTPServerStatus(tunerInstance)

def searchXMLChannel(lchannelId):
	global xmlFile
	global root
	global channel
	global channelId
	global channelName
	for channels in root.findall('channel'):
		currentChannelID = channels.get('id')
		if(currentChannelID == lchannelId):
			channel = channels[1].text
			channelName = channels[2].text
			channelId = currentChannelID

def minutesToTime(minutes):
	minutes = int(minutes)
	hours = minutes // 60
	if (hours==0):
		hours="00"
	elif (hours<10):
		hours="0"+str(hours)
	o_minutes = minutes % 60
	if (o_minutes < 10):
		o_minutes="0"+str(o_minutes)
	seconds="00"
	time = "{}:{}:{}".format(str(hours), str(o_minutes),seconds)
	return time
		

def searchXMLGuide(searchTerm, *record):
	global xmlFile
	global root
	global channel
	global channelId
	global channelName
	now = datetime.now()
	nowStr = now.strftime("%Y%m%d%H%M")
	nowInt = int(nowStr)
	todayStr = now.strftime("%Y%m%d")
	todayInt = int(todayStr)
	if (root==""):
		root=et.parse(xmlFile)
	for episode in root.findall('programme'):
		showName = episode.find('title').text
		start = str(episode.get('start'))[0:12]
		episodeName = episode.find('episode-num').text
		lengthTag = episode.find('length')
		length = episode.find('length').text
		length_t = minutesToTime(length)
		unit = lengthTag.get('units')
		stop = episode.get('stop')
		startDay = int(start[0:8])
		startInt = int(start)
		lchannelId = episode.get('channel')
		if ((showName.lower().find(searchTerm.strip().lower()) != -1) and (startInt >= nowInt) and (startDay == todayInt)):
			if (lchannelId != channelId):
				searchXMLChannel(lchannelId)
			print(showName, episodeName, start, length_t, channelName, channel)
			
			record = input('Record this episode of '+showName+'(Y/N)?')
			if (record.lower() == "yes" or record.lower() == "y"):
				startRecording(channel, start, length_t, episodeName, showName)
			else:
				print("Not recording")
			
if (len(sys.argv) < 2):
	print("Options are:")
	print("channelRequest (channelNumber)")
	print("initializeTuners")
	print("tunerStop (tunerInstance)")
	print("tunerStatuses")
	print("tvSearch (show/movie text)")
	sys.exit()


if (argv[1] == "channelRequest"):
	tuneChannel(argv[2])
	for tunerInstance in range(4):
		tunerStatus(tunerInstance)

elif (argv[1] == "initializeTuners"):
	print("Entered initializeTuners action argument")
	tunersInitialize()

elif (argv[1] == "tunerStop"):
	print("Entered stopTuner action argument")
	print("Stopping tuner "+str(argv[2]))
	tunerStop(str(argv[2]))
	disableRTPServer(argv[2])

elif (argv[1] == "RTPStop"):
	disableRTPServer(str(argv[2]))
	RTPServerStatus(str(argv[2]))

elif (argv[1] == "tvSearch"):
	searchXMLGuide(str(argv[2]))
	
elif (argv[1] == "tunerStatuses"):
	print("Getting statuses of all tuners")
	for tunerInstance in range(4):
		tunerStatus(tunerInstance)
else:
	print("Options are:")
	print("tvSearch (show/movie text)")
	print("channelRequest (channelNumber)")
	print("initializeTuners")
	print("tunerStop (tunerInstance)")
	print("tunerStatuses")
