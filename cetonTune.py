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
from langdetect import detect
import random
import subprocess as sb

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
orphanLoop = 0

def tuneChannel(tchannel, browseTime='none'):
	global orphanLoop
	if (orphanLoop == 1):
		ffmpegTunerCheck()
	tuned = False
	
	global tunerInUse
	if (orphanLoop <= 1):
		for tunerInstance in range(4):
			c = requests.get("http://192.168.200.1/get_var?i="+str(tunerInstance)+"&s=cas&v=VirtualChannelNumber")
			result_chan = bs(c.text, 'html.parser')
			channel = result_chan.get_text()
			if (channel != "0"):
				tuned = True
				tunerInUse = True
			else:
				tuned = False
				tunerInUse = False
			if (tunerInUse == False and tuned == False):
				my_channel = {"instance_id":str(tunerInstance),"channel":tchannel}
				r = requests.post("http://192.168.200.1/channel_request.cgi", data=my_channel)
				sleep(1)
				tunerInUser = True
				c = requests.get("http://192.168.200.1/get_var?i="+str(tunerInstance)+"&s=cas&v=VirtualChannelNumber")
				result_chan = bs(c.text, 'html.parser')
				channel = result_chan.get_text()
				print("Tuned tuner instance "+str(tunerInstance)+" to channel "+channel+" requested channel "+str(tchannel))
				sched_cmd = ['at', 'now', '-M']
				if (browseTime!='none' and int(channel) == int(tchannel)):
					program=getTunerProgram(tunerInstance)
					command = 'ffmpeg -i /dev/ctn91xx_mpeg0_%s -c:v copy -map 0:p:%s:v -map 0:p:%s:m:language:eng -c:a aac -ac 2 -t %s -f rtsp rtsp://myuser:mypass@127.0.0.1:8554/ceton%s && /home/richard/cetonTune.py tunerStop %s' % (tunerInstance, program, program, browseTime, tunerInstance, tunerInstance)
					p = subprocess.Popen(sched_cmd, stdin=subprocess.PIPE)
					p.communicate(command.encode('utf-8'))
				if (int(channel) != int(tchannel)):
					print("Tuner channel is not requested channel, will NOT setup stream.")
				if(int(channel) == int(tchannel)):
					tuned = True
					break
			else:
				print("Tuner instance "+str(tunerInstance)+" is in use or channel has already been tuned, not tuning so skipping...")
				if(tunerInstance == 3):
					print("All tuners are currently occupied, application will check if any are orphaned ;-(...")
		sleep(1)
		c = requests.get("http://192.168.200.1/get_var?i="+str(tunerInstance)+"&s=cas&v=VirtualChannelNumber")
		result_chan = bs(c.text, 'html.parser')
		channel = result_chan.get_text()
		if channel != tchannel:
			print("Tuned channel is not the requested channel.  Running tuning function again after running tuner cleanup.")
			orphanLoop = orphanLoop + 1
			tuneChannel(tchannel)
	else:
		print("No tuner is available, so will not record this show.")
		quit()
	return tunerInstance

def ffmpegTunerCheck():
	for tunerInstance in range(4):
		c = requests.get("http://192.168.200.1/get_var?i="+str(tunerInstance)+"&s=cas&v=VirtualChannelNumber")
		result_chan = bs(c.text, 'html.parser')
		channel = result_chan.get_text()
		if channel != 0:
			ffmpegCheck = subprocess.Popen( 'lsof /dev/ctn* | grep ctn91xx_mpeg0_'+str(tunerInstance)+' | wc -l', shell=True,
				stdin=subprocess.PIPE,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE)
			ffmpegResult = ffmpegCheck.stdout.readlines(-1)[0]
			if(ffmpegResult.decode('utf-8').strip() == "0"):
				sleep(15)
				ffmpegCheck = subprocess.Popen( 'lsof /dev/ctn* | grep ctn91xx_mpeg0_'+str(tunerInstance)+' | wc -l', shell=True,
					stdin=subprocess.PIPE,
					stdout=subprocess.PIPE,
					stderr=subprocess.PIPE)
				ffmpegResult = ffmpegCheck.stdout.readlines(-1)[0]
				if(ffmpegResult.decode('utf-8').strip() == "0"):
					print("Tuner instance "+str(tunerInstance)+" has not been occupied by ffmpeg for 15 seconds, releasing tuner")
					tunerStop(tunerInstance)
				else:
					print("Tuner instance "+str(tunerInstance)+" is occupied with ffmpeg, will NOT release tuner")
			else:
				print("Tuner instance "+str(tunerInstance)+" is occupied with ffmpeg, will NOT release tuner")
		else:
			sleep(15)
			print("Tuner is tuned to a requested channel, but does not have a corresponding ffmpeg call.  Releasing tuner")
			tunerStop(tunerInstance)

