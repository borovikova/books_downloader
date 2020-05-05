import requests
import os
from bs4 import BeautifulSoup
from pathvalidate import sanitize_filename
from urllib.parse import urljoin
import json
import argparse
import logging


def ensure_dir(directory):
    os.makedirs(directory, exist_ok=True)

def get_extension(image_url):
    return os.path.splitext(image_url)[1]


def get_book_title_author(soup):
    header = soup.select_one('h1').text
    title, author = header.split('::')
    return (title.strip(), author.strip())


def get_image_url(soup):
    selector = '.bookimage a img'
    img_relative_url = soup.select_one(selector)['src']
    return urljoin('http://tululu.org', img_relative_url)


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
    ensure_dir(folder)
    img_extension = get_extension(url)
    path = os.path.join(folder, filename) + img_extension
    with open(path, 'wb') as file:
        file.write(response.content)
    return path


def download_txt(url, filename, folder='books/'):
    response = requests.get(url)
    response.raise_for_status()
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
    soup = BeautifulSoup(response.text, 'lxml')
    book_cards = soup.select('table.d_book')
    for card in book_cards:
        book_relative_url = card.select_one('a')['href']
        links.append(urljoin('http://tululu.org', book_relative_url))
    return links


if __name__ == '__main__':
    logging.basicConfig(level=logging.ERROR)

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
    args = parser.parse_args()

    books_data = []
    all_links = []

    try:
        for num in range(args.start_page, args.end_page):
            url = 'http://tululu.org/l55/{}/'.format(num)
            all_links.extend(get_book_links(url))

        for url_html in all_links:
            response = requests.get(url_html)
            response.raise_for_status()
            if response.url != 'http://tululu.org/':
                soup = BeautifulSoup(response.text, 'lxml')

                title, author = get_book_title_author(soup)
                comments = get_book_comments(soup)
                genres = get_book_genre(soup)

                book_num = url_html.replace(
                    'http://tululu.org/b', '').replace('/', '')

                img_url = get_image_url(soup)
                img_path = download_image(img_url, book_num, folder='images/')

                url_txt = 'http://tululu.org/txt.php?id={}'.format(book_num)
                book_path = download_txt(url_txt, title, folder='books/')

                book_data = {
                    'title': title,
                    'author': author,
                    'img_src': img_path,
                    'book_path': book_path,
                    'comments': comments,
                    'genres': genres
                }

                books_data.append(book_data)
    except requests.exceptions.HTTPError as e:
        logging.error('Can\'t download a page', exc_info=True)

    with open('books.json', 'w') as my_file:
        json.dump(books_data, my_file, ensure_ascii=False)
