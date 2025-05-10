# roles.py

ROLE_DISPLAY_NAMES = {
    'material_lab_manager': 'Material Lab Manager',
    'head_rd': 'Head of R&D',
    'lab_engineer': 'Laboratory Engineer',
    'guest': 'Guest'
}

PRIVILEGES = {
    'material_lab_manager': [
        'create_equipment', 'add_maintenance', 'upload_spec', 'upload_report',
        'view_equipment', 'view_quotations', 'mark_maintenance'
    ],
    'lab_engineer': [
        'upload_report', 'view_equipment', 'mark_maintenance'
    ],
    'head_rd': [
        'view_quotations'
    ],
    'guest': [
        'view_equipment'
    ]
}

def has_permission(role, action):
    return action in PRIVILEGES.get(role, [])
