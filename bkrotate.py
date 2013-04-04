#!/usr/bin/python
###########################################################
# bkrotate.py <stemartincouk@gmail.com>                   #
#                                                         #
# A python script to do simple backups and retention      #
#                                                         #
###########################################################
# Copyright (c) 2013, Stephen Martin
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. All advertising materials mentioning features or use of this software
#    must display the following acknowledgement:
#    This product includes software developed by Stephen Martin.
# 4. Neither the name of the <organization> nor the
#    names of its contributors may be used to endorse or promote products
#    derived from this software without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS ''AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HILDERS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#Changelog
#0.5 introduced logging.
#0.6 Checking of backup and source locations prior to run.

conf={
'sourceDir':"/home/stephenm/Code/bkrotate/testing/source/",
'backupDir':"/home/stephenm/Code/bkrotate/testing/backup/",
'retention':60,
'alertDiskUsage':85, #version 0.4 or above only. percentage of disk that can be used before alert is raised. Must be an int eg. 85
'email_from':"bkrotate@lste.local",
'email_to':"s.martin@cmyk-digital.co.uk",
'smtp_server':"127.0.0.1",
'send_notifications':1,
'debug':0, # for debugging when errors occur with operation can be set integer 1 or 0,
'verbose':1, # for extra standard output, can be ser integer 1 or 0
'logFile':"./bkrotate.log"
}

#DO NOT EDIT ANYTHING UNDER HERE UNLESS YOU KNOW WHAT YOU ARE DOING.
versionNumber="0.6"
import os
import os.path
import re
import zipfile
import datetime
import smtplib
import sys
import platform
import ctypes
import collections
import signal

shutdown = False

class Logger:

    def __init__(self):
        #check if log file exists.
        if not os.path.isfile(self.logFile):
            sys.exit("No log file exists please create bkrotate.log in you log file location: "+conf['logFile'])
        self.log_message('init','LOG SYSTEM INIT =============================================')

    logFile =conf['logFile']
    type="general"
    msg=""
    def log_message(self,type,msg):

        self.type=type
        self.msg=msg
        line=datetime.datetime.now().strftime("%d/%m/%y-%H:%M:%S")+" ["+self.type+"] "+self.msg
        with open(self.logFile,'a') as lf:
            lf.write(line+'\n')
            lf.close()

bklogger=Logger()

def handleSigINT():
    bklogger.log_message("run","Caught term signal shutting down early")
    shutdown = True


signal.signal(signal.SIGINT, handleSigINT)





_ntuple_diskusage = collections.namedtuple('usage', 'total used free')
class archive:
    fileName=""
    created=""
    modified=""
    size=0 #bytes
    fileName="confSourceDir"
    sourceDir=conf['sourceDir']
    backupDir=conf['backupDir']
    createdDate=None
    errorList=[]
    skipList=[]

    def __str__(self):
        return "Archive"

    def is_archive(self,fileName):
        if conf['debug']==1:
            print "DEBUG: Testing if "+fileName+"is an archive using regex"
        regex = re.compile("-[0-9][0-9][0-9][0-9][0-9][0-9]-backup\.zip")
        if len(regex.findall(fileName))==1:
            if conf['debug']==1:
                print fileName+"DEBUG: is a valid archive"
            return True
        else:
            if conf['debug']==1:
                print fileName+"DEBUG is not a valid archive"
            return False
    def populate(self,fileName):
        if self.is_archive(fileName):
            self.modified = os.stat(fileName).st_mtime
            self.fileName = fileName
            self.size = os.path.getsize(fileName)
    def create(self):
        try:
            self.createdDate = datetime.datetime.now()
            self.fileName = os.path.basename(conf['sourceDir'])+self.createdDate.strftime("-%d%m%y")+'-backup.zip'
            zip = zipfile.ZipFile(os.path.join(self.backupDir,self.fileName), 'w', zipfile.ZIP_DEFLATED,True)
            rlen = len(self.sourceDir)
            for base, dirs, files in os.walk(self.sourceDir):
                if shutdown:
                    break
                for file in files:

                    if conf['verbose']==1:
                        print "Archiving: "+str(file)
                    fn = os.path.join(base, file)
                    try:
                        if shutdown:
                            print "Shutdown caught!"
                            break
                        zip.write(fn, fn[rlen:])
                    except Exception,err:
                        self.skipList.append(fn)
        except Exception,e:
            print e
            return False
        if len(self.errorList)==0:
            return True

