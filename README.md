![Version](https://img.shields.io/github/release/paulscherrerinstitute/data_board_backend.svg)
![Issues](https://img.shields.io/github/issues/paulscherrerinstitute/data_board_backend)
![Tests](https://img.shields.io/github/actions/workflow/status/paulscherrerinstitute/data_board_backend/test.yml?branch=main&label=tests&logo=github)
![Build Status](https://img.shields.io/github/actions/workflow/status/paulscherrerinstitute/data_board_backend/docker-image.yml?branch=main&label=build&logo=github)

# Data Board Backend

This is the backend for the Data Board project. It is a FastAPI application written in Python that provides routes for the [Data Board Frontend](https://github.com/paulscherrerinstitute/data_board_frontend).

---

## 🧭 Routes

For a list of routes, visit `/docs` (or `/api/docs` if running behind the [frontend's nginx proxy](https://github.com/paulscherrerinstitute/data_board_frontend/blob/main/default.conf)).

## 💻 Development

### Requirements

To begin with, make sure your commits are signed and the corresponding public key is uploaded to GitHub.

#### Dependencies

Depending on what you want to do, you may either install:

- [requirements.txt](requirements.txt)
  - To simply run the application and change things locally only
- [testing_requirements.txt](testing_requirements.txt)
  - To additionally run the test
- [development_requirements.txt](development_requirements.txt)
  - To run [pre-commit hooks](#pre-commit-hooks), for pushing changes, in addition to all of the above

This documentation assumes you install the dependencies in a [venv](https://docs.python.org/3/library/venv.html), and listed commands are executed in this venv.

#### Pre-Commit Hooks

If you want to push changes, you need to enable pre-commit hooks. After installing the neccessary [dependencies](#dependencies), install the hooks using `pre-commit install`. Now, the pre-commit hooks defined in [.pre-commit-config.yaml](.pre-commit-config.yaml) are executed by Git upon committing, blocking a commit if any of them fail.

Some of those hooks automatically update the changed files to make their tests pass. In those cases, the respective hook fails but indicates that it changed some files. You then need to manually verify those changes and add them to Git and commit again. Detected issues that cannot be auto-resolved will simply be displayed, and you will need to fix them yourself.

To run the hooks manually, you can do `pre-commit run --all-files`.

### Running Locally

Within the venv, you can simply run `fastapi dev` for a local instance. For production mode, use `fastapi run`.

> ⚠️ **Important:** The application won't start if it fails to establish a connection to the DB. Ensure you have an instance of MongoDB running, and [configured](#configuration) the connection for it. You can simply start a container using `docker run -d --name mongodb -p 27017:27017 -e MONGO_INITDB_DATABASE=databoard mongo:latest`, this should not require any configuration. However, this also won't be persistent.

### Configuration

You can configure the application using the following environment variables:

- `SCHEMA_PATH`  
  URL or file path to the dashboard schemas. Defaults to [the schema folder of the Data Board Frontend](https://github.com/paulscherrerinstitute/data_board_frontend/tree/main/schema).

- `VALIDATE_DASHBOARD_SCHEMA`  
  Enables or disables schema validation for dashboards. Schema validation checks each dashboard to be stored or updated, and if it doesn't exactly match a given schema, the operation is rejected. This way, it will be a bit more cumbersome to use the backend as free cloud. Accepts boolean-like strings (`"1"`, `"true"`, `"yes"`, `"on"`). Defaults to `true`.

- `VALIDATE_DASHBOARD_SIZE`  
  Enables or disables size validation for dashboards. Accepts boolean-like strings (`"1"`, `"true"`, `"yes"`, `"on"`). Defaults to `true`.

- `DASHBOARD_MAX_SINGLE_BYTES`  
  Maximum allowed size per individual dashboard in bytes. Defaults to 10MB.

- `DASHBOARD_MAX_TOTAL_STORAGE_BYTES`  
  Maximum total storage allowed for dashboards in bytes. Defaults to 10GB.

- `DASHBOARD_EVICTION_THRESHOLD`  
  Storage usage ratio at which eviction of old dashboards begins. When that happens, dashboards are ordered by when they were last fetched / updated, and then deleted from oldest to newest until the target utilization (see below) is reached. [Whitelisted](#whitelisting) dashboards are ignored. Defaults to `0.95` (95%).

- `DASHBOARD_TARGET_UTILIZATION`  
  Target storage utilization ratio to reduce to after eviction. Defaults to `0.60` (60%).

- `MONGO_HOST`  
  Hostname or IP address of the MongoDB server. Defaults to `"localhost"`.

- `MONGO_PORT`  
  Port number for the MongoDB server. Defaults to `27017`.

- `MONGO_DB_NAME`  
  Name of the MongoDB database to use. Defaults to `"databoard"`.

- `ROOT_PATH`  
  Root path under which the backend is reachable. Needs to be configured if running behind proxy. Defaults to `"/"`.

There may be additional possibilities to configure [DataHub](https://github.com/paulscherrerinstitute/datahub/blob/main/Readme.md).

### Linting / Formatting

If you have the according [dependencies](#dependencies), you can lint & format using the [pre-commit-hooks](#pre-commit-hooks).

### Testing

If you have the according [dependencies](#dependencies), you can test the application by simply running `pytest`. The tests require docker to be available. To view the coverage in your editor, you can use an extension like [Coverage Gutters](https://marketplace.visualstudio.com/items?itemName=ryanluker.vscode-coverage-gutters) for VSCode.

> ⚠️ **Important:** The tests **will** fail if not all routes have tests defined. So if any routes are added, implement at least one test for it.

### Deployment

There is a [Dockerfile](Dockerfile) for running the backend as a container. There is also a [docker compose](docker-compose.yml), which can be used to start the backend, a DB, and the [frontend](https://github.com/paulscherrerinstitute/data_board_frontend/) all together.

All services together create a fully working Data Board application. For deployment on a remote machine, there is also an [ansible script to run](docker_pull_and_run.yml) as well as an [ansible script to stop](docker_stop_and_remove.yml) all services as together as docker containers. The containers are grouped in a docker network, with only the frontend having its port mapped to the host, therefore being the only exposed service. API requests are forwarded by the [frontend's nginx proxy](https://github.com/paulscherrerinstitute/data_board_frontend/blob/main/default.conf)

By default, both ways of deploying the whole application use the most recent docker image of the services tagged with `latest`. Using arguments/environment variables, it is also possible to change that to use local images.

> ⚠️ **Important:** The [docker compose script](docker-compose.yml) uses cached images if available. To prevent it from using outdated images, run `docker compose pull`.

### Notes for Production

#### Maintenance Routes

Some routes are defined using a `maintenance_router`. These routes are configured to have the prefix `/maintenance/`. This prefix is configured in the [frontend's nginx proxy](https://github.com/paulscherrerinstitute/data_board_frontend/blob/main/default.conf), such that all requests to a route with this prefix are denied.

> ⚠️ **Important:** This forwarding is only effective when deploying the bundled application using either the [ansible script](docker_pull_and_run.yml) or the [docker compose script](docker-compose.yml).

The maintenance routes can therefore only be called from within the docker network. To use them, simply connect yourself to the docker network, from the machine it's running on. These routes are not meant to allow for any super sensitive or security-critical operations, they simply aid in certain configuration tasks, which should not directly be exposed to the users. They should never be treated as authorized routes, though, since they are not.

To see a list of all maintenance routes, visit `/docs` (or `/api/docs` if running behind the [frontend's nginx proxy](https://github.com/paulscherrerinstitute/data_board_frontend/blob/main/default.conf)).

##### Whitelisting

`POST /maintenance/dashboard/{id}/whitelist`  
Whitelists the dashboard: it won't be auto-deleted when storage is low.

`DELETE /maintenance/dashboard/{id}/whitelist`  
Removes the dashboard from the whitelist: it can be auto-deleted again.

##### Protecting

`POST /maintenance/dashboard/{id}/protect`  
Protects the dashboard: it becomes read-only.  
Also implicitly whitelists it (to avoid deletion).  
If you want it protected _but_ auto-deletable, unwhitelist it after protecting.

`DELETE /maintenance/dashboard/{id}/protect`  
Removes protection: dashboard becomes writable again.  
Does **not** change whitelisting.

##### Getting full DB Records

`GET /maintenance/dashboard/{id}`  
Returns the full dashboard record in JSON, including all mongo fields.

#### Maintainer-Tools

The backend container includes a [script](migrate_whitelisted_dashboards.sh) at `/app/migrate_whitelisted_dashboards.sh`. This script allows dumping all whitelisted dashboards to a JSON file and importing them back. It also supports importing/exporting **all** dashboards in the database using optional flags. To see all options, run the script without parameters.

This is useful for migrating dashboards when purging the MongoDB container and image. Restarting the container will reuse the named Docker volume `mongo_data_volume`, which is mounted to `/data/db` inside the MongoDB container. Even if a new or different image is used for the Mongo container, the data will persist.

However, when upgrading the Mongo image or in certain other cases, it might be necessary to purge `/data/db`. In such cases, you can back up dashboards using the script beforehand.

> ⚠️ **Important:** Make sure to save the JSON dump to the host, not inside the container, as container data will be lost on removal.

---

## 🤝 Contributing / Issues

If you find any bugs, please open a GitHub issue.

If you want to add a feature or extend the application in any other way, please get in contact with the [current maintainer](#contact--support).

For any contribution to be merged, all pipelines need to be successful, and the linter should not give any errors.

---

## Contact / Support

The current maintainer is Erik Schwarz <erik.schwarz{at}psi.ch>

---

<div style="text-align: center; margin-top: 20px;">
<img src="https://raw.githubusercontent.com/paulscherrerinstitute/data_board_frontend/main/public/logo512.png" alt="DataBoard Logo"  style="filter: grayscale(100%) contrast(1000%);" />

</div>
