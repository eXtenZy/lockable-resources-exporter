import argparse
import logging
import os
import requests
import time
import yaml
from urllib.parse import urlparse
from requests.exceptions import RequestException
from prometheus_client import Counter, Enum, Gauge, Summary
from prometheus_client.exposition import start_http_server

# Create a metric to track time spent and requests made.
REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request', ['alias'])
REQUEST_CODE = Counter('request_codes', 'Request status code', ['alias', 'code'])
STATE = Enum('resource_state', 'Description of enum', ['alias', 'name'], states=['available', 'locked', 'reserved'])
LABELS = Gauge('available_labels', "Available labels", ['alias', 'label', 'state'])


def load_yaml_config(file_name):
    yaml_object = None

    try:
        with open(file_name, 'r') as yaml_file:
            yaml_object = yaml.load(yaml_file, Loader=yaml.SafeLoader)
    except FileNotFoundError:
        print(f"{file_name} does not exist")

    return yaml_object


def process_request(alias, url, user=None, token=None, verify=True):
    request_params = dict()
    if user is not None and token is not None:
        request_params['auth'] = (user, token)

    if url[-1] == '/':
        request_params['url'] = url + 'plugin/lockable-resources/api/json'
    else:
        request_params['url'] = url + '/plugin/lockable-resources/api/json'

    request_params['verify'] = verify
    with REQUEST_TIME.labels(alias).time():
        result = requests.get(**request_params)

    REQUEST_CODE.labels(alias, result.status_code).inc()

    # Raise an exception if the result is not usable (HTTP Code is in 400-599 range)
    result.raise_for_status()

    labels = dict()
    resources = result.json()['resources']

    logging.debug(f"Found {len(resources)} resources on {alias}.")

    for resource in resources:
        for label in resource['labels'].split():
            if label not in labels:
                labels[label] = dict()
                labels[label]['available'] = 0
                labels[label]['locked'] = 0
                labels[label]['reserved'] = 0

        if resource['locked']:
            STATE.labels(alias, resource['name']).state('locked')
            for label in resource['labels'].split():
                labels[label]['locked'] += 1
        elif resource['reserved']:
            STATE.labels(alias, resource['name']).state('reserved')
            for label in resource['labels'].split():
                labels[label]['reserved'] += 1
        else:
            STATE.labels(alias, resource['name']).state('available')
            for label in resource['labels'].split():
                labels[label]['available'] += 1

    for label_name, label_values in labels.items():
        for key, value in label_values.items():
            LABELS.labels(alias, label_name, key).set(value)


def main(configuration):
    # Start up the server to expose the metrics.
    logging.info(f"Starting server on {configuration.metrics_url}:{configuration.metrics_port}")
    start_http_server(port=configuration.metrics_port, addr=configuration.metrics_url)

    while True:
        for instance in configuration.instances:

            try:
                logging.info(f"Checking {instance['alias']}.")
                process_request(**instance)
            except RequestException as exception:
                logging.error("Error occurred:")
                logging.exception(exception)

        time.sleep(settings.polling_time)


if __name__ == '__main__':
    arguments = argparse.ArgumentParser(description="Jenkins Lockable Resources Plugin Prometheus exporter")
    group = arguments.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", type=str, default=os.environ.get('JENKINS-URL'),
                       help="URL of the Jenkins instance to pull information from.")
    group.add_argument("-c", "--config", type=str, default=os.environ.get('CONFIG'),
                       help="Configuration file location.")

    arguments.add_argument("--username", type=str, default=os.environ.get('JENKINS_USER'),
                           help="User to authenticate on the Jenkins instance.")
    arguments.add_argument("--token", type=str, default=os.environ.get('JENKINS_TOKEN'),
                           help="User token to authenticate on the Jenkins instance.")
    arguments.add_argument("--alias", type=str, default=os.environ.get('JENKINS_ALIAS'),
                           help="Alias name for the Jenkins instance.")

    arguments.add_argument("-t", "--polling-time", type=int, default=os.environ.get('POLLING_TIME', 60),
                           help="Interval for polling the Jenkins instance(s) for gathering data. Unit is seconds.")
    arguments.add_argument("--metrics-url", type=str, default=os.environ.get('METRICS_URL', '0.0.0.0'),
                           help="Port on which to expose the gathered metrics. Default: %(default)s")
    arguments.add_argument("--metrics-port", type=int, default=os.environ.get('METRICS_PORT', 8080),
                           help="Port on which to expose the gathered metrics. Default: %(default)s")
    arguments.add_argument("-l", "--logging", dest="logLevel", default='INFO',
                           help="Set logging level. Default: %(default)s",
                           choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])

    # Load configuration.
    settings = arguments.parse_args()

    settings.instances = list()
    logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.getLevelName(settings.logLevel))
    logging.debug("Parsing configuration")

    if settings.config is not None and os.path.isfile(settings.config):
        try:
            yaml_config = load_yaml_config(settings.config)
            settings = argparse.Namespace(**yaml_config)
        except yaml.YAMLError as e:
            logging.error("Error opening configuration file.")
            logging.error(e)

    else:
        jenkins_instance = dict()
        jenkins_instance['url'] = settings.url
        if settings.alias is not None:
            jenkins_instance['alias'] = settings.alias
        else:
            jenkins_instance['alias'] = urlparse(jenkins_instance['url']).hostname

        if settings.username is not None:
            jenkins_instance['user'] = settings.username
            if settings.token is not None:
                jenkins_instance['token'] = settings.token

        settings.instances.append(jenkins_instance)

    logging.debug(f"Found {len(settings.instances)} instances: "
                  f"{', '.join([item['alias'] for item in settings.instances])}")
    logging.debug(f"Polling every {settings.polling_time} seconds.")

    main(settings)