def getTunerProgram(tunerInstance):
	c = requests.get("http://192.168.200.1/get_var?i="+str(tunerInstance)+"&s=mux&v=ProgramNumber")
	programResult = bs(c.text, 'html.parser')
	program = programResult.get_text()
	return program

def startRTSPService(channel, start, length, show):
	tunerInstance = tuneChannel(channel)
	sleep(2)
	program = getTunerProgram(tunerInstance)
	if (program == 0):
		print("Program is set to 0 which means we do not have a signal, more than likely due to lack of authorization from cable provider headend.  We will now reset tuner.")
		tunerStop(tunerInstance)
	else:
		print("Program is set, will now start rtsp feed and call recording to start listening to rtsp server.")
		show = show.replace(" ","_")
		sched_cmd = ['at', '-M', '-t', start]
		command = 'ffmpeg -i /dev/ctn91xx_mpeg0_%s -c:v copy -map 0:p:%s:v -map 0:p:%s:m:language:eng -c:a aac -ac 2 -t %s -f rtsp rtsp://myuser:mypass@192.168.1.3:8554/ceton%s' % (tunerInstance, program, program, length, tunerInstance)
		p = subprocess.Popen(sched_cmd, stdin=subprocess.PIPE)
		p.communicate(command.encode('utf-8'))
	return tunerInstance

def startRecording(channel, start, length, episode, show):
	show = show.replace(" ","_")
	show = show.replace(":","")
	show = show.replace("?","")
	episode = episode.replace(" ","_")
	episode = episode.replace("?","")
	episode = episode.replace(":","")
	tunerInstance = startRTSPService(channel, start, length, show)
	program = getTunerProgram(tunerInstance)
	sched_cmd = ['at', '-M', '-t', start]
	command = 'ffmpeg -i rtsp://192.168.1.3:8554/ceton%s -c copy -t %s -y /mnt/primary-backup-drive/Backup/Recordings/\"%s\"-\"%s\"-%s.ts && /home/richard/cetonTune.py tunerStop %s' % (tunerInstance, length, show, episode, channel, tunerInstance)
	p = subprocess.Popen(sched_cmd, stdin=subprocess.PIPE)
	sleep(15)
	if (getTunerChannel(tunerInstance)==channel):
		p.communicate(command.encode('utf-8'))
	else:
		print('Requested channel ('+channel+') but set to '+getTunerChannel(tunerInstance)+' restarting recording process')
		startRecording(channel, start, length, episode, show)

def getTunerChannel(tunerInstance):
	c = requests.get("http://192.168.200.1/get_var?i="+str(tunerInstance)+"&s=cas&v=VirtualChannelNumber")
	result_chan = bs(c.text, 'html.parser')
	channel = result_chan.get_text()
	return channel

def scheduleRecording(channel, start, length, episode, show):
	sched_cmd = ['at', '-M', '-t', start]
	command = '/home/richard/cetonTune.py startRecording %s %s %s \"%s\" \"%s\"' % (channel, start, length, episode, show)
	command_b = bytes(command,'utf-8')
	print("Command to call for recording: "+command)
	p = subprocess.Popen(sched_cmd, stdin=subprocess.PIPE)
	p.communicate(command_b)

