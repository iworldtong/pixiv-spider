# -*- coding: utf-8 -*-
import sys
import copy
import time
import json
import glob
import shutil
import argparse
from tqdm import tqdm
from tenacity import retry, wait_fixed, wait_exponential, retry_if_exception_type, stop_after_attempt

from pixivpy3 import AppPixivAPI, PixivError

from downloader import *
from utils import *
from key import KEY
from usr import USR

# settings
WAIT_SEC = 5
RETRY_NUM = 5
FILTER_FIX = '@'

# proxy
sys.dont_write_bytecode = True
if sys.platform == 'darwin':    # Mac OS X  
    PROXY_PORT = '1087'
elif sys.platform == 'win32':   # win
    PROXY_PORT = '10081'
_REQUESTS_KWARGS = {
    'proxies': {
        'https': 'http://127.0.0.1:{}'.format(PROXY_PORT),
    },
    # 'verify': False,  # PAPI use https, an easy way is disable requests SSL verify
}

# get your refresh_token, and replace _REFRESH_TOKEN
#  https://github.com/upbit/pixivpy/issues/158#issuecomment-778919084
def load_tokens(token_path='./TOKENS.json'):
    with open(token_path, 'r') as f:
        tokens = json.load(f)
    print('=> Access Token: {}'.format(tokens['access_token']))
    print('=> Refresh Token: {}'.format(tokens['refresh_token']))
    return tokens


def set_auth(api, retry_num=RETRY_NUM, auth_func='auth'):
    tokens = load_tokens()
    _e = None
    for _ in range(retry_num):
        try:
            if auth_func == 'auth':
                api.auth(refresh_token=tokens['refresh_token'])
            elif auth_func == 'set_auth':
                api.set_auth(access_token=tokens['access_token'],
                             refresh_token=tokens['refresh_token'])
            else:
                raise Exception('Invalid auth_func. (auth or set_auth)')
            break
        except PixivError as e:
            _e = e
            print(_e)
            time.sleep(10)
    else:
        raise _e


@retry(wait=wait_fixed(WAIT_SEC), stop=stop_after_attempt(RETRY_NUM))
def safe_search_illusts(api, keyword=None, kwargs=None):
    if kwargs is not None:
        return api.search_illust(**kwargs)
    else:
        return api.search_illust(keyword, 
                                 search_target='partial_match_for_tags')


@retry(wait=wait_fixed(WAIT_SEC), stop=stop_after_attempt(RETRY_NUM))
def safe_search_user_illusts(api, uid=None, kwargs=None):
    if kwargs is not None:
        return api.user_illusts(**kwargs)
    else:
        return api.user_illusts(uid)


def download_by_key(args):
    assert isinstance(args.input, str)
    download_args = copy.deepcopy(args)

    # get filter 
    if FILTER_FIX in download_args.input:
        download_args.input = args.input.split(FILTER_FIX)[0]
        download_args.min_bookmark = int(args.input.split(FILTER_FIX)[-1])
        print_with_time('=> Changed min bookmark to: {}'.format(str(download_args.min_bookmark)))

    dname = download_args.input
    download_args.download_dir = os.path.join(download_args.download_dir, 
                                              download_args.mode, dname)
    # setup cache
    if download_args.cache is not None:
        download_args.cache = os.path.join(download_args.cache, 
                                           download_args.mode, dname + '.json')
        if os.path.isfile(download_args.cache):
            print_with_time('=> [✓] Found cache: {}'.format(download_args.cache))
        else:
            print_with_time('=> [x] New cache: {}'.format(download_args.cache))
            os.makedirs(os.path.split(download_args.cache)[0], exist_ok=True)
            with open(download_args.cache, 'w') as f:
                json.dump(dict(), f)

    # search 
    search_results = safe_search_illusts(download_args.api,
                                         keyword=download_args.input)
    if 'illusts' in search_results.keys():
        illusts = search_results['illusts']
    else:
        raise Exception('Empty results.')

    download_thread = DownloadThread(download_args)
    for page_idx in range(1, download_args.page_start + download_args.page_num):
        if page_idx < download_args.page_start:
            continue

        print_with_time('Key: %s | Page: %d' %(download_args.input, page_idx))
        download_thread.run(illusts)

        if search_results.next_url is None:
            print_with_time('No more pages.')
            break
        else:
            search_results = safe_search_illusts(download_args.api, 
                kwargs=download_args.api.parse_qs(search_results.next_url))

            if 'illusts' in search_results.keys():
                illusts = search_results['illusts']
            else:
                return 


