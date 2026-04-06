from collections import deque
import requests
from PackageNode import PackageNode

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

        # Get the default version of the seed package if not provided
        if not seed_package_version:
            seed_package_version = self._fetch_default_version(seed_package_name)

        # Get nodes and edges
        nodes, edges = self._fetch_dependencies(seed_package_name, seed_package_version)
        
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



    def _fetch_dependencies(self, package_name, version):
        print('[GraphGenerator] Fetching dependencies...')
        dependencies_url = f'https://api.deps.dev/v3alpha/systems/{self.systems}/packages/{package_name}/versions/{version}:dependencies'
        dependencies_response = requests.get(dependencies_url).json()
        nodes = dependencies_response['nodes']
        edges = dependencies_response['edges']
        return nodes, edges

    def _fetch_default_version(self, package_name):
        print('[GraphGenerator] Package version is not provided, checking default version...')
        get_package_url = f'https://api.deps.dev/v3alpha/systems/{self.systems}/packages/{package_name}'
        package_response = requests.get(get_package_url).json()
        seed_package_version = next(item['versionKey']['version'] for item in package_response['versions'] if item['isDefault'] == True)
        return seed_package_version
    
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

                cur_dependencies_nodes, cur_dependencies_edges = self._fetch_dependencies(cur_package_name, cur_package_version)

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
            



