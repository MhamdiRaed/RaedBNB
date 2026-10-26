# RaedBNB

RaedBNB is a Django-rendered rental home website. The frontend uses Django
templates and static CSS; a separate JavaScript frontend server is not needed.

## Run locally

From the project directory:

```sh
cd backend
source ../.venv/bin/activate
python manage.py migrate
python manage.py runserver
```

Open [http://localhost:8000](http://localhost:8000). SQLite is the default
database and does not require a separate database server.

The rental catalogue is stored in SQLite. Existing sample properties are seeded
as clearly marked demo listings. Register with the landlord role, sign in, and
select **List a home** to create a rental listing. Landlord submissions are
published immediately and appear in search; optional property photos are stored
under `backend/media/`. Listings can also be managed through Django admin at
`/admin/`. Registration, sign-in,
sign-out, keyword/bedroom/budget search, and monthly-price filtering are handled
by Django. The About and Contact pages are available from the navigation; contact
form submissions are saved in SQLite and can be reviewed in Django admin.
The JSON API remains available under `/api/`, and `/health/` provides a health
check."
