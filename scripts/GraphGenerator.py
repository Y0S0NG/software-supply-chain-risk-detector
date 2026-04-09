import random
from collections import deque
from httpx import HTTPError
import requests
from .PackageNode import PackageNode

# class PackageNode:
#     def __init__(self, package):
#         self.package_id = package
#         self.features = None
#         self.depends_on = set()

class GraphGenerator:
    '''
    This is a helper class that model package dependency relationship in graph
    '''
    def __init__(self, seed_package_name, seed_package_version=None, systems='pypi', bfs_depth=3):
        '''
        Initialize the first layer of dependency graph with seed_package
        '''
        self.systems = systems
        self.levels = []
        self.nodes_map = {}
        self.bfs_depth = bfs_depth
        
        print('[GraphGenerator] Initializing 1st layer of the graph...')

        # Select a random version of the seed package if not provided
        if not seed_package_version:
            seed_package_version = self.fetch_random_version(seed_package_name, self.systems)

        # Get nodes and edges
        nodes, edges = self.fetch_dependencies(seed_package_name, seed_package_version)
        
        # map package name + version to a node id
        # construct the node map

        node_list = []
        for node in nodes:
            package_name = node['versionKey']['name']
            version = node['versionKey']['version']
            node_id  = f'{package_name}@{version}'

            package_node = PackageNode(node_id)
            self.nodes_map[node_id] = package_node            
            
            node_list.append(package_node)
            

        # Update PackageNode.depends_on using edges
        for edge in edges:
            from_node_idx = edge['fromNode']
            from_node = node_list[from_node_idx]
            to_node_idx = edge['toNode']
            to_node = node_list[to_node_idx]

            from_node.depends_on.add(to_node.package_id)

        # Store the first level of nodes
        self.levels.append([package.package_id for package in node_list])

        # Print level
        print(f'Level: {self.bfs_depth}')
        print(self.levels)

        # Expand the graph using bfs
        self._bfs_graph_construction(node_list[1:])


    def fetch_dependencies(self, package_name, version):
        print('[GraphGenerator] Fetching dependencies...')
        dependencies_url = f'https://api.deps.dev/v3alpha/systems/{self.systems}/packages/{package_name}/versions/{version}:dependencies'
        dependencies_response = requests.get(dependencies_url)
        if dependencies_response.status_code != 200:
            print(dependencies_response.status_code)
            raise HTTPError(f'Error when fetching dependencies for {package_name}; Request status code: {dependencies_response.status_code}')
        response_body = dependencies_response.json()
        nodes = response_body['nodes']
        edges = response_body['edges']
        return nodes, edges

    @staticmethod
    def fetch_random_version(package_name, system):
        print('[GraphGenerator] Package version is not provided, selecting a random version...')
        get_package_url = f'https://api.deps.dev/v3alpha/systems/{system}/packages/{package_name}'
        package_response = requests.get(get_package_url)
        if package_response.status_code != 200:
            print(package_response.status_code)
            raise HTTPError(f'Error when fetching dependencies for {package_name}; Request status code: {package_response.status_code}')
        response_body = package_response.json()
        versions = [item['versionKey']['version'] for item in response_body['versions']]
        return random.choice(versions)
    
    def _bfs_graph_construction(self, queue):
        q = deque(queue)
        while q:
            self.bfs_depth -= 1
            if self.bfs_depth == 0:
                break
            
            level_list = []

            for _ in range(len(q)):
                cur_package = q.popleft()
                cur_package_id = cur_package.package_id
                cur_package_name, cur_package_version = cur_package_id.split("@", 1)

                cur_dependencies_nodes, cur_dependencies_edges = self.fetch_dependencies(cur_package_name, cur_package_version)

                nodes_list = []
                for node in cur_dependencies_nodes:
                    package_name = node['versionKey']['name']
                    version = node['versionKey']['version']
                    node_id  = f'{package_name}@{version}'

                    # Check if the node already in nodes_map
                    if node_id not in self.nodes_map:
                        # Create a new Package Node
                        package_node = PackageNode(node_id)
                        self.nodes_map[node_id] = package_node
                        level_list.append(package_node)
                    else:
                        # Directly read from self.nodes_map
                        package_node = self.nodes_map[node_id]
                    
                    nodes_list.append(package_node)
                    

                # Update PackageNode.depends_on using edges
                for edge in cur_dependencies_edges:
                    from_node_idx = edge['fromNode']
                    from_node = nodes_list[from_node_idx]
                    to_node_idx = edge['toNode']
                    to_node = nodes_list[to_node_idx]

                    from_node.depends_on.add(to_node.package_id)
            
            for package in level_list:
                q.append(package)
            
            # Store the level
            self.levels.append([package.package_id for package in level_list])
            print(f'Level: {self.bfs_depth}')
            print(self.levels)