class library:
    archives=[]
    totalSize=0
    forecastTotalSizeRequired=None
    forecastTotalDiskUsage=None
    backupDiskSize = None
    backupDiskUsed = None
    backupDiskUsage = None

    #http://code.activestate.com/recipes/577972-disk-usage/
    def disk_usage(self,path):
        _, total, free = ctypes.c_ulonglong(), ctypes.c_ulonglong(),ctypes.c_ulonglong()
        if sys.version_info >= (3,) or isinstance(path, unicode):
            fun = ctypes.windll.kernel32.GetDiskFreeSpaceExW
        else:
            fun = ctypes.windll.kernel32.GetDiskFreeSpaceExA
        ret = fun(path, ctypes.byref(_), ctypes.byref(total), ctypes.byref(free))
        if ret == 0:
            raise ctypes.WinError()
        used = total.value - free.value
        return _ntuple_diskusage(total.value, used, free.value)
    #end
    def __init__(self):
        self.get_disk_capacity()
        self.get_disk_used()
        self.backupDiskUsage = 100*float(self.backupDiskUsed)/float(self.backupDiskSize)
    def get_disk_capacity(self):
        if platform.system() == 'Windows':

            self.backupDiskSize = self.disk_usage(conf['backupDir'])[0]
        else:
            disk = os.statvfs(conf['backupDir'])
            self.backupDiskSize = float(disk.f_bsize*disk.f_blocks)

    def get_disk_used(self):
        if platform.system() == 'Windows':

            self.backupDiskUsed = self.disk_usage(conf['backupDir'])[1]
        else:
            disk = os.statvfs(conf['backupDir'])
            self.backupDiskUsed= float(disk.f_bsize*(disk.f_blocks-disk.f_bfree))

    def get_available_space(self):
        if platform.system() == 'Windows':
            #free_bytes = ctypes.c_ulonglong(0)
            #ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(conf['backupDir']), None, None, ctypes.pointer(free_bytes))
            return self.disk_usage(conf['backupDir'])[2]
        else:
            stat = os.statvfs(conf['backupDir'])
            return stat.f_bsize * stat.f_bavail


    def get_library(self):
        for fName in os.listdir(conf['backupDir']):
            ark = archive()
            if ark.is_archive(fName):
                ark.populate(os.path.join(conf['backupDir'],fName))
                self.archives.append(ark)
                self.totalSize = self.totalSize + ark.size

    def print_library(self):
        print "Found the following archives...."
        print "--------------------------------"
        for ark in self.archives:
            print ark.fileName+" | "+str(ark.modified)+" | "+str(ark.size)+" Bytes ("+sizeof_fmt(ark.size)+")"
        print "--------------------------------"
        print "Total "+str(len(self.archives))+" Files, Total Size: "+str(self.totalSize)+" Bytes ("+str(sizeof_fmt(self.totalSize))+") /  Available space: "+str(self.get_available_space())+" Bytes ("+sizeof_fmt(self.get_available_space())+")"

    def prune_library(self):
        if conf['verbose']==1:
            print "Pruning library."
        if len(self.archives)==0:
            self.get_library()
        if conf['debug']==1:
            print "DEBUG: Sorting archives"
            self.archives.sort(key=lambda x: x.modified, reverse=True)
            self.print_library()

        if len(self.archives)>conf['retention']:
            if conf['verbose']==1:
                print "Over retention limit of: "+str(conf['retention'])
            # We are over limit we need to delete the oldest.
            #how many are we over by
            overBy = len(self.archives) - conf['retention']
            overByInverted = overBy - (2* overBy)
            if conf['debug']==1:
                print "DEBUG: overBy = "+str(overBy)
                print "DEBUG: overByInverted = "+str(overByInverted)
            #these are the archives to be pruned
            for ark in self.archives[overByInverted:]:
                if conf['verbose']:
                    print "Deleting "+ark.fileName
                os.remove(ark.fileName)
        else:
            #we are not over retention limit
            if conf['verbose']==1:
                print "We are not over the retention limit of: "+str(conf['retention'])+" nothing to prune"
    def forecast(self):
        self.get_available_space()
        if len(self.archives)==0:
            self.get_library()
        if not len(self.archives)>0:
            return True
        self.archives.sort(key=lambda x: x.size, reverse=True)
        ark = self.archives[0]
        self.forecastTotalSizeRequired = ark.size * conf['retention']
        self.forecastTotalDiskUsage = 100*float(self.forecastTotalSizeRequired)/float(self.get_available_space())
        #current largest archive times the retention limit is our forcasted total space needed.
        if conf['debug']==1:
            print "Sorted library by size"
            self.print_library()
            print "largest file is: "+ark.fileName+" SIZE:"+str(ark.size)
            print "Forcasted total size needed is "+str(self.forecastTotalSizeRequired)+" Bytes, "+sizeof_fmt(self.forecastTotalSizeRequired)
            print "Forcasted total disk usage: "+("%.2f" % self.forecastTotalDiskUsage)+"%."
        #if (self.get_available_space - self.forecastTotalSizeRequired) < (self.get_available_space / 10):
            #we are estimated to have under 10% capaicty left
            print "DISK USAGE ACTIVE STATE"+str(self.disk_usage(conf['backupDir']))

