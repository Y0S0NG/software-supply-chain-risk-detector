from FeatureGenerator import FeatureGenerator
import requests
import random
system = 'pypi'
import time

packages = []

with open("pypi_packages.txt", "r") as f:
    for line in f:
        packages.append(line.strip())
print(len(packages))

count = 0
sampled_packages = random.sample(packages, 5000)
with open("safe_packages.txt", "w") as f_safe:
    for package in sampled_packages:
        count += 1
        if count % 500 == 0:
            time.sleep(5)
        print(f"Processing {count} package")
        get_package_url = f'https://api.deps.dev/v3alpha/systems/{system}/packages/{package}'
       
        response = requests.get(get_package_url,timeout=10)
        if response.status_code == 200:
            print(f'Start fetching {package}\'s default version')
            response_body = response.json()

            package_version = next(item['versionKey']['version'] for item in response_body['versions'] if item['isDefault'] == True)
            print(f"Default version: {package_version}")

            f_safe.write(f"{package}@{package_version}\n")

