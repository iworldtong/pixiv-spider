# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import glob
import shutil
import threading
from pprint import pprint
from tenacity import retry, wait_fixed, wait_exponential, retry_if_exception_type, stop_after_attempt

import filetype

from utils import * 


if sys.version_info >= (3, 0):
    pass
else:
    reload(sys)
    sys.setdefaultencoding('utf8')
sys.dont_write_bytecode = True


IMAGE_EXT = ['*.jpg', '*.jpeg', '*.png']
IMAGE_EXT += [i.upper() for i in IMAGE_EXT]


def get_file_type(fpath):
    try:
        kind = filetype.guess(fpath)
        return kind.extension.lower()
    except Exception as e:
        if fpath.split('.')[-1].lower() in TYPES:
            return fpath.split('.')[-1].lower()
        else:
            return None


def url2name(url):
    name = url.split('/')[-1]
    return name


def check_download_condition(illust_info, args):
    is_valid = True
    if args.min_bookmark > int(illust_info['total_bookmarks']):
        is_valid = False

    return is_valid


class DownloadThread(): 
    def __init__(self, args):
        super(DownloadThread, self).__init__()
        self.args = args
        self.cache_dict = dict()
        if self.args.cache is not None:
            with open(self.args.cache, 'r') as f:
                self.cache_dict = json.load(f)

    def run(self, illusts):
        self.illusts = list()
        for illust in illusts:
            illust_info = collect_info_by_json(illust)
            if self.args.cache is None or \
               str(illust_info['id']) not in self.cache_dict or self.args.force:
                
                # download condition
                if check_download_condition(illust_info, self.args):
                    self.illusts.append(illust_info)

        if not self.illusts:
            return
        os.makedirs(self.args.download_dir, exist_ok=True)

        # download
        mt_list = []
        for illust in self.illusts:
            mt = ms_download_by_illust(illust, self.args)
            mt.start()
            mt_list.append(mt)

        # wait all work to be finished
        for mt in mt_list:
            mt.join()

        if self.args.cache is not None and self.args.update_cache:
            for illust in self.illusts:
                is_complete = True
                for image_url in illust['image_urls']:
                    image_path = os.path.join(self.args.download_dir, url2name(image_url))
                    if not os.path.exists(image_path):
                        is_complete = False
                        break
                if is_complete:
                    self.cache_dict[str(illust['id'])] = illust

            with open(self.args.cache, 'w') as f:
                json.dump(self.cache_dict, f)     


class ms_download_by_illust(threading.Thread):
    def __init__(self, illust, args):
        threading.Thread.__init__(self)            
        self.illust = illust
        self.args = args

    def download_gif(self):
        try:
            illust_id = str(self.illust['id'])
            zip_path = os.path.join(self.args.download_dir, illust_id+'.zip')
            img_dir = os.path.join(self.args.download_dir, illust_id)            
            gif_path = os.path.join(self.args.download_dir, illust_id+'.gif')

            # clean cache
            if os.path.exists(zip_path):
                os.remove(zip_path)
            if os.path.isdir(img_dir):
                shutil.rmtree(img_dir)
            if os.path.exists(gif_path):
                print_with_time('\tskip: ' + illust_id+'.gif')
                return True

            ugoira_metadata = self.args.api.ugoira_metadata(self.illust['id'])
            zip_url = sorted(list(ugoira_metadata['ugoira_metadata']['zip_urls'].values()))[-1]        
            self.args.api.download(zip_url, 
                                   path=self.args.download_dir,
                                   name=illust_id+'.zip')
            
            # get delays
            frame2delay = dict()
            for item in ugoira_metadata['ugoira_metadata']['frames']:
                frame2delay[item['file']] = item['delay']

            # extract zip
            if zipfile.is_zipfile(zip_path):
                os.makedirs(img_dir, exist_ok=True)
                f = zipfile.ZipFile(zip_path, 'r')
                for file in f.namelist():
                    f.extract(file, img_dir)     
                f.close()
            else:
                print_with_time("Not a zip file: " + zip_path)
                return

            # (zip ->) images -> gif
            images_to_gif(img_dir, gif_path, frame2delay=frame2delay)

            # clean tmp files
            shutil.rmtree(img_dir)
            os.remove(zip_path)
            
            print_with_time('\tdownload: ' + illust_id+'.gif')
            
            return True
        except Exception as e:
            if 'error' not in ugoira_metadata.keys():
                print_with_time("error in GIF: " + illust_id)
                print(ugoira_metadata.keys())
                print_with_time(e)
            return False

    def download_images(self):
        try:        
            for image_url in self.illust['image_urls']:
                self.download_image(image_url, path=self.args.download_dir)               
            return True
        except Exception as e:
            print_with_time('\terror in ms: '+str(e))
            return False

    def run(self):
        self.download_gif()
        self.download_images()

    def download_image(self, image_url, path):
        fname = url2name(image_url) 
        try:
            fpath = os.path.join(self.args.download_dir, fname)
            if os.path.exists(fpath):
                print_with_time('\tskip: ' + fname)
                return
            
            fname_part = fname + '.part'
            fpath_part = fpath + '.part'
            
            self.safe_download(image_url, path=path, name=fname_part)
            retry_cnt = 0
            while True:
                retry_cnt += 1
                if img_verify(fpath_part):
                    os.rename(fpath_part, fpath)
                    print_with_time('\tdownload: ' + fname)
                    break
                elif retry_cnt <= 5:
                    print_with_time('\tretry: {} {}\r'.format(str(retry_cnt), image_url))
                    time.sleep(1)
                else:
                    print_with_time('\tabort: {}'.format(image_url))
                    break
                self.safe_download(image_url, path=path, name=fname_part)
                

        except Exception as e:
            print_with_time('\terror in download: '+ str(e) + ' '+image_url)
            pass

    # Note that no exceptions are exposed here
    @retry(wait=wait_fixed(5), stop=stop_after_attempt(10))
    def safe_download(self, url, path, name):
        self.args.api.download(url, path=path, name=name) 


            