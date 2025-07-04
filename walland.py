#!/usr/bin/env python3

__author__ = "Matteo Golinelli, modificado por ChatGPT para incluir Wallhaven"
__copyright__ = "Copyright (C) 2023 Matteo Golinelli"
__license__ = "MIT"

from curl_cffi import requests
from bs4 import BeautifulSoup

import subprocess
import argparse
import logging
import random
import shlex
import time
import sys
import os
import re
import json

USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'

DEFAULT = 'random'

SOURCES = ['bing', 'unsplash', 'nasa', 'apod', 'earthobservatory', 'epod', 'national-geographic', 'wallhaven']

BACKENDS = ['hyprpaper', 'swaybg', 'feh', 'swww']

SUPPORTED_EXTENSIONS = ['png', 'jpg', 'jpeg', 'webp']

SOURCES_INFO = {
    'bing': {
        'url': 'https://www.bing.com/HPImageArchive.aspx?idx=0&n=1',
        'download': 'https://www.bing.com{}',
        'element': {
            'tag': 'urlBase',
            'attrs': {}
        },
    },
    'unsplash': {
        'url': 'https://unsplash.com/t/wallpapers',
        'download': '',
        'element': {
            'tag': 'img',
            'attrs': {
                'itemprop': 'thumbnailUrl',
                'src': re.compile(r'^(?!.*plus\.).*')
            }
        },
    },
    'nasa': {
        'url': 'https://www.nasa.gov/rss/dyn/lg_image_of_the_day.rss',
        'download': '',
        'element': {
            'tag': 'enclosure',
            'attrs': {'type': 'image/jpeg'}
        },
    },
    'apod': {
        'url': 'https://apod.nasa.gov/apod/astropix.html',
        'download': 'https://apod.nasa.gov/apod/{}',
        'element': {
            'tag': 'a',
            'attrs': {'href': re.compile(r'^image/')}
        },
    },
    'earthobservatory': {
        'url': 'https://earthobservatory.nasa.gov/feeds/earth-observatory.rss',
        'download': '',
        'element': {
            'tag': 'media:thumbnail',
            'attrs': {}
        },
    },
    'epod': {
        'url': 'https://epod.usra.edu/',
        'download': '',
        'element': {
            'tag': 'img',
            'attrs': {'class': 'asset-image'}
        },
    },
    'national-geographic': {
        'url': 'https://www.natgeotv.com/me/photo-of-the-day',
        'download': '',
        'element': {
            'tag': 'img',
            'attrs': {'width': '940'}
        },
    },
    'wallhaven': {
        'url': 'https://wallhaven.cc/api/v1/search',
        'download': '',
        'element': {},  # API based
    },
}

logger = logging.getLogger('walland')


def set_wallpaper(image_path, backend='hyprpaper', backend_args=''):
    try:
        if subprocess.check_output(shlex.split(f'which {backend}'), stderr=subprocess.PIPE) == b'':
            logger.error(f'Error: {backend} is not installed. Use one of the available backends: {", ".join(BACKENDS)}')
            sys.exit(1)
    except subprocess.CalledProcessError:
        logger.error(f'Error: {backend} is not installed. Use one of the available backends: {", ".join(BACKENDS)}')
        sys.exit(1)

    if backend == 'hyprpaper':
        try:
            if subprocess.check_output(shlex.split('pgrep hyprpaper'), stderr=subprocess.PIPE) == b'':
                subprocess.Popen('hyprpaper &', shell=True).wait()
                time.sleep(1)
        except subprocess.CalledProcessError:
            subprocess.Popen('hyprpaper &', shell=True).wait()
            time.sleep(1)

        subprocess.Popen(shlex.split(f'hyprctl hyprpaper preload "{image_path}"'), stdout=subprocess.PIPE).wait()

        monitors = subprocess.Popen(shlex.split('hyprctl monitors'), stdout=subprocess.PIPE).communicate()[0].decode().split('\n')
        monitors = [monitor.split('Monitor ')[1].split(' ') for monitor in monitors if 'Monitor ' in monitor]

        for monitor in monitors:
            subprocess.Popen(shlex.split(f'hyprctl hyprpaper wallpaper "{monitor[0]},{image_path}" {backend_args}'), stdout=subprocess.PIPE).wait()
    elif backend == 'swaybg':
        subprocess.Popen(shlex.split('killall swaybg')).wait()
        subprocess.Popen(shlex.split(f'swaybg --mode fill -i {image_path} {backend_args}'), stdout=subprocess.PIPE)
    elif backend == 'swww':
        try:
            if subprocess.check_output(shlex.split('pgrep swww-daemon'), stderr=subprocess.PIPE) == b'':
                subprocess.Popen('swww-daemon &', shell=True, stdout=subprocess.PIPE).wait()
                time.sleep(1)
        except subprocess.CalledProcessError:
            subprocess.Popen('swww-daemon &', shell=True, stdout=subprocess.PIPE).wait()
            time.sleep(1)

        subprocess.Popen(shlex.split(f'swww img {image_path} {backend_args}'), stdout=subprocess.PIPE)
    elif backend == 'feh':
        subprocess.Popen(shlex.split(f'feh --bg-fill {image_path} {backend_args}'), stdout=subprocess.PIPE)
    else:
        logger.error(f'Error: backend {backend} not found. Use one of the available backends: {", ".join(BACKENDS)}')
        sys.exit(1)