class mailer:
    mailFrom=conf['email_from']
    rcptTo=conf['email_to']
    subject=""
    body=""
    smtpserver = None

    def send_message(self):
        try:
            self.smtpserver = smtplib.SMTP(conf['smtp_server'])
            header = 'To:' +self.rcptTo+'\n'+'From: '+self.mailFrom+'\n'+'Subject:'+self.subject+' \n'
            msg = header +self.body+' \n\n'
            self.smtpserver.sendmail(self.mailFrom, self.rcptTo, msg)
            self.smtpserver.close()
            return True
        except Exception,e:
            return False

#Converts from bytes to human readable
# From http://stackoverflow.com/questions/1094841/reusable-library-to-get-human-readable-version-of-file-size
def sizeof_fmt(num):
    for x in ['bytes','KB','MB','GB']:
        if num < 1024.0:
            return "%3.1f%s" % (num, x)
        num /= 1024.0
    return "%3.1f%s" % (num, 'TB')
# Do operation overides first and exit early
if len(sys.argv) > 1:
    if "-h" in sys.argv:
        print "pyton bkrotate.py [options]"
    if "-p" in sys.argv:
        arkLib = library()
        arkLib.get_library()
        arkLib.print_library()
    if "-f" in sys.argv:
        print "running forecast"
        arklib = library()
        arklib = arklib.forecast()
    sys.exit(0)


bklogger.log_message('run','Starting run')
#check if the source and backup are available
if not os.path.isdir(conf['sourceDir']):
	bklogger.log_message('error','Could not find the source directory '+conf['sourceDir'])
	ma = mailer()
	ma.subject="Backup Notification: Backup FAILURE."
	ma.body="Your backup did not run successfully the reason is below. \n Error could not find the source directory "+conf['sourceDir']
	if not ma.send_message():
            if conf['verbose']:
                print "WARNING: Could not send email check you mail server settings."
                bklogger.log_message('warn','Could not send email check you mail server settings.')
	sys.exit("Error could not find the source directory "+conf['sourceDir'])
if not os.path.isdir(conf['backupDir']):
	bklogger.log_message('error','Could not find the backup destination directory / disk '+conf['backupDir'])
	ma = mailer()
	ma.subject="Backup Notification: Backup FAILURE."
	ma.body="Your backup did not run successfully the reason is below. \n Error could not find the backup destination directory / disk "+conf['backupDir']
	if not ma.send_message():
            if conf['verbose']:
                print "WARNING: Could not send email check you mail server settings."
                bklogger.log_message('warn','Could not send email check you mail server settings.')
	sys.exit("Error could not find the backup destination directory / disk  "+conf['backupDir'])
ark = archive()
arkLib = library()
arkLib.get_library()
if conf['verbose']==1:
    print "Starting backup"
if ark.create():
    arkLib.prune_library()
    arkLib.forecast()
    forecastStr="You are currently using: "+sizeof_fmt(arkLib.totalSize)+" for backups.\n You have: "+sizeof_fmt(arkLib.get_available_space())+" space available on the backup drive.\n"
    forecastStr=forecastStr+"\n You are forcasted to need: "+sizeof_fmt(arkLib.forecastTotalSizeRequired)+" to hold "+str(conf['retention'])+" backups of your largest archive so far.\nThis will eventually take up "+("%.2f" % arkLib.forecastTotalDiskUsage)+"%."+"of your total backup drive."

    if conf['send_notifications']>0:
        if conf['verbose']:
            print "sending successful notification email."
        ma = mailer()
        ma.subject="Backup Notification: Backup Completed succesfully."
        ma.body="Your backup was created successfully.\n\n"+forecastStr
        if not ma.send_message():
            if conf['verbose']:
                print "WARNING: Could not send success notification email check you mail server settings."
    if conf['verbose']==1:
        print "Backup created: "+ark.fileName
