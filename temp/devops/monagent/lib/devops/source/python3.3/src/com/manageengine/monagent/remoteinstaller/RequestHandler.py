'''
Created on 20-Oct-2016

@author: giri
'''
import urllib.request, os, configparser, sys, time
from com.manageengine.monagent.remoteinstaller import Constant,logutil
import json
import traceback
import threading
import encodings.idna
from urllib.parse import urlencode
import gzip

logger = logutil.Logger('main')

def reporthook(count, block_size, total_size):
    global start_time
    if count == 0:
        start_time = time.time()
        return
    duration = time.time() - start_time
    progress_size = int(count * block_size)
    speed = int(progress_size / (1024 * duration))
    percent = min(int(count * block_size * 100 / total_size), 100)
    sys.stdout.write("\r                                                                      ")
    sys.stdout.write("\r...%d%%, %d MB, %d KB/s, %d sec" %
                    (percent, progress_size / (1024 * 1024), speed, duration))
    sys.stdout.flush()


def download_files(url, destination, version):
    try:
        import socket
        socket.setdefaulttimeout(10)
        if version == "64":
            logger.info("Started download of 64bit install file \n")
            print("\n########################################## Downloading Install File #########################################################################\n")
            urllib.request.urlretrieve(url, destination, reporthook)
            print("\n\n"+"########################################## Bulk Installation Begins #########################################################################\n")
            logger.info("Completed download of 64bit install file")
        else:
            print("\n########################################## Downloading Install File #########################################################################\n")
            logger.info("Started download of 32bit install file \n")
            urllib.request.urlretrieve(url, destination, reporthook)
            print("\n\n"+"########################################## Bulk Installation Begins #########################################################################\n")
            logger.info("Completed download of 32bit install file")
        return True
    except Exception as e:
        logger.error ("Timout or got some  exception while downloading install file for {} bit exception {}".format(str(version), repr(e)))
        traceback.print_exc()
        return False
    
def downloader(os_type, post_data=False):
    try:
        Constant.STATIC_32BIT_URL = 'https://' + Constant.STATIC_DOMAIN + '/server/Site24x7_Linux_32bit.install'
        Constant.STATIC_64BIT_URL = 'https://' + Constant.STATIC_DOMAIN + '/server/Site24x7_Linux_64bit.install'
        Constant.PRINT_DOWNLOAD_DATA = True
        sys.stdout.write("\r  ")
        sys.stdout.write("\r")
        sys.stdout.flush()
        download_status = None
        config = configparser.RawConfigParser()
        config.read(Constant.CONFIGURATION_FILE_PATH)
        Constant.HTTP_PROXY_URL = config['PROXY']['http_proxy'] if not config['PROXY']['http_proxy'] == 'None' else None
        Constant.HTTPS_PROXY_URL = config['PROXY']['https_proxy'] if not config['PROXY']['https_proxy'] == 'None' else None
        proxy_values = {}
        '''Set http proxy'''
        if not Constant.HTTP_PROXY_URL is None:
            proxy_values['http'] = Constant.HTTP_PROXY_URL
        '''Set https proxy'''
        if not Constant.HTTPS_PROXY_URL is None:
            proxy_values['https'] = Constant.HTTPS_PROXY_URL
        proxy_handler = urllib.request.ProxyHandler(proxy_values)
        opener = urllib.request.build_opener(proxy_handler)
        if post_data is False:
            urllib.request.install_opener(opener)
            logger.info("################### Download Action #########################"+'\n')
            if os_type == "64-bit":
                if proxy_values:
                    logger.info("trying with supplied proxy to download install file")
                    download_status = download_files(Constant.STATIC_64BIT_URL, Constant.INSTALLFILE_64_BIT_PATH, "64")
                    if download_status is False:
                        print("Downloading install file failed so now trying with no proxy since trying to download install file with proxy supplied failed")
                        logger.info("now trying with no proxy since trying to download install file with proxy supplied failed")
                        proxy_values = {}
                        proxy_handler = urllib.request.ProxyHandler(proxy_values)
                        opener = urllib.request.build_opener(proxy_handler)
                        urllib.request.install_opener(opener)
                        download_status = download_files(Constant.STATIC_64BIT_URL, Constant.INSTALLFILE_64_BIT_PATH, "64")
                else:
                    logger.info("no proxy supplied to download install file")
                    download_status = download_files(Constant.STATIC_64BIT_URL, Constant.INSTALLFILE_64_BIT_PATH, "64")
            else:
                if proxy_values:
                    print("trying with supplied proxy to download install file")
                    logger.info("trying with supplied proxy to download install file")
                    download_status = download_files(Constant.STATIC_32BIT_URL, Constant.INSTALLFILE_32_BIT_PATH, "32")
                    if download_status is False:
                        print("Downloading install file failed so now trying with no proxy since trying to download install file with proxy supplied failed")
                        logger.info("now trying with no proxy since trying to download install file with proxy supplied failed")
                        proxy_values = {}
                        proxy_handler = urllib.request.ProxyHandler(proxy_values)
                        opener = urllib.request.build_opener(proxy_handler)
                        urllib.request.install_opener(opener)
                        download_status = download_files(Constant.STATIC_32BIT_URL, Constant.INSTALLFILE_32_BIT_PATH, "32")
                else:
                    logger.info("no proxy supplied to download install file")
                    download_status = download_files(Constant.STATIC_32BIT_URL, Constant.INSTALLFILE_32_BIT_PATH, "32")
        else:
            data =  json.dumps(Constant.RESULTPOOL_HANDLER.result).encode('utf8')
            req = urllib.request.Request(Constant.PLUS_S24X7_URL+Constant.API_KEY , 
                                    data, headers={'content-type': 'application/json'})
            try:
                with urllib.request.urlopen(req) as resp:
                    dict_responseHeaders = dict(resp.getheaders())
                    if resp.status == 200:
                        logger.info("results.txt successfully posted to plusserver")
            except Exception as e:
                traceback.print_exc()
        Constant.PRINT_DOWNLOAD_DATA = False
        return download_status
    
    except Exception as e:
        traceback.print_exc()
        Constant.PRINT_DOWNLOAD_DATA = False
        return False