def tunerStatus(tunerInstance):
	global tunerInUse
	ffmpegCheck = subprocess.Popen( 'lsof /dev/ctn*| grep ctn91xx_mpeg0_'+str(tunerInstance)+' | wc -l', shell=True,
		stdin=subprocess.PIPE,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE)
	response = ffmpegCheck.stdout.readlines(-1)[0]
	if(response.decode('utf-8').strip() != "0"):
		print("ffmpegcheck responded with: "+response.decode('utf-8').strip())
		ffmpegCheck = subprocess.Popen( 'lsof /dev/ctn* | grep ctn91xx_mpeg0_'+str(tunerInstance)+' | wc -l', shell=True,
			stdin=subprocess.PIPE,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE)
		response = ffmpegCheck.stdout.readlines(-1)[0]
		print("Tuner is occupied by ffmpeg")
		print(response.decode('utf-8').strip())
	c = requests.get("http://192.168.200.1/get_var?i="+str(tunerInstance)+"&s=cas&v=VirtualChannelNumber")
	result_chan = bs(c.text, 'html.parser')
	channel = result_chan.get_text()
	if (channel == "0"):
		tunerInUse = False
		print("Tuner ("+str(tunerInstance)+") is in STOPPED state")
		if (response.decode('utf-8').strip() != "0"):
			tunerStop(tunerInstance)
	else:
		tunerInUse = True
		print("Tuner ("+str(tunerInstance)+") is in RUNNING state")
		print("Tuner ("+str(tunerInstance)+") is tuned to channel ("+result_chan.get_text()+")")
		print("Tuner is using program number: "+getTunerProgram(tunerInstance))
		sleep(5)
		if(response.decode('utf-8').strip() == "0"):
			print("Tuner is running without a ffmpeg process (orphaned tuner), stopping tuner ("+str(tunerInstance)+").")
			tunerStop(tunerInstance)
	print ("===================")
	return tunerInUse

def tunerStop(tunerInstance):
	global tunerInUse
	"""
	proc_list = sb.Popen('ps -ef', stdout=sb.PIPE).communicate()[0].splitlines()
	for pid in proc_list:
		print(pid)
	"""
	c = requests.get("http://192.168.200.1/get_var?i="+str(tunerInstance)+"&s=cas&v=VirtualChannelNumber")
	result_chan = bs(c.text, 'html.parser')
	channel = result_chan.get_text()
	if (channel == "0"):
		print("Tuner not in use, skipping")
	else:
		my_channel = {"instance_id":str(tunerInstance),"channel":0}
		r = requests.post("http://192.168.200.1/channel_request.cgi", data=my_channel)
		sleep(1)
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

def showTunerChannels():
	channels = requests.get("http://192.168.200.1/view_channel_map.cgi?page=0")
	channelsResult = bs(channels.text, 'html.parser')
	channelTable = channelsResult.find('table')
	tableRows = channelTable.find_all('tr')
	print("Channel List:")
	row = 0
	data = 0
	head = ''
	for tr in tableRows:
		tHeader = tr.find_all('th')
		for th in tHeader:
			head += th.text+'|'
		print(head)
		tDatas = tr.find_all('td')
		row += 1
		tdata = ''
		for td in tDatas:
			tdata += td.text+'|'
			data += 1
		print(tdata)
		data = 0
			

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
	return channel
	
def searchXMLChannelDesc(lchannelId):
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
	return channelName

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
		

def searchXMLGuide(searchTerm, scheduledChannel=0):
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
		if (lchannelId != channelId):
			searchXMLChannel(lchannelId)
		if ((showName.lower().find(searchTerm.strip().lower()) != -1) and (startInt >= nowInt-60) and (startDay >= todayInt) and scheduledChannel == 0):
			print(showName, episodeName, start, length_t, channelName, channel)
			record = input('Record this episode of '+showName+'(Y/N)? Record all occurrences of this show on this channel (A)? Finished (q)?')
			if (record.lower() == "yes" or record.lower() == "y"):
				scheduleRecording(channel, start, length_t, episodeName, showName)
			elif (record.lower() == "a" or record.lower() == "all"):
				scheduleShowDaily(showName, channel)
			elif (record.lower() == "q" or record.lower() == "quit"):
				break
			else:
				print("Not recording")
		if (scheduledChannel != 0 and (showName.lower().find(searchTerm.strip().lower()) != -1) and (startDay == todayInt) and scheduledChannel == channel and start >= nowStr):
			scheduleRecording(scheduledChannel, start, length_t, episodeName, searchTerm)