def download_image(url, source, save=False):
    logger.debug(f'Image URL: {url}')
    response = requests.get(url, headers={'User-Agent': USER_AGENT}, impersonate='chrome')

    filename = f'{source}_{time.strftime("%Y-%m-%d")}'
    url = url.split('?')[0].split('#')[0]
    if '.' in url.split('/')[-1]:
        filename += f'.{url.split(".")[-1]}'
    else:
        filename += f'.{response.headers["content-type"].split("/")[-1]}'

    if save:
        filename = f'{os.getcwd()}/{filename}'
    else:
        tmp_dir = f'/tmp/walland'
        os.makedirs(tmp_dir, exist_ok=True)
        filename = f'{tmp_dir}/{filename}'

    logger.debug(f'Saving image as {filename}')
    with open(filename, 'wb') as f:
        f.write(response.content)

    return filename


def convert_image(image_path):
    logger.debug('Converting the image to PNG format')
    try:
        if subprocess.check_output(shlex.split('which magick'), stderr=subprocess.PIPE) == b'':
            logger.error('Error: ImageMagick is not installed.')
            sys.exit(1)
    except subprocess.CalledProcessError:
        logger.error('Error: ImageMagick is not installed.')
        sys.exit(1)

    filename = os.path.basename(image_path)
    filename = '.'.join(filename.split('.')[:-1])
    new_path = f'/tmp/walland/{filename}.png'

    subprocess.Popen(shlex.split(f'magick {image_path} {new_path}')).wait()
    logger.debug(f'Image converted to {new_path}')
    return new_path


def main():
    parser = argparse.ArgumentParser(description='Walland: wallpaper setter from multiple daily sources.')

    parser.add_argument('-s', '--source', type=str, default=DEFAULT, help=f'Source of the image. Default: random. Available: {", ".join(SOURCES)}')
    parser.add_argument('-b', '--backend', type=str, default='hyprpaper', help=f'Wallpaper backend. Default: hyprpaper. Available: {", ".join(BACKENDS)}')
    parser.add_argument('-a', '--backend-args', type=str, default='', help='Extra backend arguments.')
    parser.add_argument('-S', '--save', action='store_true', help='Save image in current directory.')
    parser.add_argument('-D', '--debug', action='store_true', help='Enable debug logs.')

    parser.add_argument('--api-key', type=str, default='', help='Wallhaven API key (required for wallhaven).')
    parser.add_argument('--tag', type=str, default='', help='Wallhaven search tag.')
    parser.add_argument('--top', type=int, default=10, help='Number of top Wallhaven results to randomize from.')

    try:
        import argcomplete
        argcomplete.autocomplete(parser)
    except ImportError:
        pass

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    logging.getLogger('urllib3').setLevel(logging.ERROR)

    if args.source == DEFAULT:
        args.source = random.choice([source for source in SOURCES if source != 'wallhaven'])
    elif args.source not in SOURCES:
        logger.error(f'Error: source {args.source} not found.')
        sys.exit(1)

    if args.backend not in BACKENDS:
        logger.error(f'Error: backend {args.backend} not found.')
        sys.exit(1)

    source_info = SOURCES_INFO[args.source]

    if args.source == 'wallhaven':
        if not args.api_key:
            logger.error('Error: --api-key is required for wallhaven.')
            sys.exit(1)

        tag_query = args.tag.replace(' ', '+')
        params = {
            'apikey': args.api_key,
            'q': tag_query,
            'sorting': 'toplist',
            'page': 1
        }

        try:
            response = requests.get(source_info['url'], headers={'User-Agent': USER_AGENT}, params=params, impersonate='chrome')
            data = response.json()
            images = data.get('data', [])
            if not images:
                logger.error('No images found for given tags.')
                sys.exit(1)
            chosen = random.choice(images[:args.top])
            path = chosen['path']
        except Exception as e:
            logger.error(f'Error fetching Wallhaven image: {e}')
            sys.exit(1)

    else:
        try:
            response = requests.get(source_info['url'], headers={'User-Agent': USER_AGENT}, impersonate='chrome')
        except Exception as e:
            logger.error(f'Error: {e}')
            sys.exit(1)

        soup = BeautifulSoup(response.text, 'xml' if args.source in ['nasa', 'earthobservatory', 'bing'] else 'html.parser')
        element = soup.find(source_info['element']['tag'], source_info['element']['attrs'])
        if args.source == 'bing':
            path = source_info['download'].format(element.text) + '_UHD.jpg'
        elif args.source == 'unsplash':
            path = element['src']
        elif args.source == 'national-geographic':
            path = element['src']
        elif args.source == 'nasa':
            path = element['url']
        elif args.source == 'apod':
            path = source_info['download'].format(element['href'])
        elif args.source == 'earthobservatory':
            path = element['url']
        elif args.source == 'epod':
            path = element['src']

    image_path = download_image(path, args.source, args.save)

    if (
        (args.backend == 'swaybg' and image_path.endswith('.webp')) or
        image_path.split('.')[-1] not in SUPPORTED_EXTENSIONS
    ):
        image_path = convert_image(image_path)

    set_wallpaper(image_path, backend=args.backend, backend_args=args.backend_args)


if __name__ == '__main__':
    main()
