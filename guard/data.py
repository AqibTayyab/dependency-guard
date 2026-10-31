# SPDX-License-Identifier: Apache-2.0
"""Small list of very popular package names, used to spot typosquats.
Stretch goal: replace this with a ranked list loaded from Snowflake."""

POPULAR = {
    "npm": frozenset("""
        lodash express react react-dom axios chalk commander request moment debug async underscore
        uuid vue webpack typescript eslint jquery bluebird colors minimist yargs glob rimraf mkdirp
        semver tslib dotenv cors body-parser jsonwebtoken mongoose next prop-types classnames
        inquirer ws node-fetch event-stream left-pad core-js rxjs redux jest mocha babel-core
        cross-env nodemon prettier
    """.split()),
    "pypi": frozenset("""
        requests numpy pandas flask django urllib3 boto3 botocore setuptools pip six certifi idna
        charset-normalizer pyyaml cryptography pytest scipy matplotlib pillow jinja2 click sqlalchemy
        beautifulsoup4 lxml tqdm colorama attrs packaging python-dateutil pytz selenium tensorflow
        torch scikit-learn fastapi pydantic aiohttp openpyxl psycopg2 redis paramiko httpx
    """.split()),
}