else:
    #there was a problem with the backup
    arkLib.forecast()
    forecastStr="You are currently using: "+sizeof_fmt(arkLib.totalSize)+" for backups.\n You have: "+sizeof_fmt(arkLib.get_available_space())+" space available on the backup drive.\n"
    forecastStr=forecastStr+"\n You are forcasted to need: "+sizeof_fmt(arkLib.forecastTotalSizeRequired)+" to hold "+str(conf['retention'])+" backups of your largest archive so far.\nThis will eventually take up "+("%.2f" % arkLib.forecastTotalDiskUsage)+"%."+"of your total backup drive."
    errorListStr=""
    for error in ark.skipList:
        skipListStr = skipListStr +error+"\n"
    if conf['send_notifications']>0:
        if conf['verbose']:
            print "sending failure notification email."
        ma = mailer()
        ma.subject="Backup Notification: Backup FAILURE."
        ma.body="Your backup did not run successfully the following files were skipped and have not been backed up.\n"+skipListStr+"\n\n"+forecastStr
        if not ma.send_message():
            if conf['verbose']:
                print "WARNING: Could not send failure notification email check you mail server settings."
    sys.exit("There was a failure archiving exiting. You may have a part archived backup")
#okay the backup is done lets look at the forecast and send and email if we need to.
if conf['verbose']:
    print "Backup disk usage: "+str(int(arkLib.backupDiskUsage))+"%"
if int(arkLib.backupDiskUsage) >= conf['alertDiskUsage']:
    #print "We are over the disk usage limit set in the config alert will be raised."
    #email warning at disk usage limit.
    if conf['send_notifications']>0:
        if conf['verbose']:
            print "sending over disk usage limit notification email."
        ma = mailer()
        ma.subject="Backup Alert: You are over your backup disk usage limit."
        ma.body="You are currently over your backup disk usage limit."+"\n\n Current usage:"+str(int(arkLib.backupDiskUsage))+"%.\n Your limit:"+str(conf['alertDiskUsage'])+"%."
        if not ma.send_message():
            if conf['verbose']:
                print "WARNING: Could not send disk usage alert notification email check you mail server settings."
                bklogger.log_message('warn','Could not send disk usage alert notification email check you mail server settings.')
        bklogger.log_message('warn',"You are currently over your backup disk usage limit."+" Current usage:"+str(int(arkLib.backupDiskUsage))+"%. Your limit:"+str(conf['alertDiskUsage'])+"%.")
else:
    bklogger.log_message('info','We are under disk usage limit for the backup disk.')
    #print "We are under disk usage limit for the backup disk"
if int(arkLib.backupDiskUsage) < conf['alertDiskUsage'] and arkLib.forecastTotalDiskUsage >= conf['alertDiskUsage']:
    #print "We are forecast to be over the disk usage limit set in the config alert will be raised."
    #email warning forecast  at disk usage limit.
    if conf['send_notifications']>0:
        if conf['verbose']:
            print "sending over disk usage limit notification email."
        ma = mailer()
        ma.subject="Backup Alert: You are forecast to be over your disk usage limit."
        ma.body="You are not currently over you disk usage. However it has been calcualted that retaining "+str(conf['retention'])+" copys of your largest archive would put you over your limit."+"\n\n Current usage:"+str(int(arkLib.backupDiskUsage))+"%.\n Forecast usage:"+str(int(arkLib.forecastTotalDiskUsage))+"%\n Your limit:"+str(conf['alertDiskUsage'])+"%."
        if not ma.send_message():
            if conf['verbose']:
                print "WARNING: Could not send disk usage alert notification email check you mail server settings."
        bklogger.log_message('warn','Disk usage forcast shows not enough room to furfill entire quota.')
else:
    #print "We are under disk usage limit for the backup disk"
    bklogger.log_message('info','Disk usage forcast shows enough room to furfill entire quota.')
bklogger.log_message('run','Run finished without error.')
