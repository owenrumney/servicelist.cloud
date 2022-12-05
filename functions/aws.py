import requests
import json
import unicodedata
import boto3
import urllib
import os

from bs4 import BeautifulSoup
from datetime import datetime

base_url = 'https://docs.aws.amazon.com'


def get_service_list():
    url = '{}/en_us/main-landing-page.xml'.format(base_url)
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


def create_service_dictionary(content, services,  category):
    for service in content.find_all('service'):
        name = service.find('name').text
        if name == 'General Reference':
            continue
        docs_url = service.get('href').replace(
            '?id=docs_gateway', 'index.html')
        landing_url = docs_url.replace('index.html', 'en_us/landing-page.xml')
        if 'http' not in docs_url:
            values = get_or_create(services, name)
            values['docs_url'] = '{}{}'.format(base_url, docs_url)
            values['landing_url'] = '{}{}'.format(base_url, landing_url)
            values['category'].append(category)
            values['name'] = name
    return services


def generate_sorted_list(services):
    for service in sorted(services.keys()):
        doc_url = services[service]
        print(service, doc_url)


def create_services_file(services):
    for service in services.get('services'):
        print('processing {}'.format(service))
        landing_url = service.get('landing_url')
        content = BeautifulSoup(requests.get(
            landing_url).content, os.environ.get('parser', 'html.parser'))
        landingEl = content.find('input', {'id': 'landing-page-xml'})
        if not landingEl:
            continue
        xml = urllib.parse.unquote(landingEl.get('value'))

        landing_xml = BeautifulSoup(
            xml, os.environ.get('parser', 'html.parser'))

        abstract = landing_xml.find('abstract')

        if abstract and abstract.text != '':
            service['abstract'] = str(abstract.text.replace("\n", " "))
        else:
            service['abstract'] = 'No description available, click for more documentation'
        del (service['landing_url'])

    for service in services:
        if not service.get('abstract'):
            service['abstract'] = 'No description available, click for more documentation'

    with open('/tmp/services.json', 'w') as f:
        f.write(json.dumps(services))

    s3 = boto3.resource('s3')
    s3.Bucket('servicelist.cloud').upload_file('/tmp/services.json',
                                               os.environ.get('s3key', 'services.json'))
    s3.Bucket('aws.servicelist.cloud').upload_file(
        '/tmp/services.json', 'services.json')


def lambda_handler(event, context):
    content = get_service_list()
    services = []
    categories = []
    for tile in content.find_all('list-card'):
        services_el = tile.find('list-card-items')
        category = tile.find('title').text
        if category in ['General Reference', 'Featured Services']:
            continue
        if services_el:
            categories.append(category)
            create_service_dictionary(services_el, services, category)

    data = {'last_updated': "{:%B %d, %Y}".format(
        datetime.now()), 'services': services,
        'categories': sorted(set(categories))}
    create_services_file(data)


if __name__ == '__main__':
    lambda_handler(None, None)
