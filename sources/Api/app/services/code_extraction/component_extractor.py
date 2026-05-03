"""C4 Level 3 Component helper functions."""


def link_components_to_containers(components: dict, containers: dict) -> None:
    """Create relationships between components and their containers."""
    for comp_id, component in components.items():
        container_name = component.get('container')
        for cont_id, container in containers.items():
            if container['name'] == container_name:
                if 'components' not in container:
                    container['components'] = []
                container['components'].append({
                    'id': comp_id,
                    'name': component['name'],
                    'type': component.get('component_type', 'Component')
                })
                component['container_id'] = cont_id
                break
