import requests
import zipfile
import shutil
import imageio
import os
from PIL import Image
from time import strftime, localtime

import pixivpy3


# file system
def print_with_time(msg):
    print('[%s] %s' %(strftime("%Y-%m-%d %H:%M:%S", localtime()), msg))


def format_dir_name(dname):
    invalid_symbol = ['\\', '/', '>', '～', '<']
    for i in invalid_symbol:
        dname = dname.replace(i, '')
    return dname


# justmysocks
jms_txt = './justmysocks-api.txt'
if os.path.isfile(jms_txt):
    with open(jms_txt, 'r') as f:
        jms_api = f.readlines()[0].strip()
else:
    jms_api = 'xxxx'


def get_bandwidth_info(url=jms_api):
    res = requests.get(url)
    return res.json() if res else None


def check_bandwidth_limit(max_bandwidth, url=jms_api):
    bandwith_res = get_bandwidth_info(url)
    bandwith_msg = 'Current: {:.2f}G, Total {:.2f}G, Ratio: {:.2f}%'.format(
        bandwith_res['bw_counter_b'] / 10e9,
        bandwith_res['monthly_bw_limit_b'] / 10e9,
        100 * bandwith_res['bw_counter_b'] / bandwith_res['monthly_bw_limit_b'])

    if max_bandwidth > 1:
        bandwith = bandwith_res['bw_counter_b']
    else:
        bandwith = bandwith_res['bw_counter_b'] / bandwith_res['monthly_bw_limit_b']

    if bandwith > max_bandwidth:
        return False, bandwith_msg
    else:
        return True, bandwith_msg


def get_bandwith_message(url=jms_api):
    bandwith_res = get_bandwidth_info(url)
    bandwith_msg = 'Current: {:.2f}G, Total {:.2f}G, Ratio: {:.2f}%'.format(
        bandwith_res['bw_counter_b'] / 10e9,
        bandwith_res['monthly_bw_limit_b'] / 10e9,
        100 * bandwith_res['bw_counter_b'] / bandwith_res['monthly_bw_limit_b'])
    return bandwith_msg


# pixivpy3 utils
COLLECT_FIELD = [
'id',
'image_urls',   # meta_pages || meta_single_page
'illust_ai_type',   # 2-ai; 1-human;
'illust_book_style',
'total_bookmarks',
'total_view',
]
def collect_info_by_json(json_dict):
    '''
    pixivpy3.utils.JsonDict
    '''
    illust = dict(json_dict)                
    image_info = dict()
    for field in COLLECT_FIELD:
        if field in illust:
            if isinstance(illust[field], pixivpy3.utils.JsonDict):
                image_info[field] = dict(illust[field])
            elif isinstance(illust[field], list):
                tmp_list = list()
                for illust_field_i in illust[field]:
                    if isinstance(illust_field_i, pixivpy3.utils.JsonDict):
                        tmp_list.append(dict(illust_field_i))
                    else:
                        tmp_list.append(illust_field_i)
                image_info[field] = tmp_list
            else:
                image_info[field] = illust[field]
        else:
            image_info[field] = None

    # get urls from meta_pages || meta_single_page
    image_info['image_urls'] = list()
    if illust['meta_pages']:
        for meta_page in illust['meta_pages']:
            image_urls = dict(dict(meta_page)['image_urls'])
            if 'original' in image_urls:
                image_info['image_urls'].append(image_urls['original'])
            elif 'large' in image_urls:
                image_info['image_urls'].append(image_urls['large'])
            elif 'medium' in image_urls:
                image_info['image_urls'].append(image_urls['medium'])
    if illust['meta_single_page']:
        image_info['image_urls'].append(dict(illust['meta_single_page'])['original_image_url'])

    return image_info


def appapi_illust(api, pixiv_id):
    json_result = api.illust_detail(pixiv_id)
    return json_result.illust


def collect_info_by_pid(api, pixiv_id):
    json_dict = appapi_illust(api, pixiv_id)
    image_info = collect_info_by_json(json_dict)
    return image_info


# image utils
def img_verify(file): 
    is_valid = True
    if isinstance(file, (str, os.PathLike)):
        fileObj = open(file, 'rb')
    else:
        fileObj = file

    buf = fileObj.read()
    if buf[6:10] in (b'JFIF', b'Exif'): # jpg
        if not buf.rstrip(b'\0\r\n').endswith(b'\xff\xd9'):
            is_valid = False
    elif buf[1:4] in (b'PNG'):     # png
        if not buf.rstrip(b'\0\r\n').endswith(b'\xaeB`\x82'):
            is_valid = False
    else:        
        try:  
            Image.open(fileObj).verify() 
        except:  
            is_valid = False
            
    return is_valid


def images_to_gif(img_dir, gif_name, fps=15, frame2delay=None):
    frames = []
    png_files = sorted(os.listdir(img_dir))

    if frame2delay is not None:
        assert len(png_files) == len(frame2delay)
    # PIL
    # for frame_id in range(len(png_files)):
    #     frame = Image.open(os.path.join(img_dir, png_files[frame_id]))
    #     frames.append(frame)
    #     frames[0].save(gif_name, save_all=True,
    #         append_images=frames[1:],
    #         transparency=0,
    #         duration=1000//fps,
    #         loop=0,
    #         disposal=2)

    # imageio
    with imageio.get_writer(uri=gif_name, mode='I', fps=fps) as writer:
        for file in png_files:
            fpath = os.path.join(img_dir, file)
            writer.append_data(imageio.imread(fpath))

    if frame2delay is not None:
        duration = [v/1000 for v in frame2delay.values()]
        imageio.mimsave(gif_name, imageio.mimread(gif_name, memtest=False),
                        duration=duration)



