from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import ContactMessage, Property, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
	fieldsets = UserAdmin.fieldsets + (("Profile", {"fields": ("phone", "role")}),)
	add_fieldsets = UserAdmin.add_fieldsets + (("Profile", {"fields": ("email", "phone", "role")}),)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
	list_display = ("subject", "name", "email", "created_at")
	search_fields = ("subject", "name", "email", "message")
	readonly_fields = ("created_at",)


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
	list_display = ("title", "city", "monthly_rent", "bedrooms", "is_published", "is_demo")
	list_filter = ("is_published", "property_type", "city", "is_demo")
	search_fields = ("title", "city", "address", "description")
	readonly_fields = ("created_at", "updated_at")
