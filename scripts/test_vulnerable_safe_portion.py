'''
Test the portion of the safe package out of the deafult version of packages out of 5000 randomly selected packages
'''

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

sampled_packages = random.sample(packages, 5000)
count = 0
safe_count = 0
unavailable_count = 0
vulnerable_count = 0
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

        print("Start fetch vulnerability")
        vulnerabilities = FeatureGenerator.get_security_advisory(package, package_version, system)
        if len(vulnerabilities) == 0:
            safe_count += 1
        else:
            vulnerable_count += 1

    elif response.status_code == 429:
        print('Get too much requests!')
        break
    else:
        print("Not Exist")
        unavailable_count += 1
        continue

print(f"Get {safe_count} safe packages")
print(f"Get {vulnerable_count} vulnerable packages")
print(f"Get {unavailable_count} unavailable packages")


