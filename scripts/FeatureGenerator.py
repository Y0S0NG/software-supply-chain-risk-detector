import requests


class FeatureGenerator:
    def __init__(self, system):
        self.system = system
        
    def get_security_advisory(self, package, version):
        get_version_url = f"https://api.deps.dev/v3/systems/{self.system}/packages/{package}/versions/{version}"
        version_response = requests.get(get_version_url).json()
        advisory_keys = version_response['advisoryKeys']

        # No advisory records
        if len(advisory_keys) == 0:
            return []
        
        # Call getAdvisory API and get vulnerabilities
        vulnerabilities = []
        for advisory in advisory_keys:
            advisory_id = advisory["id"]
            get_advisory_url =f"https://api.deps.dev/v3/advisories/{advisory_id}"
            vulnerability = requests.get(get_advisory_url).json()
            vulnerabilities.append(vulnerability)
        
        return vulnerabilities
    
    def get_full_features(self, package_id, nodes_map):
        full_metadata = []
        col_names = []

        package, version = package_id.rsplit('@', 1)
        package_metadata = self.get_package_metadata(package, version)
        
        package_node =nodes_map.get(package_id)
        structural_metadata = self.get_structural_metadata(package_node, nodes_map)

        package_feature_order = [
            "package_name",
            "package_version",
            "num_authors",
            "num_maintainers",
            "has_license",
            "yanked",
            "has_project_url",
            "has_package_url",
            "has_release_url",
            "python_requirement",
            "has_organization",
            "num_roles",
            "num_distributions",
        ]
        structural_feature_order = ["in_degree", "out_degree"]

        col_names = package_feature_order + structural_feature_order
        full_metadata = [package_metadata.get(c) for c in package_feature_order] + \
                        [structural_metadata.get(c) for c in structural_feature_order]

        return {"full_metadata": full_metadata, "col_names": col_names}



    def get_package_metadata(self, package, version):
        metadata_map = {"package_name": package, "package_version": version}
        features = [
            'num_authors',
            'num_maintainers',
            'has_license',
            'yanked',
            'has_project_url',
            'has_package_url',
            'has_release_url',
            'python_requirement',
            # 'description',
            'has_organization',
            'num_roles',
            'num_distributions'
        ]

        if self.system == 'pypi':
            # get metadata by pypi API
            get_package_metadata_url = f"https://pypi.org/{self.system}/{package}/{version}/json"
            metadata_response = requests.get(get_package_metadata_url).json()
            if not metadata_response:
                return {}
            
            # parse info
            info = metadata_response.get('info', {})
            author_email = info.get("author_email") or ""
            maintainer_email = info.get("maintainer_email") or ""
            num_authors = len([e.strip() for e in author_email.split(",") if e.strip()])
            num_maintainers = len([e.strip() for e in maintainer_email.split(",") if e.strip()])
            license_files = info.get("license_files") or []
            has_license = len(license_files) > 0
            yanked = info.get('yanked')
            has_project_url = bool(info.get("project_url"))
            has_package_url = bool(info.get("package_url"))
            has_release_url = bool(info.get("release_url"))
            # -------------------------------------------- #
            python_requirement = info['requires_python'] or "" # Don't know how to process
            # description = info['description'] or "" # Do not know how to vectorize, NLP? will that help with vulnerability detection?
            
            # parse ownership
            ownership = metadata_response['ownership']
            has_organization = (ownership['organization'] != None)
            num_roles = len(ownership['roles'])

            # parse urls
            num_distributions = len(metadata_response['urls'])

            # Merge all constructed feature variables into metadata in one step
            local_vars = locals()
            metadata_map.update({name: local_vars[name] for name in features})

        return metadata_map
    
    def get_structural_metadata(self, node, nodes_map):
        structural_metadata_map = {} # in_degree and out_degree

        if not nodes_map:
            return {"in_degree": 0, "out_degree": 0}

        node_id = node.package_id

        if node is None:
            return {"in_degree": 0, "out_degree": 0}

        out_degree = len(node.depends_on)

        in_degree = 0
        for other_node in nodes_map.values():
            if node_id in other_node.depends_on:
                in_degree += 1

        structural_metadata_map["in_degree"] = in_degree
        structural_metadata_map["out_degree"] = out_degree
        return structural_metadata_map
