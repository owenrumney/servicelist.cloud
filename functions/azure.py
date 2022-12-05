import json
import os
from datetime import datetime

import boto3
import requests
from bs4 import BeautifulSoup

base_url = 'https://docs.microsoft.com/en-us/azure/'


def get_service_list():
    url = '{}?products=all'.format(base_url)
    resp = requests.get(url)
    if resp.status_code != 200:
        exit(-1)
    return BeautifulSoup(resp.content, os.environ.get('parser', 'html.parser'))


def get_or_create(services, name):
    for service in services:
        if service.get('name') == name:
            return service
    new_service = {'category': []}
    services.append(new_service)
    return new_service


def create_service_dictionary(content, services, category):
    for service in content.find_all('a'):
        name = service.text
        docs_url = service.get('href')
        landing_url = docs_url
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


def try_other_abstract(content):
    main = content.find('main')
    if main:
        abstract = main.find('p', recursive=False)
        if abstract and abstract.text != '':
            return abstract.text
        else:
            container = main.find('div', {'class': 'container'})
            if container and container.find('p'):
                return container.find('p').text

    return 'Description not found'


def create_services_file(services):
    for service in services.get('services'):

        landing_url = service.get('landing_url')
        content = BeautifulSoup(requests.get(
            landing_url).content, os.environ.get('parser', 'html.parser'))
        abstract = content.find('section', {'id': 'landing-head'})
        if abstract and abstract.find('p') and abstract.find('p').text != '':
            service['abstract'] = str(abstract.text)
        else:
            service['abstract'] = try_other_abstract(content)
            print('processing {}'.format(service))
        service['abstract'] = service['abstract'].lstrip(
            '{} documentation'.format(service['name'])).strip('\n')
        del (service['landing_url'])

    with open('/tmp/services.json', 'w') as f:
        f.write(json.dumps(services))

    s3 = boto3.resource('s3')
    target_file = os.environ.get('s3key', 'guides/azure/services.json')
    print("Uploading to {}".format(target_file))
    s3.Bucket('servicelist.cloud').upload_file(
        '/tmp/services.json', target_file)
    s3.Bucket('azure.servicelist.cloud').upload_file(
        '/tmp/services.json', 'services.json')


def lambda_handler(event, context):
    content = get_service_list()
    services = []
    categories = []
    for group in content.find_all("div", {"class": "box"}):
        for category_sections in group.find_all('ul'):
            category = category_sections.find_previous_sibling('h3').text
            categories.append(category)
            for service in category_sections.find_all('li'):
                create_service_dictionary(service, services, category)

    data = {'last_updated': "{:%B %d, %Y}".format(
        datetime.now()), 'services': services,
        'categories': sorted(set(categories))}
    create_services_file(data)
