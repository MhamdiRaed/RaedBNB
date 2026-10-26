import re
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import ContactMessage, Property


class RegistrationForm(forms.Form):
    ROLE_CHOICES = (
        ("client", "I'm looking"),
        ("landlord", "I'm a landlord"),
    )

    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=30, required=False)
    password = forms.CharField(min_length=8, strip=False)
    role = forms.ChoiceField(choices=ROLE_CHOICES)

    def clean_username(self):
        username = self.cleaned_data["username"]
        user_model = get_user_model()
        if user_model.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already in use.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"]
        user_model = get_user_model()
        if user_model.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def create_user(self):
        user_model = get_user_model()
        return user_model.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            phone=self.cleaned_data["phone"],
            password=self.cleaned_data["password"],
            role=self.cleaned_data["role"],
        )


class ContactMessageForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ("name", "email", "subject", "message")
        widgets = {
            "message": forms.Textarea(attrs={"rows": 5}),
        }


class PropertyForm(forms.ModelForm):
    area_sqm = forms.DecimalField(
        min_value=Decimal("0.01"),
        max_digits=8,
        decimal_places=2,
        label="Area (m²)",
        widget=forms.NumberInput(attrs={"step": "0.01", "placeholder": "e.g. 85"}),
    )
    monthly_rent = forms.DecimalField(
        min_value=Decimal("0.01"),
        max_digits=10,
        decimal_places=2,
        label="Monthly rent (DT)",
        widget=forms.NumberInput(attrs={"step": "0.01", "placeholder": "e.g. 1100"}),
    )

    class Meta:
        model = Property
        fields = (
            "title",
            "property_type",
            "city",
            "address",
            "description",
            "bedrooms",
            "bathrooms",
            "area_sqm",
            "monthly_rent",
            "photo",
        )
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. Sunny apartment"}),
            "city": forms.TextInput(attrs={"placeholder": "e.g. Tunis"}),
            "address": forms.TextInput(attrs={"placeholder": "Street or neighborhood (optional)"}),
            "description": forms.Textarea(attrs={"rows": 5, "placeholder": "Describe the home and its features"}),
            "bedrooms": forms.NumberInput(attrs={"min": 0, "max": 50}),
            "bathrooms": forms.NumberInput(attrs={"min": 1, "max": 50}),
            "photo": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bedrooms"].min_value = 0
        self.fields["bathrooms"].min_value = 1
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", "form-input")
            if field.required:
                field.widget.attrs.setdefault("required", "required")
            else:
                field.widget.attrs.pop("required", None)


def home(request):
    return render(
        request,
        "users/home.html",
        {"listings": Property.objects.filter(is_published=True)[:3]},
    )


def explore(request):
    query = request.GET.get("q", "").strip()
    try:
        max_price = min(
            max(Decimal(request.GET.get("max_price", "3000")), Decimal("300")),
            Decimal("3000"),
        )
    except (InvalidOperation, TypeError, ValueError):
        max_price = Decimal("3000")

    normalized_query = query.casefold()
    room_match = re.search(
        r"\b(\d+)\s*[- ]?(?:bedrooms?|beds?|rooms?)\b",
        normalized_query,
    )
    if room_match:
        room_count = int(room_match.group(1))
        normalized_query = normalized_query[:room_match.start()] + normalized_query[room_match.end():]
    else:
        room_count = None

    budget_match = re.search(
        r"\b(?:under|below|less than|up to|max(?:imum)?)\s*([\d,]+)\s*(?:dt|tnd)?\b",
        normalized_query,
    )
    if budget_match:
        budget = Decimal(budget_match.group(1).replace(",", ""))
        max_price = min(max_price, budget)
        normalized_query = normalized_query[:budget_match.start()] + normalized_query[budget_match.end():]

    ignored_terms = {
        "a", "an", "at", "below", "bed", "beds", "bedroom", "bedrooms",
        "dt", "in", "less", "max", "maximum", "month", "monthly", "of",
        "per", "room", "rooms", "than", "the", "to", "tnd", "under", "up",
        "with",
    }
    search_terms = [
        term
        for term in re.findall(r"[a-z0-9]+", normalized_query)
        if term not in ignored_terms
    ]

    listings = Property.objects.filter(
        is_published=True,
        monthly_rent__lte=max_price,
    )
    if room_count is not None:
        listings = listings.filter(bedrooms=room_count)
    for term in search_terms:
        listings = listings.filter(
            Q(title__icontains=term)
            | Q(city__icontains=term)
            | Q(description__icontains=term)
            | Q(property_type__icontains=term)
        )
    return render(
        request,
        "users/explore.html",
        {
            "listings": listings,
            "query": query,
            "max_price": int(max_price),
        },
    )


def about(request):
    return render(request, "users/about.html")


def contact(request):
    form = ContactMessageForm(request.POST or None)
    submitted = request.GET.get("sent") == "1"
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(f"{reverse('site:contact')}?sent=1")
    return render(
        request,
        "users/contact.html",
        {"form": form, "submitted": submitted},
    )


def sign_in(request):
    if request.user.is_authenticated:
        return redirect("site:home")

    error = ""
    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.POST.get("next") or request.GET.get("next", "")
            if url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect("site:home")
        error = "Invalid username or password."

    return render(request, "users/login.html", {"error": error})


def register(request):
    if request.user.is_authenticated:
        return redirect("site:home")

    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.create_user()
        login(request, user)
        return redirect("site:home")

    return render(request, "users/register.html", {"form": form})


@require_POST
def sign_out(request):
    logout(request)
    return redirect("site:home")


@login_required(login_url="site:login")
def add_property(request):
    if getattr(request.user, "role", None) != "landlord":
        return redirect("site:home")

    form = PropertyForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        property_listing = form.save(commit=False)
        property_listing.owner = request.user
        property_listing.is_published = True
        property_listing.is_demo = False
        property_listing.save()
        return redirect(f"{reverse('site:add-property')}?created=1")

    return render(
        request,
        "users/add_property.html",
        {
            "form": form,
            "created": request.GET.get("created") == "1",
            "my_properties": Property.objects.filter(owner=request.user),
        },
    )
