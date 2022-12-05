import requests
import json
import unicodedata
import boto3
import urllib
import os

from bs4 import BeautifulSoup
from datetime import datetime

base_url = 'https://cloud.google.com/'


def get_service_list():
    url = '{}products'.format(base_url)
    resp = requests.get(url)
    if resp.status_code != 200:
        exit(-1)
    return BeautifulSoup(resp.content,  os.environ.get('parser', 'html.parser'))


def get_or_create(services, name):
    for service in services:
        if service.get('name') == name:
            return service
    new_service = {'category': []}
    services.append(new_service)
    return new_service


def create_service_dictionary(service, services,  category):
    docs_url = service.get('href')
    name = service.find('div', {'class': 'cws-headline'})
    abstract = service.find('div', {'class': 'cws-body'})

    values = get_or_create(services, name)
    values['docs_url'] = docs_url
    values['category'].append(category)
    values['name'] = name.text
    values['abstract'] = abstract.text
    return services


def generate_sorted_list(services):
    for service in sorted(services.keys()):
        doc_url = services[service]
        print(service, doc_url)


def create_services_file(services):
    for service in services.get('services', []):
        if not service.get('abstract'):
            service['abstract'] = 'No description available, click for more documentation'

    with open('/tmp/services.json', 'w') as f:
        f.write(json.dumps(services))

    s3 = boto3.resource('s3')
    s3.Bucket('gcp.servicelist.cloud').upload_file('/tmp/services.json',
                                                   os.environ.get('s3key', 'services.json'))


def lambda_handler(event, context):
    content = get_service_list()
    services = []
    categories = []
    for tile in content.find_all('section', {'class': 'link-card-grid-section'}):
        category = tile.find(
            'h2', {'class': 'link-card-grid-module__headline'}).text.replace('\n', '').strip()
        if category in ["Featured products", "More cloud offerings"]:
            continue
        services_el = tile.find_all('a', {'class': 'cws-card'})
        if services_el:
            categories.append(category)
            for service_el in services_el:
                create_service_dictionary(service_el, services, category)

    data = {'last_updated': "{:%B %d, %Y}".format(
        datetime.now()), 'services': services,
        'categories': sorted(set(categories))}
    create_services_file(data)


if __name__ == '__main__':
    lambda_handler(None, None)
