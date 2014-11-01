#!/usr/bin/env python
# TO DO:
# - Fixing encoding and parsing issues
# - Adding tv_grab standard options
#   --config-file
# - Using a temporary file to save user province, channels and epg days, so we save time in each execution

# Stardard tools
import sys
import os
import re
import logging
import json
import argparse

# Time handling
import time
import datetime
from datetime import timedelta

#Threading
import threading


# XML
import urllib
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element, SubElement, Comment, ElementTree, dump

# ese's tva lib
from tva import TvaStream, TvaParser


def parse_day(n,xmltv,rawclist):
    i = n + 130
    logger.info("\nReading day " + str(i - 130) +"\n")
    epgstream = TvaStream('239.0.2.'+str(i),MCAST_PORT)
    epgstream.getfiles()
    for i in epgstream.files().keys():
        logger.info("Parsing "+i)
        epgparser = TvaParser(epgstream.files()[i])
        epgparser.parseepg(OBJ_XMLTV,rawclist)
    return

parser = argparse.ArgumentParser()
parser.add_argument("--description",
                    help="show 'Spain: Movistar IPTV grabber'",
                    action="store_true")
parser.add_argument("--capabilities",
                    help="show xmltv capabilities",
                    action="store_true")
parser.add_argument("--quiet",
                    help="Suppress all progress information. The grabber shall only print error-messages to stderr.",
                    action="store_true")
parser.add_argument("--output",
                    help="Redirect the xmltv output to the specified file. Otherwise output goes to stdout.",
                    action="store",
                    dest="filename")
# add default="/tmp/tv_grab_es_movistar.xml" above to save to a
# default file
parser.add_argument("--days",
                    action = "store",
                    type = int,
                    dest = "grab_days",
                    help = "Supply data for X days. Grabber may have an upper limit to the number of days that it can return data for. If X is larger than that limit, the grabber shall return no data for the days that it lacks data for, print a warning to stderr, and exit with an error-code. See XmltvErrorCodes. In other words, if too many days are requested, the grabber will return data for as many days as it can. The default number of days is 'as many as possible'",
                    default = 6)
parser.add_argument("--offset",
                    action = "store",
                    type = int,
                    dest = "grab_offset",
                    help = "Start with data for day today plus X days. The default is 0, today; 1 means start from tomorrow, etc. ",
                    default = 0)
#parser.add_argument("--config-file",
#                    action="store",
#                    dest="config_file",
#                    help = "The grabber shall read all configuration data from the specified file.")
parser.add_argument("--m3u",
                    help = "Dump channels in m3u format",
                    action = "store_true")



args = parser.parse_args()

if args.description:
    print "Spain: Movistar IPTV grabber"
elif args.capabilities:
    print "baseline"
else:
    logger = logging.getLogger('movistarxmltv')
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # log to file
    fh = logging.FileHandler('/tmp/movistar.log')
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # log to console
    if not args.quiet:
        ch = logging.StreamHandler()
        ch.setLevel(logging.ERROR)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    reload(sys)

    clientprofile = json.loads(urllib.urlopen("http://172.26.22.23:2001/appserver/mvtv.do?action=getClientProfile").read())['resultData']
    platformprofile = json.loads(urllib.urlopen("http://172.26.22.23:2001/appserver/mvtv.do?action=getPlatformProfile").read())['resultData']
    DEMARCATION =  clientprofile["demarcation"]
    TVPACKAGES = clientprofile["tvPackages"].split("|")
    MCAST_GRP_START = platformprofile["dvbConfig"]["dvbEntryPoint"].split(":")[0]
    MCAST_PORT = int(platformprofile["dvbConfig"]["dvbEntryPoint"].split(":")[1])
    logger.info("Init. DEM="+str(DEMARCATION)+" TVPACKS="+str(TVPACKAGES)+" ENTRY_MCAST="+MCAST_GRP_START+":"+str(MCAST_PORT))

    ENCODING_EPG = 'utf-8'
    ENCODING_SYS = sys.getdefaultencoding()
    sys.setdefaultencoding(ENCODING_EPG)

    # Main starts

    demarcationstream = TvaStream(MCAST_GRP_START,MCAST_PORT)
    demarcationstream.getfiles()
    demarcationxml = demarcationstream.files()["1_0"]

    logger.info("Getting channels source for DEM: "+str(DEMARCATION))
    MCAST_CHANNELS = TvaParser(demarcationxml).get_mcast_demarcationip(DEMARCATION)


    now = datetime.datetime.utcnow()
    OBJ_XMLTV = ET.Element("tv" , {"date":now.strftime("%Y%m%d%H%M%S +0000"),"source_info_url":"https://go.tv.movistar.es","source_info_name":"Grabber for internal multicast of MovistarTV","generator_info_name":"python-xml-parser","generator_info_url":"http://wiki.xmltv.org/index.php/XMLTVFormat"})
    #OBJ_XMLTV = ET.Element("tv" , {"date":now.strftime("%Y%m%d%H%M%S")+" +0200"})

    logger.info("Getting channels list from: "+MCAST_CHANNELS)
    channelsstream = TvaStream(MCAST_CHANNELS,MCAST_PORT)
    channelsstream.getfiles()
    xmlchannels = channelsstream.files()["2_0"]
    xmlchannelspackages = channelsstream.files()["5_0"]

    channelparser = TvaParser(xmlchannels)
    rawclist = {}
    rawclist = channelparser.channellist(rawclist)

    channelspackages = {}
    channelspackages = TvaParser(xmlchannelspackages).getpackages()

    # If m3u arg create m3u and exit
    if args.m3u:
        clist = {}
        for package in TVPACKAGES:
            for channel in channelspackages[package].keys():
                clist[channel] = rawclist[channel]
                clist[channel]["order"] = channelspackages[package][channel]["order"]

        channelsm3u = channelparser.channels2m3u(clist)
        if args.filename:
            FILE_M3U = args.filename
            if os.path.isfile(FILE_M3U):
                os.remove(FILE_M3U)
            fM3u = open(FILE_M3U, 'w+')
            fM3u.write(channelsm3u)
            fM3u.close
        else:
            print channelsm3u
        exit()

    OBJ_XMLTV = channelparser.channels2xmltv(OBJ_XMLTV,rawclist)

    last_day = args.grab_offset + args.grab_days
    if last_day > 6:
        last_day = 6

    threads = list()
    for d in range(args.grab_offset, last_day):
        t =  threading.Thread(target=parse_day, args=(d,OBJ_XMLTV,rawclist)) 
        threads.append(t)
        t.start()

    [x.join() for x in threads]    


    # A standard grabber should print the xmltv file to the stdout or to
    # filename if called with option --output filename
    if args.filename:
        FILE_XML = args.filename
        ElementTree(OBJ_XMLTV).write(FILE_XML,encoding="UTF-8")
    else:
        dump(ElementTree(OBJ_XMLTV))
    # changed to logger to respect --quiet
    logger.info("Grabbed "+ str(len(OBJ_XMLTV.findall('channel'))) +" channels and "+str(len(OBJ_XMLTV.findall('programme')))+" programmes")

exit()
