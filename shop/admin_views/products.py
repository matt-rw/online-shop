"""
Product, category, promotion, attribute, and bundle management admin views.
"""

import base64
import io
import json
import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.files.base import ContentFile
from django.db.models import Count, F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

import pytz

from shop.models import (
    Bundle,
    BundleItem,
    Category,
    CustomAttribute,
    CustomAttributeValue,
    Discount,
    Product,
    ProductVariant,
    Size,
    Color,
)

logger = logging.getLogger(__name__)

def products_dashboard(request):
    """
    Products management dashboard.
    """
    from django.db.models import Count, Q, Sum

    from shop.models import Product, ProductVariant

    # Handle product actions
    if request.method == "POST":
        from django.http import JsonResponse

        action = request.POST.get("action")

        # Debug logging
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"POST action received: {action}")

        if action == "toggle_active":
            from django.http import JsonResponse

            product_id = request.POST.get("product_id")
            try:
                product = Product.objects.get(id=product_id)
                product.is_active = not product.is_active
                product.save()
                return JsonResponse({"success": True, "is_active": product.is_active})
            except Product.DoesNotExist:
                return JsonResponse({"success": False, "error": "Product not found"})

        elif action == "upload_product_image":
            # Upload and optimize product image
            from shop.utils.image_optimizer import optimize_image

            try:
                image_data = request.POST.get("image_data")
                if not image_data:
                    return JsonResponse({"success": False, "error": "No image data provided"})

                # Parse base64 data
                if "base64," not in image_data:
                    return JsonResponse({"success": False, "error": "Invalid image format"})

                format_part, data_part = image_data.split("base64,", 1)
                image_content = base64.b64decode(data_part)

                if len(image_content) == 0:
                    return JsonResponse({"success": False, "error": "Empty image"})

                # Optimize image (resize, convert to WebP, compress)
                original_size = len(image_content)
                optimized_content, filename, content_type = optimize_image(
                    io.BytesIO(image_content),
                    filename=f"product_{uuid.uuid4().hex[:8]}"
                )
                optimized_size = len(optimized_content)

                # Use Cloudinary if available, otherwise fall back to local storage
                from django.conf import settings as django_settings
                if getattr(django_settings, 'CLOUDINARY_ENABLED', False):
                    import cloudinary.uploader
                    result = cloudinary.uploader.upload(
                        optimized_content,
                        folder="products",
                        public_id=f"product_{uuid.uuid4().hex[:8]}",
                        resource_type="image"
                    )
                    url = result['secure_url']
                else:
                    from django.core.files.storage import default_storage
                    path = default_storage.save(f"products/{filename}", ContentFile(optimized_content))
                    url = default_storage.url(path)

                # Log optimization
                savings = round((1 - optimized_size / original_size) * 100, 1) if original_size > 0 else 0
                logger.info(f"Product image optimized: {original_size} -> {optimized_size} bytes ({savings}% reduction)")

                return JsonResponse({"success": True, "url": url})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "create_product":
            import json

            from django.http import JsonResponse
            from django.utils.text import slugify

            from shop.models import Category

            name = request.POST.get("name", "").strip()
            if not name:
                return JsonResponse({"success": False, "error": "Product name is required"})

            # Generate slug from name
            base_slug = slugify(name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            # Get category if provided
            category_slug = request.POST.get("category")
            category_obj = None
            if category_slug:
                try:
                    category_obj = Category.objects.get(slug=category_slug)
                except Category.DoesNotExist:
                    pass

            # Get base price (default to 0 if not provided)
            try:
                base_price = float(request.POST.get("base_price", 0))
            except (ValueError, TypeError):
                base_price = 0

            # Get base cost (default to 0 if not provided)
            try:
                base_cost = float(request.POST.get("base_cost", 0))
            except (ValueError, TypeError):
                base_cost = 0

            # Get weight (optional)
            weight_oz_str = request.POST.get("weight_oz")
            weight_oz = None
            if weight_oz_str:
                try:
                    from decimal import Decimal
                    weight_oz = Decimal(weight_oz_str)
                except (ValueError, TypeError):
                    weight_oz = None

            # Parse images
            images_json = request.POST.get("images", "[]")
            try:
                images = json.loads(images_json)
            except json.JSONDecodeError:
                images = []

            try:
                # available_for_purchase defaults to True if not specified or if "on" (checkbox value)
                available = request.POST.get("available_for_purchase", "true")
                available_for_purchase = available in ("true", "on", True)

                product = Product.objects.create(
                    name=name,
                    slug=slug,
                    description=request.POST.get("description", ""),
                    base_price=base_price,
                    base_cost=base_cost,
                    weight_oz=weight_oz,
                    category_obj=category_obj,
                    is_active=request.POST.get("is_active") == "true",
                    featured=request.POST.get("featured") in ("true", "on"),
                    available_for_purchase=available_for_purchase,
                    images=images,
                )
                return JsonResponse({"success": True, "product_id": product.id, "slug": product.slug})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_price":
            from django.http import JsonResponse

            product_id = request.POST.get("product_id")
            new_price = request.POST.get("price")
            try:
                product = Product.objects.get(id=product_id)
                product.base_price = new_price
                product.save()
                return JsonResponse({"success": True})
            except Product.DoesNotExist:
                return JsonResponse({"success": False, "error": "Product not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_product":
            import json

            from django.http import JsonResponse

            from shop.models import Category

            product_id = request.POST.get("product_id")
            try:
                from decimal import Decimal

                product = Product.objects.get(id=product_id)

                # Store old base_price to update variants using it
                old_base_price = product.base_price
                new_base_price = Decimal(request.POST.get("base_price"))

                product.name = request.POST.get("name")
                product.slug = request.POST.get("slug")

                # Update category - try to find Category object by slug, fallback to legacy
                category_slug = request.POST.get("category")
                if category_slug:
                    try:
                        category_obj = Category.objects.get(slug=category_slug)
                        product.category_obj = category_obj
                    except Category.DoesNotExist:
                        # Fallback to legacy category field
                        product.category_legacy = category_slug

                product.description = request.POST.get("description")
                product.base_price = new_base_price
                product.base_cost = request.POST.get("base_cost") or 0
                weight_oz = request.POST.get("weight_oz", "").strip()
                logger.info(f"Saving product {product.id}: weight_oz received = '{weight_oz}', all POST keys: {list(request.POST.keys())}")
                if weight_oz:
                    try:
                        product.weight_oz = Decimal(weight_oz)
                        logger.info(f"Set weight_oz to {product.weight_oz}")
                    except (InvalidOperation, ValueError) as e:
                        logger.error(f"Invalid weight_oz value: {e}")
                        product.weight_oz = None
                else:
                    product.weight_oz = None
                    logger.info("weight_oz was empty, set to None")
                product.featured = request.POST.get("featured") == "true"
                product.available_for_purchase = request.POST.get("available_for_purchase") == "true"

                # Update images
                images_json = request.POST.get("images")
                if images_json is not None:
                    try:
                        product.images = json.loads(images_json)
                    except json.JSONDecodeError:
                        pass

                product.save()

                # Verify save by re-reading from database
                product.refresh_from_db()
                logger.info(f"After save - product {product.id} weight_oz in DB: {product.weight_oz}")

                # Update all variants that were using the old base price to the new base price
                if old_base_price != new_base_price:
                    variants_updated = product.variants.filter(price=old_base_price).update(
                        price=new_base_price
                    )

                return JsonResponse({"success": True})
            except Product.DoesNotExist:
                return JsonResponse({"success": False, "error": "Product not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "get_sizes_colors_materials":
            from django.http import JsonResponse

            from shop.models import Color, Material, Size

            sizes = list(Size.objects.all().values("id", "code", "label", "display_order"))
            colors = list(Color.objects.all().values("id", "name", "display_order"))
            materials = list(Material.objects.all().values("id", "name"))

            return JsonResponse(
                {"success": True, "sizes": sizes, "colors": colors, "materials": materials}
            )

        elif action == "get_product_category_attributes":
            from django.http import JsonResponse

            product_id = request.POST.get("product_id")
            try:
                product = Product.objects.get(id=product_id)
                category = product.category_obj

                if not category:
                    return JsonResponse(
                        {"success": False, "error": "Product has no category assigned"}
                    )

                return JsonResponse(
                    {
                        "success": True,
                        "category_name": category.name,
                        "uses_size": category.uses_size,
                        "uses_color": category.uses_color,
                        "uses_material": category.uses_material,
                        "custom_attributes": category.custom_attributes or [],
                        "common_fields": category.common_fields or [],
                    }
                )
            except Product.DoesNotExist:
                return JsonResponse({"success": False, "error": "Product not found"})

        elif action == "get_variants":
            from django.db.models import Sum
            from django.http import JsonResponse

            from shop.models import ShipmentItem

            product_id = request.POST.get("product_id")
            try:
                product = Product.objects.get(id=product_id)
                variants = product.variants.all().select_related("size", "color", "material").order_by(
                    "size__display_order", "size__code", "color__display_order", "color__name"
                )

                # Get pending shipment data for all variants in this product
                pending_shipments = ShipmentItem.objects.filter(
                    variant__product=product,
                    shipment__status__in=["pending", "in-transit", "delayed"]
                ).select_related("shipment", "variant")

                # Build lookup of pending items by variant_id
                pending_by_variant = {}
                for item in pending_shipments:
                    if item.variant_id not in pending_by_variant:
                        pending_by_variant[item.variant_id] = []
                    pending_by_variant[item.variant_id].append({
                        "shipment_id": item.shipment.id,
                        "name": item.shipment.name,
                        "tracking": item.shipment.tracking_number,
                        "supplier": item.shipment.supplier,
                        "expected_date": item.shipment.expected_date.isoformat() if item.shipment.expected_date else None,
                        "status": item.shipment.status,
                        "quantity": item.quantity,
                    })

                variants_data = []
                base_price = product.base_price
                base_cost = product.base_cost
                for v in variants:
                    pending_items = pending_by_variant.get(v.id, [])
                    pending_total = sum(item["quantity"] for item in pending_items)
                    # Check if variant has custom price (differs from product base_price)
                    has_custom_price = v.price != base_price if base_price else False
                    # Check if variant has custom cost (has a value set, not null)
                    has_custom_cost = v.cost is not None
                    # Effective cost is variant cost if set, otherwise product base_cost
                    effective_cost = v.cost if v.cost is not None else base_cost
                    # Check if variant has custom weight (has a value set, not null)
                    has_custom_weight = v.weight_oz is not None
                    # Effective weight is variant weight if set, otherwise product weight
                    effective_weight = v.weight_oz if v.weight_oz is not None else product.weight_oz
                    variants_data.append({
                        "id": v.id,
                        "sku": v.sku,
                        "size": str(v.size),
                        "size_id": v.size.id,
                        "color": str(v.color),
                        "color_id": v.color.id,
                        "material": str(v.material) if v.material else None,
                        "material_id": v.material.id if v.material else None,
                        "stock_quantity": v.stock_quantity,
                        "price": str(v.price),
                        "has_custom_price": has_custom_price,
                        "cost": str(effective_cost) if effective_cost else "0",
                        "has_custom_cost": has_custom_cost,
                        "weight_oz": str(effective_weight) if effective_weight else "",
                        "has_custom_weight": has_custom_weight,
                        "is_active": v.is_active,
                        "images": v.images if hasattr(v, "images") else [],
                        "custom_fields": v.custom_fields if hasattr(v, "custom_fields") else {},
                        "pending_shipments": pending_items,
                        "pending_total": pending_total,
                    })

                return JsonResponse({"success": True, "variants": variants_data})
            except Product.DoesNotExist:
                return JsonResponse({"success": False, "error": "Product not found"})

        elif action == "add_variant":
            import json

            from django.http import JsonResponse

            product_id = request.POST.get("product_id")
            size_id = request.POST.get("size_id")
            color_id = request.POST.get("color_id")
            material_id = request.POST.get("material_id")
            sku = request.POST.get("sku", "")
            stock_quantity = request.POST.get("stock_quantity", 0)
            price = request.POST.get("price")
            weight_oz = request.POST.get("weight_oz")
            use_base_weight = request.POST.get("use_base_weight") == "true"
            images_json = request.POST.get("images", "[]")
            custom_fields_json = request.POST.get("custom_fields", "{}")

            try:
                from shop.models import Color, Material, Size

                product = Product.objects.get(id=product_id)
                size = Size.objects.get(id=size_id)
                color = Color.objects.get(id=color_id)
                material = Material.objects.get(id=material_id) if material_id else None

                # Parse JSON data
                try:
                    images = json.loads(images_json)
                    custom_fields = json.loads(custom_fields_json)
                except json.JSONDecodeError:
                    images = []
                    custom_fields = {}

                # Check if variant already exists
                existing = ProductVariant.objects.filter(
                    product=product, size=size, color=color, material=material
                ).first()

                if existing:
                    parts = [str(size), str(color)]
                    if material:
                        parts.append(str(material))
                    return JsonResponse(
                        {"success": False, "error": f'Variant {" - ".join(parts)} already exists'}
                    )

                from decimal import Decimal

                # Determine weight_oz value
                variant_weight = None
                if not use_base_weight and weight_oz:
                    variant_weight = Decimal(weight_oz)

                variant = ProductVariant.objects.create(
                    product=product,
                    size=size,
                    color=color,
                    material=material,
                    sku=sku or None,  # Let model auto-generate if empty
                    stock_quantity=stock_quantity,
                    price=price,
                    weight_oz=variant_weight,
                    images=images,
                    custom_fields=custom_fields,
                    is_active=True,
                )

                return JsonResponse({"success": True})
            except Product.DoesNotExist:
                return JsonResponse({"success": False, "error": "Product not found"})
            except Size.DoesNotExist:
                return JsonResponse({"success": False, "error": "Size not found"})
            except Color.DoesNotExist:
                return JsonResponse({"success": False, "error": "Color not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_variant":
            import json

            from django.http import JsonResponse

            variant_id = request.POST.get("variant_id")
            size_id = request.POST.get("size_id")
            color_id = request.POST.get("color_id")
            material_id = request.POST.get("material_id")
            sku = request.POST.get("sku", "")
            stock_quantity = request.POST.get("stock_quantity", 0)
            price = request.POST.get("price")
            cost = request.POST.get("cost")  # None means use base cost
            use_base_cost = request.POST.get("use_base_cost") == "true"
            weight_oz = request.POST.get("weight_oz")
            use_base_weight = request.POST.get("use_base_weight") == "true"
            images_json = request.POST.get("images", "[]")
            custom_fields_json = request.POST.get("custom_fields", "{}")

            try:
                from shop.models import Color, Material, Size

                variant = ProductVariant.objects.get(id=variant_id)
                size = Size.objects.get(id=size_id)
                color = Color.objects.get(id=color_id)
                material = Material.objects.get(id=material_id) if material_id else None

                try:
                    images = json.loads(images_json)
                    custom_fields = json.loads(custom_fields_json)
                except json.JSONDecodeError:
                    images = []
                    custom_fields = {}

                # Check for duplicate (different variant with same size/color/material)
                existing = ProductVariant.objects.filter(
                    product=variant.product, size=size, color=color, material=material
                ).exclude(id=variant_id).first()

                if existing:
                    parts = [str(size), str(color)]
                    if material:
                        parts.append(str(material))
                    return JsonResponse(
                        {"success": False, "error": f'Variant {" - ".join(parts)} already exists'}
                    )

                variant.size = size
                variant.color = color
                variant.material = material
                variant.sku = sku or None
                variant.stock_quantity = stock_quantity
                variant.price = price
                # Handle cost - None means use base cost, a value means custom cost
                if use_base_cost:
                    variant.cost = None
                elif cost:
                    variant.cost = cost
                # Handle weight - None means use base weight, a value means custom weight
                from decimal import Decimal
                if use_base_weight:
                    variant.weight_oz = None
                elif weight_oz:
                    variant.weight_oz = Decimal(weight_oz)
                variant.images = images
                variant.custom_fields = custom_fields
                variant.save()

                return JsonResponse({"success": True})
            except ProductVariant.DoesNotExist:
                return JsonResponse({"success": False, "error": "Variant not found"})
            except Size.DoesNotExist:
                return JsonResponse({"success": False, "error": "Size not found"})
            except Color.DoesNotExist:
                return JsonResponse({"success": False, "error": "Color not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "bulk_create_variants":
            """
            Create multiple variants at once by selecting multiple sizes and colors.
            This creates all size×color combinations (matrix builder).
            """
            import json

            from django.http import JsonResponse

            product_id = request.POST.get("product_id")
            size_ids = request.POST.getlist("size_ids[]") or json.loads(request.POST.get("size_ids", "[]"))
            color_ids = request.POST.getlist("color_ids[]") or json.loads(request.POST.get("color_ids", "[]"))
            material_id = request.POST.get("material_id")
            price = request.POST.get("price")
            stock_quantity = int(request.POST.get("stock_quantity", 0))

            try:
                from shop.models import Color, Material, Size

                product = Product.objects.get(id=product_id)
                material = Material.objects.get(id=material_id) if material_id else None

                created_count = 0
                skipped_count = 0
                errors = []

                for size_id in size_ids:
                    for color_id in color_ids:
                        try:
                            size = Size.objects.get(id=size_id)
                            color = Color.objects.get(id=color_id)

                            # Check if variant already exists
                            existing = ProductVariant.objects.filter(
                                product=product, size=size, color=color, material=material
                            ).first()

                            if existing:
                                skipped_count += 1
                                continue

                            # Create the variant
                            ProductVariant.objects.create(
                                product=product,
                                size=size,
                                color=color,
                                material=material,
                                stock_quantity=stock_quantity,
                                price=price,
                                images=[],
                                custom_fields={},
                                is_active=True,
                            )
                            created_count += 1
                        except (Size.DoesNotExist, Color.DoesNotExist) as e:
                            errors.append(str(e))
                            continue

                message = f"Created {created_count} variant(s)"
                if skipped_count > 0:
                    message += f", skipped {skipped_count} existing"

                return JsonResponse({
                    "success": True,
                    "created": created_count,
                    "skipped": skipped_count,
                    "message": message
                })
            except Product.DoesNotExist:
                return JsonResponse({"success": False, "error": "Product not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_variant_price":
            from django.http import JsonResponse

            variant_id = request.POST.get("variant_id")
            new_price = request.POST.get("price")

            try:
                variant = ProductVariant.objects.get(id=variant_id)
                variant.price = new_price
                variant.save()
                return JsonResponse({"success": True})
            except ProductVariant.DoesNotExist:
                return JsonResponse({"success": False, "error": "Variant not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "apply_base_price_to_all":
            from django.http import JsonResponse

            product_id = request.POST.get("product_id")

            try:
                product = Product.objects.get(id=product_id)
                base_price = product.base_price

                if not base_price:
                    return JsonResponse({"success": False, "error": "Product has no base price"})

                # Update all variants to use the base price
                updated_count = product.variants.update(price=base_price)

                return JsonResponse({
                    "success": True,
                    "updated_count": updated_count,
                    "base_price": str(base_price)
                })
            except Product.DoesNotExist:
                return JsonResponse({"success": False, "error": "Product not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "toggle_variant_active":
            from django.http import JsonResponse

            variant_id = request.POST.get("variant_id")

            try:
                variant = ProductVariant.objects.get(id=variant_id)
                variant.is_active = not variant.is_active
                variant.save()
                return JsonResponse({"success": True, "is_active": variant.is_active})
            except ProductVariant.DoesNotExist:
                return JsonResponse({"success": False, "error": "Variant not found"})

        elif action == "delete_variant":
            from django.http import JsonResponse

            variant_id = request.POST.get("variant_id")

            try:
                variant = ProductVariant.objects.get(id=variant_id)
                variant.delete()
                return JsonResponse({"success": True})
            except ProductVariant.DoesNotExist:
                return JsonResponse({"success": False, "error": "Variant not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "get_pending_shipments":
            from django.http import JsonResponse

            from shop.models import Shipment

            try:
                shipments = Shipment.objects.filter(
                    status__in=["pending", "in-transit", "delayed"]
                ).order_by("-expected_date")

                shipments_data = [
                    {
                        "id": s.id,
                        "name": s.name,
                        "tracking_number": s.tracking_number,
                        "supplier": s.supplier,
                        "expected_date": s.expected_date.isoformat() if s.expected_date else None,
                        "status": s.status,
                        "item_count": s.item_count,
                    }
                    for s in shipments
                ]

                return JsonResponse({"success": True, "shipments": shipments_data})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "quick_create_shipment":
            from shop.models import Shipment

            supplier = request.POST.get("supplier", "").strip()
            tracking = request.POST.get("tracking_number", "").strip()

            if not supplier:
                return JsonResponse({"success": False, "error": "Supplier name is required"})

            # Auto-generate tracking number if not provided
            if not tracking:
                tracking = f"QUICK-{uuid.uuid4().hex[:8].upper()}"

            # Default expected date is 2 weeks from now
            expected_date = timezone.now().date() + timedelta(days=14)

            try:
                shipment = Shipment.objects.create(
                    tracking_number=tracking,
                    supplier=supplier,
                    expected_date=expected_date,
                    status="pending",
                )

                return JsonResponse({
                    "success": True,
                    "shipment": {
                        "id": shipment.id,
                        "name": shipment.name,
                        "tracking_number": shipment.tracking_number,
                        "supplier": shipment.supplier,
                        "expected_date": shipment.expected_date.isoformat(),
                        "status": shipment.status,
                    }
                })
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "add_variant_to_shipment":
            from decimal import Decimal

            from django.http import JsonResponse

            from shop.models import Shipment, ShipmentItem

            shipment_id = request.POST.get("shipment_id")
            variant_id = request.POST.get("variant_id")
            quantity = request.POST.get("quantity", 0)
            unit_cost = request.POST.get("unit_cost", "")

            if not shipment_id or not variant_id:
                return JsonResponse({"success": False, "error": "Shipment and variant are required"})

            try:
                quantity = int(quantity)
                if quantity <= 0:
                    return JsonResponse({"success": False, "error": "Quantity must be positive"})

                shipment = Shipment.objects.get(id=shipment_id)
                variant = ProductVariant.objects.select_related("product").get(id=variant_id)

                # Auto-populate unit_cost from variant cost or product base_cost if not provided
                if unit_cost and unit_cost.strip():
                    final_cost = Decimal(unit_cost)
                elif variant.cost is not None:
                    final_cost = variant.cost
                else:
                    final_cost = variant.product.base_cost or Decimal("0")

                # Check if item already exists - update quantity if so
                item, created = ShipmentItem.objects.get_or_create(
                    shipment=shipment,
                    variant=variant,
                    defaults={
                        "quantity": quantity,
                        "unit_cost": final_cost,
                    }
                )

                if not created:
                    # Update existing item
                    item.quantity += quantity
                    item.unit_cost = final_cost
                    item.save()

                return JsonResponse({
                    "success": True,
                    "created": created,
                    "item": {
                        "id": item.id,
                        "quantity": item.quantity,
                        "unit_cost": str(item.unit_cost),
                    }
                })
            except Shipment.DoesNotExist:
                return JsonResponse({"success": False, "error": "Shipment not found"})
            except ProductVariant.DoesNotExist:
                return JsonResponse({"success": False, "error": "Variant not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "bulk_update_stock":
            """
            Update stock for multiple variants at once.
            Supports setting absolute value or incrementing/decrementing.
            """
            import json

            from django.http import JsonResponse

            product_id = request.POST.get("product_id")
            update_mode = request.POST.get("update_mode", "set")  # 'set', 'add', 'subtract'
            stock_value = int(request.POST.get("stock_value", 0))
            variant_ids = request.POST.getlist("variant_ids[]") or json.loads(request.POST.get("variant_ids", "[]"))

            try:
                product = Product.objects.get(id=product_id)

                if not variant_ids:
                    # If no specific variants, update all variants of this product
                    variants = product.variants.all()
                else:
                    variants = ProductVariant.objects.filter(id__in=variant_ids, product=product)

                updated_count = 0
                for variant in variants:
                    if update_mode == "set":
                        variant.stock_quantity = max(0, stock_value)
                    elif update_mode == "add":
                        variant.stock_quantity = variant.stock_quantity + stock_value
                    elif update_mode == "subtract":
                        variant.stock_quantity = max(0, variant.stock_quantity - stock_value)
                    variant.save()
                    updated_count += 1

                return JsonResponse({
                    "success": True,
                    "updated": updated_count,
                    "message": f"Updated stock for {updated_count} variant(s)"
                })
            except Product.DoesNotExist:
                return JsonResponse({"success": False, "error": "Product not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_product":
            from django.http import JsonResponse

            product_id = request.POST.get("product_id")
            try:
                product = Product.objects.get(id=product_id)
                product_name = product.name
                # Delete all variants first (cascades automatically, but being explicit)
                product.variants.all().delete()
                product.delete()
                return JsonResponse({"success": True, "message": f'Product "{product_name}" deleted'})
            except Product.DoesNotExist:
                return JsonResponse({"success": False, "error": "Product not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        # If we got here, the action was not recognized
        return JsonResponse({"success": False, "error": f"Unknown action: {action}"})

    # Get sort parameter
    sort_by = request.GET.get("sort", "newest")

    # Import aggregation functions
    from django.db.models import Max, Min

    # Get all products with variant data in a single query (optimized)
    # Exclude test checkout item from inventory reports
    from shop.models import OrderStatus
    products = Product.objects.exclude(slug="test-checkout-item").select_related("category_obj").annotate(
        variants_count=Count("variants"),
        stock_total=Sum("variants__stock_quantity"),
        variants_active=Count("variants", filter=Q(variants__is_active=True)),
        min_price=Min("variants__price"),
        max_price=Max("variants__price"),
        # Total sold: sum of order item quantities for completed orders
        total_sold=Sum(
            "variants__orderitem__quantity",
            filter=Q(variants__orderitem__order__status__in=[
                OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.FULFILLED
            ])
        ),
    )

    # Apply sorting
    if sort_by == "newest":
        products = products.order_by("-created_at")
    elif sort_by == "name":
        products = products.order_by("name")
    elif sort_by == "category":
        products = products.order_by("category_obj__name", "name")
    elif sort_by == "status":
        products = products.order_by("-is_active", "name")
    else:
        products = products.order_by("-created_at")

    # Build products data from annotated queryset
    products_data = []
    for product in products:
        # Format price range
        min_price = product.min_price
        max_price = product.max_price
        if min_price is None or max_price is None:
            price_range = f"${product.base_price:.2f}"
        elif min_price == max_price:
            price_range = f"${min_price:.2f}"
        else:
            price_range = f"${min_price:.2f} - ${max_price:.2f}"

        # Get category slug for editing
        category_slug = ""
        if product.category_obj:
            category_slug = product.category_obj.slug
        elif product.category_legacy:
            category_slug = product.category_legacy

        products_data.append(
            {
                "id": product.id,
                "name": product.name,
                "slug": product.slug,
                "category": (
                    product.category_obj.name
                    if product.category_obj
                    else (product.category_legacy or "Uncategorized")
                ),
                "category_slug": category_slug,
                "description": product.description,
                "base_price": product.base_price,
                "base_cost": product.base_cost,
                "price_range": price_range,
                "is_active": product.is_active,
                "featured": product.featured,
                "available_for_purchase": product.available_for_purchase,
                "variant_count": product.variants_count or 0,
                "total_stock": product.stock_total or 0,
                "total_sold": product.total_sold or 0,
                "active_variants": product.variants_active or 0,
                "images": product.images or [],
            }
        )

    # Stats - use already-fetched data to avoid extra queries
    total_products = len(products_data)
    active_products = sum(1 for p in products_data if p.get("is_active", True))

    # Get variant stats in a single query instead of 4 separate queries
    # Exclude test checkout item from stats
    variant_stats = ProductVariant.objects.exclude(product__slug="test-checkout-item").aggregate(
        total_variants=Count("id"),
        total_stock=Sum("stock_quantity"),
        low_stock_count=Count("id", filter=Q(stock_quantity__lt=10, stock_quantity__gt=0)),
        out_of_stock_count=Count("id", filter=Q(stock_quantity=0)),
    )
    total_variants = variant_stats["total_variants"] or 0
    total_stock = variant_stats["total_stock"] or 0
    low_stock_count = variant_stats["low_stock_count"] or 0
    out_of_stock_count = variant_stats["out_of_stock_count"] or 0

    # Get all categories for the dropdown
    from shop.models import Category

    categories = Category.objects.all().order_by("name")

    context = {
        "products": products_data,
        "categories": categories,
        "total_products": total_products,
        "active_products": active_products,
        "total_variants": total_variants,
        "total_stock": total_stock,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "sort_by": sort_by,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/products_dashboard.html", context)


@staff_member_required
def product_wizard(request):
    """
    Step-by-step product creation wizard.
    Provides a simpler flow for creating products with variants.
    """
    from shop.models import Category, Color, CustomAttribute, Material, Size

    # Get all categories
    categories = Category.objects.all().order_by("name")

    # Get all standard attribute values (using model default ordering)
    sizes = Size.objects.all()
    colors = Color.objects.all()
    materials = Material.objects.all().order_by("name")

    # Get custom attributes with their values
    custom_attributes = CustomAttribute.objects.filter(is_active=True).prefetch_related("values").order_by("name")
    custom_attrs_data = []
    for attr in custom_attributes:
        custom_attrs_data.append({
            "id": attr.id,
            "name": attr.name,
            "slug": attr.slug,
            "values": list(attr.values.filter(is_active=True).order_by("display_order", "value").values("id", "value"))
        })

    context = {
        "categories": categories,
        "sizes": sizes,
        "colors": colors,
        "materials": materials,
        "custom_attributes": custom_attrs_data,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/product_wizard.html", context)


@staff_member_required
def product_preview(request, product_id):
    """
    Preview a product as it would appear to customers.
    """
    from shop.models import Product

    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return HttpResponse("Product not found", status=404)

    # Collect unique images from variants
    images = []
    seen_images = set()
    for variant in product.variants.all():
        if variant.images:
            for img in variant.images:
                if img and not img.startswith(("/", "http")):
                    img_path = f"/static/{img}"
                else:
                    img_path = img
                if img_path not in seen_images:
                    images.append(img_path)
                    seen_images.add(img_path)

    context = {
        "product": product,
        "images": images,
    }

    return render(request, "admin/product_preview.html", context)


def categories_dashboard(request):
    """
    Categories management dashboard.
    """
    from django.http import JsonResponse

    from shop.models import Category

    # Handle category actions
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create_category":
            import json

            try:
                name = request.POST.get("name")
                slug = request.POST.get("slug")
                description = request.POST.get("description", "")
                uses_size = request.POST.get("uses_size") == "true"
                uses_color = request.POST.get("uses_color") == "true"
                uses_material = request.POST.get("uses_material") == "true"
                custom_attributes = json.loads(request.POST.get("custom_attributes", "[]"))
                common_fields = json.loads(request.POST.get("common_fields", "[]"))

                category = Category.objects.create(
                    name=name,
                    slug=slug,
                    description=description,
                    uses_size=uses_size,
                    uses_color=uses_color,
                    uses_material=uses_material,
                    custom_attributes=custom_attributes,
                    common_fields=common_fields,
                )

                return JsonResponse({"success": True, "category_id": category.id})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_category":
            import json

            try:
                category_id = request.POST.get("category_id")
                category = Category.objects.get(id=category_id)

                category.name = request.POST.get("name")
                category.slug = request.POST.get("slug")
                category.description = request.POST.get("description", "")
                category.uses_size = request.POST.get("uses_size") == "true"
                category.uses_color = request.POST.get("uses_color") == "true"
                category.uses_material = request.POST.get("uses_material") == "true"
                category.custom_attributes = json.loads(request.POST.get("custom_attributes", "[]"))
                category.common_fields = json.loads(request.POST.get("common_fields", "[]"))
                category.save()

                return JsonResponse({"success": True})
            except Category.DoesNotExist:
                return JsonResponse({"success": False, "error": "Category not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_category":
            try:
                category_id = request.POST.get("category_id")
                category = Category.objects.get(id=category_id)

                # Check if category has products
                if category.products.exists():
                    return JsonResponse(
                        {
                            "success": False,
                            "error": f"Cannot delete category with {category.products.count()} products. Reassign or delete products first.",
                        }
                    )

                category.delete()
                return JsonResponse({"success": True})
            except Category.DoesNotExist:
                return JsonResponse({"success": False, "error": "Category not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "toggle_category_visibility":
            try:
                category_id = request.POST.get("category_id")
                category = Category.objects.get(id=category_id)
                category.is_hidden = not category.is_hidden
                category.save()
                return JsonResponse({"success": True, "is_hidden": category.is_hidden})
            except Category.DoesNotExist:
                return JsonResponse({"success": False, "error": "Category not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

    # Get all categories with product counts
    categories = Category.objects.all().order_by("name")
    categories_data = []

    for category in categories:
        # Get all products in this category
        all_products = category.products.all()

        # Active products (is_active=True and has stock)
        active_count = 0
        # Out of stock (is_active=True but no stock)
        out_of_stock_count = 0
        # Draft/pending (is_active=False)
        draft_count = all_products.filter(is_active=False).count()

        for product in all_products.filter(is_active=True):
            total_stock = product.total_stock
            if total_stock > 0:
                active_count += 1
            else:
                out_of_stock_count += 1

        categories_data.append(
            {
                "id": category.id,
                "name": category.name,
                "slug": category.slug,
                "description": category.description,
                "uses_size": category.uses_size,
                "uses_color": category.uses_color,
                "uses_material": category.uses_material,
                "custom_attributes": category.custom_attributes,
                "common_fields": category.common_fields,
                "is_hidden": category.is_hidden,
                "product_count": category.products.count(),
                "active_count": active_count,
                "out_of_stock_count": out_of_stock_count,
                "draft_count": draft_count,
            }
        )

    import json

    context = {
        "categories": categories_data,
        "categories_json": json.dumps(categories_data),
        "total_categories": categories.count(),
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/categories_dashboard.html", context)


def promotions_dashboard(request):
    """
    Promotions and deals management dashboard.
    """
    from django.http import JsonResponse

    from shop.models import Discount

    # Handle discount actions
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "toggle_discount" or action == "toggle_discount_status":
            discount_id = request.POST.get("discount_id")
            try:
                discount = Discount.objects.get(id=discount_id)
                discount.is_active = not discount.is_active
                discount.save()
                return JsonResponse({"success": True, "is_active": discount.is_active})
            except Discount.DoesNotExist:
                return JsonResponse({"success": False, "error": "Discount not found"})

        elif action == "create_discount":
            try:
                discount_type = request.POST.get("discount_type")
                is_active = request.POST.get("is_active") == "on"

                # Validate: only one active auto_free_shipping allowed
                if discount_type == "auto_free_shipping" and is_active:
                    existing = Discount.objects.filter(
                        discount_type="auto_free_shipping",
                        is_active=True,
                    ).first()
                    if existing:
                        messages.error(
                            request,
                            f"Only one Free Shipping Threshold can be active at a time. "
                            f"Please deactivate '{existing.name}' first."
                        )
                        return redirect("promotions_dashboard")

                # Validate: auto_free_shipping requires min_purchase_amount
                if discount_type == "auto_free_shipping":
                    min_purchase = request.POST.get("min_purchase_amount")
                    if not min_purchase:
                        messages.error(request, "Free Shipping Threshold requires a minimum purchase amount.")
                        return redirect("promotions_dashboard")

                discount = Discount(
                    name=request.POST.get("name"),
                    code=request.POST.get("code") if discount_type != "auto_free_shipping" else "",
                    discount_type=discount_type,
                    value=request.POST.get("value") or 0,
                    min_purchase_amount=request.POST.get("min_purchase_amount") or None,
                    max_uses=request.POST.get("max_uses") or None,
                    valid_from=request.POST.get("valid_from"),
                    valid_until=request.POST.get("valid_until") or None,
                    applies_to_all=request.POST.get("applies_to_all") == "on",
                    is_active=is_active,
                    link_destination=request.POST.get("link_destination", ""),
                    landing_url=request.POST.get("landing_url", ""),
                )
                discount.save()
                messages.success(request, f"Promotion '{discount.name}' created successfully!")
                return redirect("promotions_dashboard")
            except Exception as e:
                messages.error(request, f"Error creating promotion: {str(e)}")
                return redirect("promotions_dashboard")

        elif action == "update_discount":
            try:
                discount_id = request.POST.get("discount_id")
                discount = Discount.objects.get(id=discount_id)

                discount_type = request.POST.get("discount_type")
                is_active = request.POST.get("is_active") == "on"

                # Validate: only one active auto_free_shipping allowed
                if discount_type == "auto_free_shipping" and is_active:
                    existing = Discount.objects.filter(
                        discount_type="auto_free_shipping",
                        is_active=True,
                    ).exclude(pk=discount.pk).first()
                    if existing:
                        messages.error(
                            request,
                            f"Only one Free Shipping Threshold can be active at a time. "
                            f"Please deactivate '{existing.name}' first."
                        )
                        return redirect("promotions_dashboard")

                # Validate: auto_free_shipping requires min_purchase_amount
                if discount_type == "auto_free_shipping":
                    min_purchase = request.POST.get("min_purchase_amount")
                    if not min_purchase:
                        messages.error(request, "Free Shipping Threshold requires a minimum purchase amount.")
                        return redirect("promotions_dashboard")

                discount.name = request.POST.get("name")
                discount.code = request.POST.get("code", "") if discount_type != "auto_free_shipping" else ""
                discount.discount_type = discount_type
                discount.value = request.POST.get("value") or 0
                discount.valid_from = request.POST.get("valid_from")
                discount.valid_until = request.POST.get("valid_until") or None
                discount.min_purchase_amount = request.POST.get("min_purchase_amount") or None
                discount.max_uses = request.POST.get("max_uses") or None
                discount.applies_to_all = request.POST.get("applies_to_all") == "on"
                discount.is_active = is_active
                discount.link_destination = request.POST.get("link_destination", "")
                discount.landing_url = request.POST.get("landing_url", "")

                discount.save()
                messages.success(request, f"Promotion '{discount.name}' updated successfully!")
                return redirect("promotions_dashboard")
            except Discount.DoesNotExist:
                messages.error(request, "Promotion not found")
                return redirect("promotions_dashboard")
            except Exception as e:
                messages.error(request, f"Error updating promotion: {str(e)}")
                return redirect("promotions_dashboard")

    # Get all discounts
    discounts = Discount.objects.all().order_by("-created_at")

    # Stats
    active_discounts = discounts.filter(is_active=True).count()
    total_uses = sum(d.times_used for d in discounts)

    # Get valid discounts
    from django.utils import timezone

    now = timezone.now()
    valid_discounts = [d for d in discounts if d.is_valid]

    context = {
        "discounts": discounts,
        "active_discounts": active_discounts,
        "total_uses": total_uses,
        "valid_discounts_count": len(valid_discounts),
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/discounts_dashboard.html", context)


def attributes_dashboard(request):
    """
    Manage product attributes: Sizes, Colors, Materials, and Custom Attributes.
    These are used to create product variants.
    """
    from django.http import JsonResponse
    from django.utils.text import slugify

    from shop.models import Color, CustomAttribute, CustomAttributeValue, Material, Size

    # Handle AJAX actions
    if request.method == "POST":
        action = request.POST.get("action")

        # SIZE ACTIONS
        if action == "create_size":
            try:
                code = request.POST.get("code", "").strip().upper()
                label = request.POST.get("label", "").strip()
                if not code:
                    return JsonResponse({"success": False, "error": "Size code is required"})
                if Size.objects.filter(code=code).exists():
                    return JsonResponse({"success": False, "error": f"Size '{code}' already exists"})
                size = Size.objects.create(code=code, label=label or code)
                return JsonResponse({"success": True, "id": size.id, "code": size.code, "label": size.label})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_size":
            try:
                size_id = request.POST.get("size_id")
                code = request.POST.get("code", "").strip().upper()
                label = request.POST.get("label", "").strip()
                size = Size.objects.get(id=size_id)
                if code and code != size.code:
                    if Size.objects.filter(code=code).exclude(id=size_id).exists():
                        return JsonResponse({"success": False, "error": f"Size '{code}' already exists"})
                    size.code = code
                size.label = label or code
                size.save()
                return JsonResponse({"success": True})
            except Size.DoesNotExist:
                return JsonResponse({"success": False, "error": "Size not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_size":
            try:
                size_id = request.POST.get("size_id")
                size = Size.objects.get(id=size_id)
                # Check if size is in use
                variant_count = size.productvariant_set.count()
                if variant_count > 0:
                    return JsonResponse({
                        "success": False,
                        "error": f"Cannot delete: {variant_count} variant(s) are using this size"
                    })
                size.delete()
                return JsonResponse({"success": True})
            except Size.DoesNotExist:
                return JsonResponse({"success": False, "error": "Size not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "reorder_sizes":
            try:
                import json
                size_ids = json.loads(request.POST.get("size_ids", "[]"))
                for order, size_id in enumerate(size_ids):
                    Size.objects.filter(id=size_id).update(display_order=order)
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        # COLOR ACTIONS
        elif action == "create_color":
            try:
                name = request.POST.get("name", "").strip()
                if not name:
                    return JsonResponse({"success": False, "error": "Color name is required"})
                if Color.objects.filter(name__iexact=name).exists():
                    return JsonResponse({"success": False, "error": f"Color '{name}' already exists"})
                color = Color.objects.create(name=name)
                return JsonResponse({"success": True, "id": color.id, "name": color.name})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_color":
            try:
                color_id = request.POST.get("color_id")
                name = request.POST.get("name", "").strip()
                color = Color.objects.get(id=color_id)
                if name and name.lower() != color.name.lower():
                    if Color.objects.filter(name__iexact=name).exclude(id=color_id).exists():
                        return JsonResponse({"success": False, "error": f"Color '{name}' already exists"})
                    color.name = name
                    color.save()
                return JsonResponse({"success": True})
            except Color.DoesNotExist:
                return JsonResponse({"success": False, "error": "Color not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_color":
            try:
                color_id = request.POST.get("color_id")
                color = Color.objects.get(id=color_id)
                variant_count = color.productvariant_set.count()
                if variant_count > 0:
                    return JsonResponse({
                        "success": False,
                        "error": f"Cannot delete: {variant_count} variant(s) are using this color"
                    })
                color.delete()
                return JsonResponse({"success": True})
            except Color.DoesNotExist:
                return JsonResponse({"success": False, "error": "Color not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "reorder_colors":
            try:
                import json
                color_ids = json.loads(request.POST.get("color_ids", "[]"))
                for order, color_id in enumerate(color_ids):
                    Color.objects.filter(id=color_id).update(display_order=order)
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        # MATERIAL ACTIONS
        elif action == "create_material":
            try:
                name = request.POST.get("name", "").strip()
                description = request.POST.get("description", "").strip()
                if not name:
                    return JsonResponse({"success": False, "error": "Material name is required"})
                if Material.objects.filter(name__iexact=name).exists():
                    return JsonResponse({"success": False, "error": f"Material '{name}' already exists"})
                material = Material.objects.create(name=name, description=description)
                return JsonResponse({"success": True, "id": material.id, "name": material.name})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_material":
            try:
                material_id = request.POST.get("material_id")
                name = request.POST.get("name", "").strip()
                description = request.POST.get("description", "").strip()
                material = Material.objects.get(id=material_id)
                if name and name.lower() != material.name.lower():
                    if Material.objects.filter(name__iexact=name).exclude(id=material_id).exists():
                        return JsonResponse({"success": False, "error": f"Material '{name}' already exists"})
                    material.name = name
                material.description = description
                material.save()
                return JsonResponse({"success": True})
            except Material.DoesNotExist:
                return JsonResponse({"success": False, "error": "Material not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_material":
            try:
                material_id = request.POST.get("material_id")
                material = Material.objects.get(id=material_id)
                variant_count = material.productvariant_set.count()
                if variant_count > 0:
                    return JsonResponse({
                        "success": False,
                        "error": f"Cannot delete: {variant_count} variant(s) are using this material"
                    })
                material.delete()
                return JsonResponse({"success": True})
            except Material.DoesNotExist:
                return JsonResponse({"success": False, "error": "Material not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        # CUSTOM ATTRIBUTE ACTIONS
        elif action == "create_custom_attribute":
            try:
                from django.db.models import Max

                name = request.POST.get("name", "").strip()
                input_type = request.POST.get("input_type", "select").strip()
                description = request.POST.get("description", "").strip()
                if not name:
                    return JsonResponse({"success": False, "error": "Attribute name is required"})
                slug = slugify(name)
                if CustomAttribute.objects.filter(slug=slug).exists():
                    return JsonResponse({"success": False, "error": f"Attribute '{name}' already exists"})
                # Get next display order
                max_order = CustomAttribute.objects.aggregate(Max("display_order"))["display_order__max"] or 0
                attr = CustomAttribute.objects.create(
                    name=name, slug=slug, input_type=input_type,
                    description=description, display_order=max_order + 1
                )
                return JsonResponse({"success": True, "id": attr.id, "name": attr.name, "slug": attr.slug})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_custom_attribute":
            try:
                attr_id = request.POST.get("attribute_id")
                name = request.POST.get("name", "").strip()
                description = request.POST.get("description", "").strip()
                attr = CustomAttribute.objects.get(id=attr_id)
                if name and name != attr.name:
                    new_slug = slugify(name)
                    if CustomAttribute.objects.filter(slug=new_slug).exclude(id=attr_id).exists():
                        return JsonResponse({"success": False, "error": f"Attribute '{name}' already exists"})
                    attr.name = name
                    attr.slug = new_slug
                attr.description = description
                attr.save()
                return JsonResponse({"success": True})
            except CustomAttribute.DoesNotExist:
                return JsonResponse({"success": False, "error": "Attribute not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_custom_attribute":
            try:
                attr_id = request.POST.get("attribute_id")
                attr = CustomAttribute.objects.get(id=attr_id)
                # Check if any values are linked to product variants
                in_use_count = sum(v.variants.count() for v in attr.values.all())
                if in_use_count > 0:
                    return JsonResponse({
                        "success": False,
                        "error": f"Cannot delete '{attr.name}' - it has values linked to {in_use_count} product variant(s). Remove from products first."
                    })
                value_count = attr.values.count()
                attr.delete()
                return JsonResponse({"success": True, "values_deleted": value_count})
            except CustomAttribute.DoesNotExist:
                return JsonResponse({"success": False, "error": "Attribute not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        # CUSTOM ATTRIBUTE VALUE ACTIONS
        elif action == "add_attribute_value":
            try:
                from django.db.models import Max

                attr_id = request.POST.get("attribute_id")
                value = request.POST.get("value", "").strip()
                hex_code = request.POST.get("hex_code", "").strip()
                if not value:
                    return JsonResponse({"success": False, "error": "Value is required"})
                attr = CustomAttribute.objects.get(id=attr_id)
                if attr.values.filter(value__iexact=value).exists():
                    return JsonResponse({"success": False, "error": f"Value '{value}' already exists"})
                # Get next display order
                max_order = attr.values.aggregate(Max("display_order"))["display_order__max"] or 0
                # Build metadata if hex_code provided
                metadata = {}
                if hex_code:
                    metadata["hex_code"] = hex_code
                attr_value = CustomAttributeValue.objects.create(
                    attribute=attr, value=value, display_order=max_order + 1, metadata=metadata
                )
                return JsonResponse({"success": True, "id": attr_value.id, "value": attr_value.value})
            except CustomAttribute.DoesNotExist:
                return JsonResponse({"success": False, "error": "Attribute not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_attribute_value":
            try:
                value_id = request.POST.get("value_id")
                attr_value = CustomAttributeValue.objects.get(id=value_id)
                # Check if value is linked to any product variants
                variant_count = attr_value.variants.count()
                if variant_count > 0:
                    return JsonResponse({
                        "success": False,
                        "error": f"Cannot delete '{attr_value.value}' - it's linked to {variant_count} product variant(s)."
                    })
                attr_value.delete()
                return JsonResponse({"success": True})
            except CustomAttributeValue.DoesNotExist:
                return JsonResponse({"success": False, "error": "Value not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "reorder_attribute_values":
            # Reorder values within an attribute (drag-and-drop)
            try:
                import json
                value_ids = json.loads(request.POST.get("value_ids", "[]"))
                for order, value_id in enumerate(value_ids):
                    CustomAttributeValue.objects.filter(id=value_id).update(display_order=order)
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_attribute_value":
            # Update a value's metadata (e.g., hex_code for colors)
            try:
                import json
                value_id = request.POST.get("value_id")
                attr_value = CustomAttributeValue.objects.get(id=value_id)

                # Update metadata
                metadata = attr_value.metadata or {}
                hex_code = request.POST.get("hex_code")
                label = request.POST.get("label")

                if hex_code is not None:
                    metadata["hex_code"] = hex_code
                if label is not None:
                    metadata["label"] = label

                attr_value.metadata = metadata
                attr_value.save()
                return JsonResponse({"success": True, "metadata": metadata})
            except CustomAttributeValue.DoesNotExist:
                return JsonResponse({"success": False, "error": "Value not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_attribute_type":
            # Update an attribute's input_type and display_order
            try:
                attr_id = request.POST.get("attribute_id")
                attr = CustomAttribute.objects.get(id=attr_id)

                input_type = request.POST.get("input_type")
                display_order = request.POST.get("display_order")

                if input_type:
                    attr.input_type = input_type
                if display_order is not None:
                    attr.display_order = int(display_order)

                attr.save()
                return JsonResponse({"success": True})
            except CustomAttribute.DoesNotExist:
                return JsonResponse({"success": False, "error": "Attribute not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "reorder_attributes":
            # Reorder attributes (drag-and-drop)
            try:
                import json
                attr_ids = json.loads(request.POST.get("attribute_ids", "[]"))
                for order, attr_id in enumerate(attr_ids):
                    CustomAttribute.objects.filter(id=attr_id).update(display_order=order)
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

    # GET request - render dashboard (use model's default ordering)
    sizes = Size.objects.all()
    colors = Color.objects.all()
    materials = Material.objects.all().order_by("name")

    # Get usage counts
    sizes_data = []
    for size in sizes:
        variant_count = size.productvariant_set.count()
        sizes_data.append({
            "id": size.id,
            "code": size.code,
            "label": size.label,
            "display_order": size.display_order,
            "variant_count": variant_count,
        })

    colors_data = []
    for color in colors:
        variant_count = color.productvariant_set.count()
        colors_data.append({
            "id": color.id,
            "name": color.name,
            "display_order": color.display_order,
            "variant_count": variant_count,
        })

    materials_data = []
    for material in materials:
        variant_count = material.productvariant_set.count()
        materials_data.append({
            "id": material.id,
            "name": material.name,
            "description": material.description,
            "variant_count": variant_count,
        })

    # Get custom attributes with their values, ordered by display_order
    custom_attributes = CustomAttribute.objects.prefetch_related("values").filter(is_active=True).order_by("display_order", "name")
    custom_attrs_data = []
    total_values = 0
    total_in_use = 0
    for attr in custom_attributes:
        values_data = []
        for v in attr.values.filter(is_active=True).order_by("display_order", "value"):
            # Count variants using this value
            variant_count = v.variants.count()
            values_data.append({
                "id": v.id,
                "value": v.value,
                "display_order": v.display_order,
                "metadata": v.metadata or {},
                "variant_count": variant_count,
            })
            total_values += 1
            if variant_count > 0:
                total_in_use += 1
        custom_attrs_data.append({
            "id": attr.id,
            "name": attr.name,
            "input_type": attr.input_type,
            "display_order": attr.display_order,
            "slug": attr.slug,
            "description": attr.description,
            "values": values_data,
            "value_count": len(values_data),
        })

    context = {
        "sizes": sizes_data,
        "colors": colors_data,
        "materials": materials_data,
        "custom_attributes": custom_attrs_data,
        "total_sizes": len(sizes_data),
        "total_colors": len(colors_data),
        "total_materials": len(materials_data),
        "total_custom_attributes": len(custom_attrs_data),
        "total_values": total_values,
        "total_in_use": total_in_use,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/attributes_dashboard.html", context)


def bundles_dashboard(request):
    """
    Dashboard for managing product bundles.
    """
    from django.utils.text import slugify
    from shop.models import Bundle, BundleItem, Product

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "upload_bundle_image":
            # Upload and optimize bundle image
            from shop.utils.image_optimizer import optimize_image

            try:
                image_data = request.POST.get("image_data")
                if not image_data:
                    return JsonResponse({"success": False, "error": "No image data provided"})

                if "base64," not in image_data:
                    return JsonResponse({"success": False, "error": "Invalid image format"})

                format_part, data_part = image_data.split("base64,", 1)
                image_content = base64.b64decode(data_part)

                if len(image_content) == 0:
                    return JsonResponse({"success": False, "error": "Empty image"})

                # Optimize image
                original_size = len(image_content)
                optimized_content, filename, content_type = optimize_image(
                    io.BytesIO(image_content),
                    filename=f"bundle_{uuid.uuid4().hex[:8]}"
                )
                optimized_size = len(optimized_content)

                # Use Cloudinary if available, otherwise fall back to local storage
                from django.conf import settings as django_settings
                if getattr(django_settings, 'CLOUDINARY_ENABLED', False):
                    import cloudinary.uploader
                    result = cloudinary.uploader.upload(
                        optimized_content,
                        folder="bundles",
                        public_id=f"bundle_{uuid.uuid4().hex[:8]}",
                        resource_type="image"
                    )
                    url = result['secure_url']
                else:
                    from django.core.files.storage import default_storage
                    path = default_storage.save(f"bundles/{filename}", ContentFile(optimized_content))
                    url = default_storage.url(path)

                savings = round((1 - optimized_size / original_size) * 100, 1) if original_size > 0 else 0
                logger.info(f"Bundle image optimized: {original_size} -> {optimized_size} bytes ({savings}% reduction)")

                return JsonResponse({"success": True, "url": url})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "create":
            import json
            name = request.POST.get("name")
            price = request.POST.get("price")
            use_component_pricing = request.POST.get("use_component_pricing") == "on"
            description = request.POST.get("description", "")
            product_ids = request.POST.getlist("product_ids")
            images_json = request.POST.get("images", "[]")
            try:
                images = json.loads(images_json) if images_json else []
            except json.JSONDecodeError:
                images = []

            if not name or (not use_component_pricing and not price):
                messages.error(request, "Name and price are required (unless using component pricing)")
                return redirect("admin_bundles")

            try:
                # Generate unique slug
                base_slug = slugify(name)
                slug = base_slug
                counter = 1
                while Bundle.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1

                bundle = Bundle.objects.create(
                    name=name,
                    slug=slug,
                    price=price if not use_component_pricing else None,
                    use_component_pricing=use_component_pricing,
                    description=description,
                    images=images,
                    show_includes=request.POST.get("show_includes") == "on",
                    is_active=True,
                    available_for_purchase=True,
                )

                # Add products to bundle
                for i, product_id in enumerate(product_ids):
                    if product_id:
                        product = Product.objects.get(id=product_id)
                        BundleItem.objects.create(
                            bundle=bundle,
                            product=product,
                            quantity=1,
                            display_order=i,
                        )

                messages.success(request, f'Bundle "{bundle.name}" created successfully!')
            except Exception as e:
                messages.error(request, f"Error creating bundle: {str(e)}")

            return redirect("admin_bundles")

        elif action == "update":
            import json
            bundle_id = request.POST.get("bundle_id")
            try:
                bundle = Bundle.objects.get(id=bundle_id)
                bundle.name = request.POST.get("name")
                use_component_pricing = request.POST.get("use_component_pricing") == "on"
                bundle.use_component_pricing = use_component_pricing
                bundle.price = request.POST.get("price") if not use_component_pricing else None
                bundle.description = request.POST.get("description", "")
                bundle.show_includes = request.POST.get("show_includes") == "on"
                bundle.is_active = request.POST.get("is_active") == "on"
                bundle.available_for_purchase = request.POST.get("available_for_purchase") == "on"
                bundle.featured = request.POST.get("featured") == "on"
                # Handle images
                images_json = request.POST.get("images", "[]")
                try:
                    bundle.images = json.loads(images_json) if images_json else []
                except json.JSONDecodeError:
                    pass  # Keep existing images if JSON is invalid
                bundle.save()

                # Update products
                product_ids = request.POST.getlist("product_ids")
                bundle.items.all().delete()
                for i, product_id in enumerate(product_ids):
                    if product_id:
                        product = Product.objects.get(id=product_id)
                        BundleItem.objects.create(
                            bundle=bundle,
                            product=product,
                            quantity=1,
                            display_order=i,
                        )

                messages.success(request, f'Bundle "{bundle.name}" updated!')
            except Bundle.DoesNotExist:
                messages.error(request, "Bundle not found")
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")

            return redirect("admin_bundles")

        elif action == "delete":
            bundle_id = request.POST.get("bundle_id")
            try:
                bundle = Bundle.objects.get(id=bundle_id)
                name = bundle.name
                bundle.delete()
                messages.success(request, f'Bundle "{name}" deleted!')
            except Bundle.DoesNotExist:
                messages.error(request, "Bundle not found")

            return redirect("admin_bundles")

        elif action == "toggle_active":
            bundle_id = request.POST.get("bundle_id")
            try:
                bundle = Bundle.objects.get(id=bundle_id)
                bundle.is_active = not bundle.is_active
                bundle.save()
                status = "activated" if bundle.is_active else "deactivated"
                messages.success(request, f'Bundle "{bundle.name}" {status}!')
            except Bundle.DoesNotExist:
                messages.error(request, "Bundle not found")

            return redirect("admin_bundles")

    # Get all bundles
    bundles = Bundle.objects.prefetch_related("items__product").all().order_by("-created_at")

    # Build availability data for each bundle
    bundles_with_stock = []
    for bundle in bundles:
        available_sizes = bundle.get_available_sizes()
        size_stock_data = []
        total_available = 0

        for size in available_sizes:
            variants_for_size = bundle.get_variants_for_size(size)
            skus = []
            max_qty = 999

            if variants_for_size:
                for item, variant in variants_for_size:
                    skus.append(variant.sku)
                    available_bundles = variant.stock_quantity // item.quantity
                    max_qty = min(max_qty, available_bundles)

            if max_qty != 999 and max_qty > 0:
                size_stock_data.append({
                    "size": size.label or size.code,
                    "quantity": max_qty,
                    "skus": skus,
                })
                total_available += max_qty

        bundles_with_stock.append({
            "bundle": bundle,
            "size_stock": size_stock_data,
            "total_available": total_available,
        })

    # Get all products for the create/edit form
    products = Product.objects.filter(is_active=True).order_by("name")

    context = {
        "bundles_with_stock": bundles_with_stock,
        "products": products,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/bundles_dashboard.html", context)


