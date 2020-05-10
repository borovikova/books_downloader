import requests
import os
from bs4 import BeautifulSoup
from pathvalidate import sanitize_filename
from urllib.parse import urljoin
import json
import argparse
import logging
from dotenv import load_dotenv


def raise_for_redirect(response):
    for record in response.history:
        if record.status_code == 302:
            raise requests.exceptions.HTTPError('Redirect occured')


def ensure_dir(directory):
    os.makedirs(directory, exist_ok=True)


def get_extension(image_url):
    return os.path.splitext(image_url)[1]


def get_book_title_author(soup):
    header = soup.select_one('h1').text
    title, author = header.split('::')
    return title.strip(), author.strip()


def get_image_url(soup, html_page_url):
    selector = '.bookimage a img'
    img_relative_url = soup.select_one(selector)['src']
    return urljoin(html_page_url, img_relative_url)


def get_book_comments(soup):
    divs = soup.select('.texts ')
    if divs:
        return [div.select_one('.black').text for div in divs]


def get_book_genre(soup):
    links = soup.select('span.d_book a')
    if links:
        return [link.text for link in links]


def download_image(url, filename, folder='images/'):
    response = requests.get(url)
    response.raise_for_status()
    raise_for_redirect(response)
    ensure_dir(folder)
    img_extension = get_extension(url)
    path = os.path.join(folder, filename) + img_extension
    with open(path, 'wb') as file:
        file.write(response.content)
    return path


def download_txt(url, filename, folder='books/'):
    response = requests.get(url)
    response.raise_for_status()
    raise_for_redirect(response)
    if 'text/plain' in response.headers['Content-Type']:
        ensure_dir(folder)
        sanitized_filename = sanitize_filename(filename)
        path = os.path.join(folder, sanitized_filename) + '.txt'
        with open(path, 'wb') as file:
            file.write(response.content)
        return path


def get_book_links(url):
    links = []
    response = requests.get(url)
    response.raise_for_status()
    raise_for_redirect(response)
    soup = BeautifulSoup(response.text, 'lxml')
    book_cards = soup.select('table.d_book')
    for card in book_cards:
        book_relative_url = card.select_one('a')['href']
        links.append(urljoin(url, book_relative_url))
    return links


def get_args():
    load_dotenv()
    file_path = os.getenv("FILE_PATH")

    parser = argparse.ArgumentParser(
        description='Parser for an online library tululu.org')
    parser.add_argument('--start_page',
                        default='1',
                        type=int,
                        help='Page to start parsing with, can\'t be less than 1 ')
    parser.add_argument('--end_page',
                        default='701',
                        type=int,
                        help='Page until which books should be parsed')
    parser.add_argument('--file_path',
                        default=file_path,
                        type=str,
                        help='Filename (with extension) where the books metadata is stored')
    return parser.parse_args()


def collect_book(soup, html_page_url):
    title, author = get_book_title_author(soup)
    comments = get_book_comments(soup)
    genres = get_book_genre(soup)
    book_num = html_page_url.replace('http://tululu.org/b', '').replace('/', '')
    img_url = get_image_url(soup, html_page_url)
    img_path = download_image(img_url, book_num, folder='images/')
    txt_version_url = 'http://tululu.org/txt.php?id={}'.format(book_num)
    book_path = download_txt(txt_version_url, title, folder='books/')
    return {
        'title': title,
        'author': author,
        'img_src': img_path,
        'book_path': book_path,
        'comments': comments,
        'genres': genres
    }


if __name__ == '__main__':
    logging.basicConfig(level=logging.ERROR)
    args = get_args()

    books = []
    all_links = []

    for num in range(args.start_page, args.end_page):
        try:
            url = 'http://tululu.org/l55/{}/'.format(num)
            all_links.extend(get_book_links(url))
        except requests.exceptions.HTTPError:
            logging.exception('Can\'t download site page')
    for html_page_url in all_links:
        try:
            response = requests.get(html_page_url)
            response.raise_for_status()
            raise_for_redirect(response)
            if response.url == 'http://tululu.org/':
                continue
            soup = BeautifulSoup(response.text, 'lxml')
            book = collect_book(soup, html_page_url)
            books.append(book)
        except requests.exceptions.HTTPError:
            logging.exception('Can\'t download book page, skipping')

    with open(args.file_path, 'w') as my_file:
        json.dump(books, my_file, ensure_ascii=False)
