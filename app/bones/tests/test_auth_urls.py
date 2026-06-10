from django.contrib.auth.views import LoginView
from django.template.loader import get_template
from django.test import SimpleTestCase
from django.urls import resolve, reverse


class AuthenticationUrlTests(SimpleTestCase):
    def test_login_url_is_registered_with_template(self):
        match = resolve(reverse("login"))
        template = get_template("registration/login.html")

        self.assertIs(match.func.view_class, LoginView)
        self.assertEqual(template.origin.template_name, "registration/login.html")

    def test_dashboard_redirects_anonymous_users_to_login(self):
        response = self.client.get(reverse("bones:dashboard"))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('bones:dashboard')}",
            fetch_redirect_response=False,
        )
