# Lockable Resources Exporter

This is an small [Prometheus](https://prometheus.io/) exporter to gather metrics regarding [Jenkins Lockable Resources Plugin](https://plugins.jenkins.io/lockable-resources/) usage. 

It exposes the configured lockable resources for scraping by Prometheus.

It has the following features:
* Supports multiple Jenkins instances.
* Can expose individual resource usage as well as grouped resources (multiple resources with the same label).
* Each resource can be monitored according to its state: Available, Locked or Reserved.
* Uses the Jenkins JSON REST API endpoint so as to be fast and efficient.

## Running

### Stand-alone
1. Clone the repository
2. Install dependencies from requirements.txt
3. Adjust settings.yaml to suit your environment
4. Run application using command:

   `python src/lockable-resources-exporter.py --config settings.yaml`

### Docker
1. Build Docker image

    `docker build -t lockable-resources-exporter:latest .`
2. Run using command:

    `docker run -p 8080:8080 lockable-resources-exporter:latest --url http://jenkins_host:8080`