def scheduleShowDaily(showName, channel):
	print("Scheduling show "+showName+" daily to record if found on channel "+str(channel))
	showsFile = open("cetonShows.txt", "a")
	showsFile.write(showName+"|"+channel+"\n")
	showsFile.close()
	showsFile = open("cetonShows.txt", "r")
	print("List of shows set to be scanned for daily:")
	print(showsFile.read())
	showsFile.close

def setDailyShowJobs():
	showsFile = open("cetonShows.txt", "r")
	count = 0
	while True:
		count +=1
		show = showsFile.readline()
		if not show:
			break
		showSplit = show.split('|')
		showName = showSplit[0]
		showChannel = showSplit[1]
		print("Show: "+showName+" channel to record: "+showChannel.strip())
		searchXMLGuide(showName, showChannel.strip())

	
		

def showChannels(channelFilter):
	global root
	if (root == ""):
		root = et.parse(xmlFile)
	for channel in root.findall('channel'):
		c_channel = channel[1].text
		c_channelName = channel[2].text
		if((c_channelName.lower().find(channelFilter.strip().lower()) != -1)):
			print('Found channel: '+c_channel+' callsign: '+c_channelName)

def showMovies(cTitle):
	global root
	now = datetime.now()
	nowStr = now.strftime("%Y%m%d%H%M")
	nowint = int(nowStr)
	todayStr=now.strftime("%Y%m%d")
	todayInt=int(todayStr)
	print("Searching for: '"+str(cTitle).lower()+"' nowint is:"+str(nowint)+" nowStr is: "+nowStr)
	if(root == ""):
		root = et.parse(xmlFile)
	for movies in root.findall('programme'):
		try:
			category = movies.find('category').text
			if (category == 'Movie' and detect(movies.find('desc').text)=='en' and movies.find('title').text.lower().__contains__(str(cTitle).lower()) and int(movies.get('start')[0:12]) >= nowint ):
				title=movies.find('title').text
				year=movies.find('date').text
				desc=movies.find('desc').text
				start = str(movies.get('start'))[0:12]
				length = movies.find('length').text
				length_t = minutesToTime(length)
				channel = searchXMLChannel(movies.get('channel'))
				channelName = searchXMLChannelDesc(movies.get('channel'))
				print("Channel:"+str(channel)+"("+channelName+")@"+start[0:4]+"/"+str(start[4:6])+"/"+str(start[6:8])+"@"+str(start[8:10])+":"+str(start[10:12])+" Title: "+title+" year "+year+" desc:"+desc)
				record = input("Do you want to record this movie? (Y/N/Q)")
				if (record.lower() == "yes" or record.lower() == "y"):
					scheduleRecording(channel, start, length_t, year, title)
				elif (record.lower() == "q" or record.lower() == "quit"):
					break
				else:
					print("Not recording")
		except:
			a=1

def showFreeformMovies():
	global root
	now = datetime.now()
	nowStr = now.strftime("%Y%m%d%H%M")
	nowint = int(nowStr)
	todayStr=now.strftime("%Y%m%d")
	todayInt=int(todayStr)
	if(root == ""):
		root = et.parse(xmlFile)
	for movies in root.findall('programme'):
