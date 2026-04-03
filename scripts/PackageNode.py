class PackageNode:
    def __init__(self, package):
        self.package_id = package
        self.features = []
        self.depends_on = set()