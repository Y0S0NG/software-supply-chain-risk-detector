from FeatureGenerator import FeatureGenerator
import requests
import random
system = 'pypi'
import time

url = "https://pypi.org/simple/"
headers = {
    "Accept": "application/vnd.pypi.simple.v1+json"
}

resp = requests.get(url, headers=headers)
data = resp.json()

packages = [p["name"] for p in data["projects"]]
print(f"PyPI simple API returns totally {len(packages)} packages")


sampled_packages = random.sample(packages, 5000)
count = 0
safe_count = 0
unavailable_count = 0
vulnerable_count = 0
with open("safe_packages.txt", "w") as f_safe, open("vulnerable_packages.txt", "w") as f_vulnerable:
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
                f_safe.write(f"{package}\n")
            else:
                vulnerable_count += 1
                f_vulnerable.write(f"{package}\n")

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