#		if(movies.get('channel') == 'I244.59615.zap2it.com' and movies.find('category') is not None and movies.find('category').text == 'Movie'):
#			print("Channel: "+movies.get('channel')+"Title: "+movies.find('title').text)

		if (movies.find('category') is not None):
			if (movies.find('category').text == 'Movie' and ((movies.get('channel') == 'I244.59615.zap2it.com') )and nowStr <= str(movies.get('start'))[0:12]):
				title=movies.find('title').text
				year=movies.find('date').text
				desc=movies.find('desc').text
				start = str(movies.get('start'))[0:12]
				length = movies.find('length').text
				length_t = minutesToTime(length)
				print('Title: '+title+' -year ('+year+') start@'+start+' desc:'+desc)
				record = input("Do you want to record this movie? (Y/N) or Quit (q)")
				if (record.lower() == "yes" or record.lower() == "y"):
					channel = searchXMLChannel(movies.get('channel'))
					scheduleRecording(channel, start, length_t, year, title)
				elif (record.lower() == "q" or record.lower() == "quit"):
					break
				else:
					print("Not recording")


def showSports(sport, teams):
	global root
	now = datetime.now()
	nowStr = now.strftime("%Y%m%d%H%M")
	nowint = int(nowStr)
	todayStr=now.strftime("%Y%m%d")
	todayInt=int(todayStr)
	if(root == ""):
		root = et.parse(xmlFile)
	for sports in root.findall('programme'):

		if (sports.find('category') is not None and sports.find('sub-title') is not None):
			if (sports.find('category').text == 'Sports' and (sports.find('title').text.lower().__contains__(sport) and sports.find('sub-title').text.lower().__contains__(teams))):
				title=sports.find('title').text
				subtitle=sports.find('sub-title').text
				desc=sports.find('desc').text
				start = str(sports.get('start'))[0:12]
				length = sports.find('length').text
				length_t = minutesToTime(length)
				channelId = sports.get('channel')
				channel = searchXMLChannel(channelId)
				channelName = searchXMLChannelDesc(channelId)
				print('Title: '+title+' - ('+subtitle+') channel '+channel+'('+channelName+') start@'+start+' desc:'+desc)
				record = input("Do you want to record this sports event? (Y/N) or Quit (q)")
				if (record.lower() == "yes" or record.lower() == "y"):
					scheduleRecording(channel, start, length_t, subtitle, title)
				elif (record.lower() == "q" or record.lower() == "quit"):
					break
				else:
					print("Not recording")
					continue

def displayNewShows(*searchTerm):
	global root
	print("Should be returning all new shows for next week!")
	if (root == ""):
		root = et.parse(xmlFile)
	for show in root.findall('programme'):
		if(show.findall('.//new') and (show.find('title').text.lower().find('night') == -1) and (show.find('title').text.lower().find('news') == -1) and (show.find('title').text.lower().find('sport') == -1)  and (show.find('title').text.lower().find('bloomberg') == -1) and (show.find('title').text.lower().find('morning') == -1) and (show.find('title').text.lower().find('evening') == -1) and (show.find('title').text.lower().find('ball') == -1) and (2000 <= int(str(show.get('start'))[8:12]) <= 2200) ):
			try:
				lang = detect(show.find('title').text)
				if(lang == "en" and ((str(searchXMLChannel(show.get('channel'))).lower().find('wsb')) != -1) or ((str(searchXMLChannel(show.get('channel'))).lower().find('wgcl')) != -1) or ((str(searchXMLChannel(show.get('channel'))).lower().find('wxia')) != -1) or ((str(searchXMLChannel(show.get('channel'))).lower().find('waga')) != -1) ):
					channel=show.get('channel')
					print('Detected language: '+lang+' channelid is:'+channel)
					print('Show is new: '+show.find('title').text+' @:'+str(show.get('start'))[0:12]+" channel "+str(searchXMLChannel(channel)) )
			except:
				a=1

