from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q


class User(AbstractUser):
	class Role(models.TextChoices):
		CLIENT = "client", "Client"
		LANDLORD = "landlord", "Landlord"

	email = models.EmailField(unique=True)
	phone = models.CharField(max_length=30, blank=True)
	role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)


class ContactMessage(models.Model):
	name = models.CharField(max_length=150)
	email = models.EmailField()
	subject = models.CharField(max_length=200)
	message = models.TextField()
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ("-created_at",)

	def __str__(self):
		return f"{self.subject} — {self.name}"


class Property(models.Model):
	class PropertyType(models.TextChoices):
		APARTMENT = "apartment", "Apartment"
		HOUSE = "house", "House"
		VILLA = "villa", "Villa"
		STUDIO = "studio", "Studio"
		DUPLEX = "duplex", "Duplex"

	owner = models.ForeignKey(
		"users.User",
		on_delete=models.SET_NULL,
		related_name="properties",
		null=True,
		blank=True,
	)
	title = models.CharField(max_length=200)
	description = models.TextField(blank=True)
	property_type = models.CharField(
		max_length=20,
		choices=PropertyType.choices,
		default=PropertyType.HOUSE,
	)
	city = models.CharField(max_length=100, db_index=True)
	address = models.CharField(max_length=255, blank=True)
	bedrooms = models.PositiveSmallIntegerField(default=1)
	bathrooms = models.PositiveSmallIntegerField(default=1)
	area_sqm = models.DecimalField(max_digits=8, decimal_places=2)
	monthly_rent = models.DecimalField(max_digits=10, decimal_places=2, db_index=True)
	photo = models.ImageField(upload_to="properties/", blank=True)
	is_published = models.BooleanField(default=False, db_index=True)
	is_demo = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ("-created_at", "-pk")
		constraints = [
			models.CheckConstraint(
				condition=Q(area_sqm__gt=0),
				name="property_area_must_be_positive",
			),
			models.CheckConstraint(
				condition=Q(monthly_rent__gt=0),
				name="property_rent_must_be_positive",
			),
		]

	def __str__(self):
		return f"{self.title} — {self.city}"
