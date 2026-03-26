class GraphGenerator:
    def __init__(self):
        self.node_map = {}
        self.edges = []

    # Implement BFS for graph expansion
    from collections import deque
    def bfs_graph_construction(graph, seed_package_name):
        visited = set()
        deque = deque([seed_package_name])
          # First get the default version of the current package
        get_package_url = f'https://api.deps.dev/v3alpha/systems/pypi/packages/{seed_package_name}'
        package_response = requests.get(get_package_url).json()
        seed_package_version = next(item['versionKey']['version'] for item in package_response['versions'] if item['isDefault'] == True)
        
        while deque:
            current_package = deque.popleft()
            if current_package not in visited:
                visited.add(current_package)
                # Add dependencies to the graph