def displayNewShowsToday(*searchTerm):
	global root
	now = datetime.now()
	todayStr=now.strftime("%Y%m%d")
	todayInt=int(todayStr)
	print("Should be returning all new shows for today!")
	if (root == ""):
		root = et.parse(xmlFile)
	for show in root.findall('programme'):
		if(show.findall('.//new') and (show.find('title').text.lower().find('night') == -1) and (show.find('title').text.lower().find('news') == -1) and (show.find('title').text.lower().find('sport') == -1)  and (show.find('title').text.lower().find('bloomberg') == -1) and (show.find('title').text.lower().find('morning') == -1) and (show.find('title').text.lower().find('evening') == -1) and (show.find('title').text.lower().find('ball') == -1) and (2000 <= int(str(show.get('start'))[8:12]) <= 2300) ):
			try:
				lang = detect(show.find('title').text)
				if(lang == "en" and ((str(searchXMLChannel(show.get('channel'))).lower().find('wsb')) != -1) or ((str(searchXMLChannel(show.get('channel'))).lower().find('wgcl')) != -1) or ((str(searchXMLChannel(show.get('channel'))).lower().find('wxia')) != -1) or ((str(searchXMLChannel(show.get('channel'))).lower().find('waga')) != -1) ):
					channel=show.get('channel')
					print('Detected language: '+lang+' channelid is:'+channel)
					print('Show is new: '+show.find('title').text+' @:'+str(show.get('start'))[0:12]+" channel "+str(searchXMLChannel(channel)) )
			except:
				a=1


if (len(sys.argv) < 2):
	print("Options are:")
	print("channelRequest (channelNumber)")
	print("initializeTuners")
	print("tunerStop (tunerInstance)")
	print("tunerStatuses")
	print("tvSearch (show/movie text)")
	print("displayNewShows")
	print("showChannels (channel filter (str))")
	print("scheduleDailyShowJobs")
	print("freeformMovies")
	print("showSports(sport, team)")
	print("showMovies(title)")
	print("displayNewShowsToday")
	print("showTunerChannels")
	sys.exit()


if (argv[1] == "channelRequest"):
	print (argv)
	print(len(argv))
	if (int(len(argv))<4):
		tunerInstance = tuneChannel(argv[2])
	else:
		tunerInstance = tuneChannel(argv[2], argv[3])
	tunerStatus(tunerInstance)
	program=getTunerProgram(tunerInstance)
	sleep(5)
	checkProgram=getTunerProgram(tunerInstance)
	if (int(program) != int(checkProgram)):
		print("Program is no longer initital tuned program for tunerInstance "+str(tunerInstance))

elif (argv[1] == "scheduleDailyShowJobs"):
	print("Setting daily show scheduled jobs")
	setDailyShowJobs()

elif (argv[1] == "displayNewShowsToday"):
	print("Displaying new shows for today on \"the Big 4 Networks\"")
	displayNewShowsToday()

elif (argv[1] == "showSports"):
	print("Searching for sports shows")
	showSports(argv[2], argv[3])

elif (argv[1] == "freeformMovies"):
	showFreeformMovies()

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

elif (argv[1] == "showMovies"):
	showMovies(str(argv[2]))

elif (argv[1] == "tvSearch"):
	searchXMLGuide(str(argv[2]))

elif (argv[1] == "startRecording"):
	'''startRecording(channel, start, length, episode, show):'''
	startRecording(str(argv[2]),str(argv[3]),str(argv[4]),str(argv[5]),"\""+str(argv[6])+"\"")
elif (argv[1] == "tunerStatuses"):
	print("Getting statuses of all tuners")
	for tunerInstance in range(4):
		tunerStatus(tunerInstance)
elif (argv[1] == "displayNewShows"):
	print("Showing new shows for next week!")
	displayNewShows()
elif (argv[1] == "showChannels"):
	print("Displaying channels")
	showChannels(str(argv[2]))
elif (argv[1] == "showTunerChannels"):
	print("Displaying Tuner Channels")
	showTunerChannels()
else:
	print("Options are:")
	print("tvSearch (show/movie text)")
	print("channelRequest (channelNumber)")
	print("initializeTuners")
	print("tunerStop (tunerInstance)")
	print("tunerStatuses")
	print("displayNewShows")
	print("showSports (sport, team)")
	print("scheduleDailyShowJobs")
	print("freeformMovies")
	print("showTunerChannels")
