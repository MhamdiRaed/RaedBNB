from io import BytesIO
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase
from django.test import override_settings
from PIL import Image

from .models import ContactMessage, Property, User


class AuthenticationApiTests(APITestCase):
	def test_register_login_and_fetch_current_user(self):
		registration = self.client.post(
			"/api/auth/register/",
			{
				"username": "amina",
				"email": "amina@example.com",
				"phone": "+21612345678",
				"password": "secure-pass-123",
				"role": "landlord",
			},
			format="json",
		)

		self.assertEqual(registration.status_code, status.HTTP_201_CREATED)
		user = User.objects.get(username="amina")
		self.assertTrue(user.check_password("secure-pass-123"))

		login = self.client.post(
			"/api/auth/login/",
			{"username": "amina", "password": "secure-pass-123"},
			format="json",
		)

		self.assertEqual(login.status_code, status.HTTP_200_OK)
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
		me = self.client.get("/api/auth/me/")

		self.assertEqual(me.status_code, status.HTTP_200_OK)
		self.assertEqual(
			me.data,
			{
				"id": user.id,
				"username": "amina",
				"email": "amina@example.com",
				"phone": "+21612345678",
				"role": "landlord",
			},
		)
from django.test import TestCase

from .models import User


class RentalPagesTests(TestCase):
	def test_homepage_shows_rental_content_without_ai_or_tour_features(self):
		response = self.client.get("/")

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Find the right home")
		self.assertContains(response, "Homes to rent")
		self.assertContains(response, 'href="/about/"')
		self.assertContains(response, 'href="/contact/"')
		self.assertNotContains(response, "AI")
		self.assertNotContains(response, "360")
		self.assertContains(response, "Sample listing")

	def test_explore_filters_by_keyword_and_maximum_monthly_price(self):
		response = self.client.get(
			"/explore/",
			{"q": "Tunis", "max_price": "1200"},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Modern apartment")
		self.assertNotContains(response, "Sea-view villa")

	def test_home_search_supports_bedrooms_city_and_budget(self):
		response = self.client.get(
			"/explore/",
			{"q": "2-bedroom apartment in Tunis under 1200 DT"},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Modern apartment")
		self.assertNotContains(response, "Sea-view villa")
		self.assertContains(response, 'id="max-price-value">1200 DT</strong>')

	def test_maximum_price_filter_updates_results(self):
		response = self.client.get("/explore/", {"max_price": "1000"})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Cozy studio")
		self.assertContains(response, "Family flat")
		self.assertNotContains(response, "Modern apartment")

	def test_published_properties_are_read_from_the_database(self):
		property_listing = Property.objects.create(
			title="Sunny rental",
			description="A bright rental near the university.",
			property_type=Property.PropertyType.APARTMENT,
			city="Monastir",
			bedrooms=2,
			bathrooms=1,
			area_sqm="72.50",
			monthly_rent="750.00",
			is_published=True,
		)
		unpublished = Property.objects.create(
			title="Private draft",
			city="Monastir",
			bedrooms=1,
			area_sqm="40",
			monthly_rent="500",
			is_published=False,
		)

		homepage = self.client.get("/")
		search_results = self.client.get("/explore/", {"q": "university"})

		self.assertContains(homepage, property_listing.title)
		self.assertNotContains(homepage, unpublished.title)
		self.assertContains(search_results, property_listing.title)
		self.assertNotContains(search_results, unpublished.title)

	def test_admin_can_create_a_property_with_an_uploaded_photo(self):
		admin_user = User.objects.create_superuser(
			username="siteadmin",
			email="admin@example.com",
			password="admin-pass-123",
		)
		self.client.force_login(admin_user)
		image_bytes = BytesIO()
		Image.new("RGB", (2, 2), color="teal").save(image_bytes, format="PNG")
		image = SimpleUploadedFile(
			"rental.png",
			image_bytes.getvalue(),
			content_type="image/png",
		)

		with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
			response = self.client.post(
				"/admin/users/property/add/",
				{
					"title": "Admin-created rental",
					"description": "An available rental home.",
					"property_type": Property.PropertyType.APARTMENT,
					"city": "Nabeul",
					"address": "",
					"bedrooms": "2",
					"bathrooms": "1",
					"area_sqm": "75",
					"monthly_rent": "850",
					"owner": "",
					"is_published": "on",
					"photo": image,
				},
			)

			self.assertEqual(response.status_code, 302)
			property_listing = Property.objects.get(title="Admin-created rental")
			self.assertTrue(property_listing.is_published)
			self.assertTrue(property_listing.photo.storage.exists(property_listing.photo.name))

	def test_landlord_can_publish_a_property_from_the_site_form(self):
		landlord = User.objects.create_user(
			username="landlord",
			email="landlord@example.com",
			password="landlord-pass-123",
			role=User.Role.LANDLORD,
		)
		self.client.force_login(landlord)

		response = self.client.post(
			"/add-property/",
			{
				"title": "Sunny Monastir apartment",
				"property_type": Property.PropertyType.APARTMENT,
				"city": "Monastir",
				"address": "Near the beach",
				"description": "A bright two-bedroom rental.",
				"bedrooms": "2",
				"bathrooms": "1",
				"area_sqm": "82.5",
				"monthly_rent": "950",
			},
		)

		self.assertRedirects(response, "/add-property/?created=1")
		property_listing = Property.objects.get(title="Sunny Monastir apartment")
		self.assertEqual(property_listing.owner, landlord)
		self.assertTrue(property_listing.is_published)
		self.assertFalse(property_listing.is_demo)
		self.assertContains(self.client.get("/explore/", {"q": "Monastir"}), property_listing.title)
		self.assertContains(self.client.get("/add-property/"), "Your rental listings")

	def test_landlord_property_form_rejects_non_positive_rent(self):
		landlord = User.objects.create_user(
			username="landlord",
			email="landlord@example.com",
			password="landlord-pass-123",
			role=User.Role.LANDLORD,
		)
		self.client.force_login(landlord)

		response = self.client.post(
			"/add-property/",
			{
				"title": "Invalid rental",
				"property_type": Property.PropertyType.APARTMENT,
				"city": "Tunis",
				"bedrooms": "2",
				"bathrooms": "1",
				"area_sqm": "75",
				"monthly_rent": "0",
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Ensure this value is greater than or equal to 0.01.")
		self.assertFalse(Property.objects.filter(title="Invalid rental").exists())

	def test_property_form_validates_and_saves_uploaded_photo(self):
		landlord = User.objects.create_user(
			username="landlord",
			email="landlord@example.com",
			password="landlord-pass-123",
			role=User.Role.LANDLORD,
		)
		self.client.force_login(landlord)
		image_bytes = BytesIO()
		Image.new("RGB", (2, 2), color="teal").save(image_bytes, format="PNG")
		photo = SimpleUploadedFile(
			"rental.png",
			image_bytes.getvalue(),
			content_type="image/png",
		)

		with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
			response = self.client.post(
				"/add-property/",
				{
					"title": "Sunny photo rental",
					"property_type": Property.PropertyType.APARTMENT,
					"city": "Nabeul",
					"description": "A rental with a photo.",
					"bedrooms": "2",
					"bathrooms": "1",
					"area_sqm": "75",
					"monthly_rent": "850",
					"photo": photo,
				},
			)

			self.assertRedirects(response, "/add-property/?created=1")
			property_listing = Property.objects.get(title="Sunny photo rental")
			self.assertTrue(property_listing.photo.storage.exists(property_listing.photo.name))

	def test_non_landlord_cannot_add_a_property(self):
		renter = User.objects.create_user(
			username="renter",
			email="renter@example.com",
			password="renter-pass-123",
			role=User.Role.CLIENT,
		)
		self.client.force_login(renter)

		response = self.client.get("/add-property/")

		self.assertRedirects(response, "/")

	def test_property_search_filters_bedrooms_and_database_price(self):
		Property.objects.create(
			title="Monastir apartment",
			description="Two-bedroom rental close to the university.",
			property_type=Property.PropertyType.APARTMENT,
			city="Monastir",
			bedrooms=2,
			bathrooms=1,
			area_sqm="72.50",
			monthly_rent="750.00",
			is_published=True,
		)
		response = self.client.get(
			"/explore/",
			{"q": "2-bedroom apartment in Monastir under 800 DT"},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Monastir apartment")
		self.assertNotContains(response, "Modern apartment")

	def test_about_and_contact_pages_are_reachable_from_navigation(self):
		about_response = self.client.get("/about/")
		contact_response = self.client.get("/contact/")

		self.assertEqual(about_response.status_code, 200)
		self.assertContains(about_response, "About us")
		self.assertEqual(contact_response.status_code, 200)
		self.assertContains(contact_response, "Contact us")
		self.assertContains(contact_response, 'name="message"')

	def test_contact_form_saves_a_message(self):
		response = self.client.post(
			"/contact/",
			{
				"name": "Amina",
				"email": "amina@example.com",
				"subject": "Rental question",
				"message": "I would like to ask about a home.",
			},
		)

		self.assertRedirects(response, "/contact/?sent=1")
		confirmation = self.client.get(response.url)
		self.assertContains(confirmation, "Your message has been received.")
		self.assertEqual(ContactMessage.objects.count(), 1)
		self.assertEqual(ContactMessage.objects.get().email, "amina@example.com")

	def test_registration_creates_and_signs_in_a_user(self):
		response = self.client.post(
			"/register/",
			{
				"username": "amina",
				"email": "amina@example.com",
				"phone": "+21612345678",
				"password": "secure-pass-123",
				"role": "landlord",
			},
		)

		self.assertRedirects(response, "/")
		user = User.objects.get(username="amina")
		self.assertTrue(user.check_password("secure-pass-123"))
		self.assertEqual(user.role, User.Role.LANDLORD)
		self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
		self.client.post("/logout/")

		login_response = self.client.post(
			"/login/",
			{"username": "amina", "password": "secure-pass-123"},
		)

		self.assertRedirects(login_response, "/")
		self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

	def test_login_and_logout_use_django_sessions(self):
		User.objects.create_user(
			username="amina",
			email="amina@example.com",
			password="secure-pass-123",
		)

		login_response = self.client.post(
			"/login/",
			{"username": "amina", "password": "secure-pass-123"},
		)

		self.assertRedirects(login_response, "/")
		self.assertTrue("_auth_user_id" in self.client.session)
		logout_response = self.client.post("/logout/")
		self.assertRedirects(logout_response, "/")
		self.assertNotIn("_auth_user_id", self.client.session)

	def test_list_a_home_requires_sign_in(self):
		response = self.client.get("/add-property/")

		self.assertRedirects(response, "/login/?next=/add-property/")

	def test_login_rejects_an_incorrect_password(self):
		User.objects.create_user(
			username="amina",
			email="amina@example.com",
			password="secure-pass-123",
		)

		response = self.client.post(
			"/login/",
			{"username": "amina", "password": "incorrect-password"},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Invalid username or password.")
		self.assertNotIn("_auth_user_id", self.client.session)