def download_by_usr(args):
    assert isinstance(args.input, str)
    download_args = copy.deepcopy(args)
    download_args.input = int(download_args.input)  # User Id must be an integer

    # get usr name by uid
    json_result = download_args.api.user_illusts(download_args.input)
    try:
        print_with_time('Usr: [{}] {}'.format(download_args.input, json_result.user.name))
    except Exception as e:
        pprint(json_result)
        raise

    usr_name = format_dir_name(json_result.user.name)
    dname = '[{}] {}'.format(download_args.input, usr_name)

    # adapot dir's name 
    usr_root = os.path.join(download_args.download_dir, download_args.mode)
    if os.path.isdir(usr_root):
        for dn in os.listdir(usr_root):
            if os.path.isdir(os.path.join(usr_root, dn)) and \
                dn.find(str(download_args.input)) != -1:
                dname = dn
                print_with_time('=> [✓] Found image dir: {}'.format(dname))
                break

    download_args.download_dir = os.path.join(usr_root, dname)
    # setup cache
    if download_args.cache is not None:
        download_args.cache = os.path.join(download_args.cache, download_args.mode, 
                                           '[{}] {}'.format(download_args.input, usr_name) + '.json')
        if os.path.isfile(download_args.cache):
            print_with_time('=> [✓] Found cache: {}'.format(download_args.cache))
        else:
            print_with_time('=> [x] New cache: {}'.format(download_args.cache))
            os.makedirs(os.path.split(download_args.cache)[0], exist_ok=True)
            with open(download_args.cache, 'w') as f:
                json.dump(dict(), f)

    # search 
    search_results = safe_search_user_illusts(download_args.api,
                                              uid=download_args.input)
    if 'illusts' in search_results.keys():
        illusts = search_results['illusts']
    else:
        raise Exception('Empty results.')
        
    download_thread = DownloadThread(download_args)
    while True:            
        download_thread.run(search_results.illusts)

        if search_results.next_url is None:
            print_with_time('No more pages.')
            break
        else:
            search_results = safe_search_user_illusts(download_args.api, 
                kwargs=download_args.api.parse_qs(search_results.next_url))


def download_by_list(args):
    if args.input is not None and '+' in args.input:
        MODE = args.input.split('+')
    else:
        MODE = eval(args.mode.upper()) 

    idx_path = './tmp/{}_idx.txt'.format(args.mode)
    with open(idx_path, 'r') as f:
        input_idx = int(f.readlines()[0].strip())
    input_idx %= len(MODE)

    while True:
        download_args = copy.deepcopy(args)
        download_args.input = MODE[input_idx]
        eval('download_by_{}'.format(download_args.mode))(download_args)

        input_idx += 1
        input_idx %= len(MODE)
        with open(idx_path, 'w') as f:
            f.write(str(input_idx))

    
def clean(args):
    remove_ext = ['part', 'zip']
    modes = [i for i in os.listdir(args.download_dir) 
                if os.path.isdir(os.path.join(args.download_dir, i)) and i[0] != '.']
    for mode in modes:
        mode_dirs = [i for i in os.listdir(os.path.join(args.download_dir, mode)) 
                        if os.path.isdir(os.path.join(args.download_dir, mode, i)) and i[0] != '.']
        for mode_idx, mode_dir in enumerate(mode_dirs):        
            print('[{}][{}/{}] => {}'.format(mode, mode_idx + 1, len(mode_dirs), mode_dir))

            mode_dpath = os.path.join(args.download_dir, mode, mode_dir)
            remove_list = list()
            for ext in remove_ext:
                remove_list += glob.glob(os.path.join(mode_dpath, '*.{}'.format(ext)))
            remove_list += [os.path.join(mode_dpath, i) 
                                for i in os.listdir(mode_dpath) 
                                    if os.path.isdir(os.path.join(mode_dpath, i))]
            for remove_idx, path in enumerate(remove_list):
                print('[{}][{}/{}]\t\t{}'.format(mode, mode_idx + 1, len(mode_dirs), path))
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)


def rewrite_input_txt(args):
    mode = args.mode.split('-')[-1]
    if mode not in ['key', 'usr']:
        raise('Unsupport mode type: {}'.format(mode))
    MODE = eval(mode.upper())
    input_path = os.path.join(args.input_dir, mode + '.txt')

    retrieved_inputs = [i for i in os.listdir(os.path.join(args.download_dir, mode)) 
                        if os.path.isdir(os.path.join(args.download_dir, mode, i))]
    if mode == 'usr':
        retrieved_inputs = [get_uid_from_dname(i) for i in retrieved_inputs]

    # retrieved_inputs contains, MODE not contains
    diff_inputs = list(set(retrieved_inputs).difference(set(MODE)))
    print('=> Diff {}: '.format(mode.lower()))
    pprint(diff_inputs)

    if os.path.isfile(input_path):
        with open(input_path, 'r') as f:
            lines = f.readlines()
    else:
        lines = [mode.upper() + ' = [\n', ']']
        with open(input_path, 'w') as f:
            for line in lines:
                f.write(line)

    with open(input_path, 'w') as f:
        for line in lines:
            if line.strip() != ']': 
                f.write(line)
            else:
                break
        for i in diff_inputs:
            f.write('\'{}\','.format(i) + '\n')
        f.write(']')


def get_uid_from_dname(dname):
    if dname[-1] == ')':
        uid = dname.split('(')[-1][:-1]
    else:
        uid = dname.split(']')[0].split('[')[-1]
    return uid


