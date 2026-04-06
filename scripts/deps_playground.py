# This script similate an iteration of graph expansion process

import requests
# the 'very seed package'
seed_package_name = 'scipy'
get_package_url = f'https://api.deps.dev/v3alpha/systems/pypi/packages/{seed_package_name}'

# get the default version of the seed package
package_response = requests.get(get_package_url).json()
default_version = next(item['versionKey']['version'] for item in package_response['versions'] if item['isDefault'] == True)
get_default_version_url = f'https://api.deps.dev/v3alpha/systems/pypi/packages/{seed_package_name}/versions/{default_version}'
version_response = requests.get(get_default_version_url).json()
print(f'Default version of {seed_package_name} is {default_version}')

# get dependencies with the version
dependencies_url = f'https://api.deps.dev/v3alpha/systems/pypi/packages/{seed_package_name}/versions/{default_version}:dependencies'
dependencies_response = requests.get(dependencies_url).json()
print(f'Dependencies of {seed_package_name} version {default_version}:')
print(dependencies_response)


# map package name + version to a node id
node_map = {}

# construct the node map
for i, node in enumerate(dependencies_response['nodes']):
    seed_package_name = node['versionKey']['name']
    version = node['versionKey']['version']
    node_id  = f'{seed_package_name}@{version}'
    node_map[node_id] = i

edges = []
# construct edge list
for edge in dependencies_response['edges']:
    from_node = edge['fromNode']
    to_node = edge['toNode']
    edges.append([from_node, to_node])




