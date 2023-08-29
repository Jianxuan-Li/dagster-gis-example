# Dagster example for GIS data

An example of utilizing [Dagster](https://dagster.io/) for processing and analyzing GIS data.

<img src="./docs/1.png" height="320">
<img src="./docs/2.png" height="320">

## Main GIS Features

* GDAL 3.6.2 installed
* PostGIS 3.3 (Postgresql 15) ready to use

## development

### requirements

* [docker](https://docs.docker.com/get-docker/) (with docker-compose) installed
* if you are using Windows, install make first: `choco install make`. But `WSL2` is recommended.

### start the development server

* create `.env.local` file
* run `make up` to start the development containers
* run `make dev` in the created container to start the development server

### Tips:

* installed packages are cached for the next use.
* exit the container, then run `make down` to stop the containers