def update(args):
    _func = args.mode.split('-')[-1]

    if _func == 'cache':
        update_cache(args)
    else:
        rewrite_input_txt(args)


def update_cache(args):
    assert args.cache is not None

    modes = [i for i in os.listdir(args.download_dir) 
                if os.path.isdir(os.path.join(args.download_dir, i)) and i[0] != '.']
    for mode in modes:
        mode_dirs = [i for i in os.listdir(os.path.join(args.download_dir, mode)) 
                        if os.path.isdir(os.path.join(args.download_dir, mode, i)) and i[0] != '.']
        for mode_idx, mode_dir in enumerate(mode_dirs):        
            if mode == 'usr':
                mode_input = mode_dir.split(']')[0][1:]
            else:
                mode_input = mode_dir
            print('[{}][{}/{}] => {}'.format(mode, mode_idx + 1, len(mode_dirs), mode_dir))

            mode_dpath = os.path.join(args.download_dir, mode, mode_dir)

            # load cache
            cache_dict = dict()
            cache_path = os.path.join(args.cache, mode, mode_input + '.json')
            if os.path.exists(cache_path):
                print('[{}][{}/{}] => [✓] Found cache: {}'.format(
                    mode, mode_idx + 1, len(mode_dirs), cache_path))
                with open(cache_path, 'r') as f:
                    cache_dict = json.load(f)
            else:
                print('[{}][{}/{}] => [x] New cache: {}'.format(
                    mode, mode_idx + 1, len(mode_dirs), cache_path))
                os.makedirs(os.path.split(cache_path)[0], exist_ok=True)
                with open(cache_path, 'w') as f:
                    json.dump(cache_dict, f)

            # retrieve illust info
            files = [i for i in os.listdir(mode_dpath) 
                        if os.path.isfile(os.path.join(mode_dpath, i)) and i[0] != '.']
            pixiv_ids = list(set([fname.split('_')[0] for fname in files]))
            bar = tqdm(pixiv_ids)
            for pixiv_id in bar:
                bar.set_description(pixiv_id)
                illust_info = collect_info_by_pid(args.api, pixiv_id)
                cache_dict[str(illust_info['id'])] = illust_info

            # update cache json
            with open(cache_path, 'w') as f:
                json.dump(cache_dict, f)
            print('[{}][{}/{}] => Updated cache: {}'.format(
                    mode, mode_idx + 1, len(mode_dirs), cache_path))


def check_bandwidth_state(args):
    if args.max_bandwidth is not None:
        bandwith_res, bandwith_msg = check_bandwidth_limit(args.max_bandwidth)
        if args.max_bandwidth > 1:
            bandwidth_str = "{:.2f}G".format(args.max_bandwidth)
        else:
            bandwidth_str = "{:.2f}%".format(args.max_bandwidth * 100)

        if not bandwith_res:
            print('=> [x] JustMySocks: {}, max: {}'.format(bandwith_msg, bandwidth_str))
            return False
        else:
            print('=> [✓] JustMySocks: {}, max: {}'.format(bandwith_msg, bandwidth_str))
            return True


'''
python auto_runner.py -c "python main.py key -d /Volumes/iwt/pixiv/pixiv --cache ./cache --update-cache"
'''
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', default=None, choices=['key', 'usr', \
                                                       'clean',\
                                                       'update-key', \
                                                       'update-usr', 
                                                       'update-cache'])
    parser.add_argument('-i', '--input', default=None, type=str)
    parser.add_argument('-ps', '--page-start', default=1, type=int)
    parser.add_argument('-pn', '--page-num', default=200, type=int)    
    parser.add_argument('-c', '--cache', default=None, type=str)
    parser.add_argument('-f', '--force', action='store_true')
    parser.add_argument('-u', '--update-cache', action='store_true')
    parser.add_argument('-d', '--download-dir', default=None, type=str)
    parser.add_argument('-mb', '--min-bookmark', default=2000, type=int)
    parser.add_argument('-a', '--auth-func', default='auth', choices=['auth', 'set_auth'])

    # update input.txt from download_dir
    parser.add_argument('--input-dir', default='.', type=str)

    # justmysocks
    parser.add_argument('--max-bandwidth', default=None, type=float)

    args = parser.parse_args()

    assert args.mode is not None
    if args.cache is not None:
        print('=> Use cache: {}'.format(args.cache))
        os.makedirs(args.cache, exist_ok=True)
    else:
        print('=> Not cached')

    print('=> Args:')
    pprint(vars(args))

    # check justmysocks bandwidth limit
    if args.max_bandwidth is not None and not check_bandwidth_state(args):
        return
    
    args.api = AppPixivAPI(**_REQUESTS_KWARGS)
    set_auth(args.api, auth_func=args.auth_func) 

    # utils
    if args.mode not in ['key', 'usr']:
        eval(args.mode.split('-')[0])(args)
        return

    # download
    _func = 'download_by_{format}'.format(format='list' \
        if args.input is None or '+' in args.input else args.mode)
    eval(_func)(args)
    

if __name__ == "__main__":
    main()