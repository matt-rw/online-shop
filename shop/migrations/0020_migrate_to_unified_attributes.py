# Generated manually for data migration

from django.db import migrations


def migrate_attributes_forward(apps, schema_editor):
    """
    Migrate Size, Color, Material data into the unified CustomAttribute system.
    Also populates the ProductVariant.attributes M2M field.
    """
    Size = apps.get_model('shop', 'Size')
    Color = apps.get_model('shop', 'Color')
    Material = apps.get_model('shop', 'Material')
    CustomAttribute = apps.get_model('shop', 'CustomAttribute')
    CustomAttributeValue = apps.get_model('shop', 'CustomAttributeValue')
    ProductVariant = apps.get_model('shop', 'ProductVariant')

    # Define standard size ordering
    SIZE_ORDER = {
        'XXS': 1, 'XS': 2, 'S': 3, 'M': 4, 'L': 5,
        'XL': 6, '2XL': 7, 'XXL': 7, '3XL': 8, 'XXXL': 8,
        # Numeric sizes
        '28': 28, '29': 29, '30': 30, '31': 31, '32': 32,
        '33': 33, '34': 34, '36': 36, '38': 38, '40': 40,
    }

    # Create Size attribute
    size_attr, _ = CustomAttribute.objects.get_or_create(
        slug='size',
        defaults={
            'name': 'Size',
            'input_type': 'select',
            'display_order': 1,
            'is_active': True,
        }
    )

    # Create Color attribute
    color_attr, _ = CustomAttribute.objects.get_or_create(
        slug='color',
        defaults={
            'name': 'Color',
            'input_type': 'color',
            'display_order': 2,
            'is_active': True,
        }
    )

    # Create Material attribute
    material_attr, _ = CustomAttribute.objects.get_or_create(
        slug='material',
        defaults={
            'name': 'Material',
            'input_type': 'select',
            'display_order': 3,
            'is_active': True,
        }
    )

    # Migrate Size values
    size_value_map = {}  # old_id -> new CustomAttributeValue
    for size in Size.objects.all():
        order = SIZE_ORDER.get(size.code.upper(), 100)
        value, _ = CustomAttributeValue.objects.get_or_create(
            attribute=size_attr,
            value=size.code,
            defaults={
                'display_order': order,
                'metadata': {'label': size.label} if size.label else {},
                'is_active': True,
            }
        )
        size_value_map[size.id] = value

    # Migrate Color values
    color_value_map = {}  # old_id -> new CustomAttributeValue
    for idx, color in enumerate(Color.objects.all()):
        value, _ = CustomAttributeValue.objects.get_or_create(
            attribute=color_attr,
            value=color.name,
            defaults={
                'display_order': idx * 10,
                'metadata': {'hex_code': '#000000'},  # Default, can be updated in admin
                'is_active': True,
            }
        )
        color_value_map[color.id] = value

    # Migrate Material values
    material_value_map = {}  # old_id -> new CustomAttributeValue
    for idx, material in enumerate(Material.objects.all()):
        value, _ = CustomAttributeValue.objects.get_or_create(
            attribute=material_attr,
            value=material.name,
            defaults={
                'display_order': idx * 10,
                'metadata': {'description': material.description} if material.description else {},
                'is_active': True,
            }
        )
        material_value_map[material.id] = value

    # Migrate ProductVariant relationships
    for variant in ProductVariant.objects.all():
        attributes_to_add = []

        if variant.size_id and variant.size_id in size_value_map:
            attributes_to_add.append(size_value_map[variant.size_id])

        if variant.color_id and variant.color_id in color_value_map:
            attributes_to_add.append(color_value_map[variant.color_id])

        if variant.material_id and variant.material_id in material_value_map:
            attributes_to_add.append(material_value_map[variant.material_id])

        if attributes_to_add:
            variant.attributes.add(*attributes_to_add)


def migrate_attributes_reverse(apps, schema_editor):
    """
    Reverse migration - clear the M2M relationships.
    Note: This doesn't delete the CustomAttribute/Values as they may be used elsewhere.
    """
    ProductVariant = apps.get_model('shop', 'ProductVariant')
    for variant in ProductVariant.objects.all():
        variant.attributes.clear()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0019_unified_attributes'),
    ]

    operations = [
        migrations.RunPython(migrate_attributes_forward, migrate_attributes_reverse),
    ]
