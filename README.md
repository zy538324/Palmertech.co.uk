# Palmertech Flask Web App

This project is a Python Flask implementation of the Palmertech homepage, featuring:
- Business introduction and branding
- Service highlights with links
- Contact form (Name, Email, Phone, Message, Consent)
- Business hours
- Footer with additional links

## Project Structure
- `app.py`: Main Flask application
- `templates/`: HTML templates
- `static/`: Static assets (CSS, images)
- `wordpress/themes/palmertech-wp/`: WordPress theme mirroring the Flask layout for cloud hosting import

## How to Run
1. Create a virtual environment (optional but recommended).
2. Install dependencies: `pip install -r requirements.txt`
3. Run the app: `python app.py` (starts Uvicorn on `0.0.0.0:8080` by default)
4. Alternatively, run directly with Uvicorn: `uvicorn app:asgi_app --host 0.0.0.0 --port 8080`
5. Visit `http://localhost:8080` in your browser (override with the `PORT` environment variable if needed)

## Using the WordPress Theme
1. Copy `wordpress/themes/palmertech-wp` into your WordPress installation under `wp-content/themes/`.
2. Ensure file permissions allow WordPress to read the assets (recommended: owner `www-data` with `755` directories and `644` files).
3. Activate **Palmertech WP** from the WordPress admin Appearance → Themes screen.
4. Assign a menu to the **Primary Navigation** location to populate the header links.
5. Set a static homepage (Settings → Reading) to use the bundled `front-page.php` layout. Other pages will use `page.php` while retaining the shared header/footer styling.

## Environment Variables
Create a `.env` file (or configure environment variables in Cloud Run) with at least the following values:

- `SECRET_KEY`: Flask session secret.
- `SENDGRID_API_KEY`: API key with permission to send email.
- `MAIL_DEFAULT_SENDER`: Verified sender address (e.g. `contact@palmertech.co.uk`).
- `MAIL_OWNER_RECIPIENT`: Destination for contact form notifications (defaults to `contact@palmertech.co.uk`).
- `HOST`/`PORT`: Optional overrides for the server bind address and port.

Optional mail server settings from older configurations are no longer required once SendGrid is in use.

## To Do
- Add automated tests for contact/enquiry flows
- Integrate deployment automation for Cloud Run
