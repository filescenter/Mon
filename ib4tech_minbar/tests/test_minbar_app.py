from datetime import timedelta

from odoo import http
from odoo.tests import HttpCase, tagged
from odoo.tests.common import HOST

# Smallest valid PNG, used as a poster.
PIXEL = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")

from .common import MinbarCommon


@tagged("post_install", "-at_install")
class TestMinbarApp(HttpCase, MinbarCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setup_minbar()
        cls.owner.password = "owner-password-1"
        # Visitors who picked no city see the default one first.
        cls.env["ir.config_parameter"].set_param("ib4tech_minbar.default_city_id", str(cls.city.id))
        category = cls.env["ib4tech.minbar.content.category"].create({"name": "Test Duas"})
        cls.content = cls.env["ib4tech.minbar.content"].create({
            "name": "Visible Dua", "category_id": category.id, "body": "<p>Text</p>"})
        cls.hidden_content = cls.env["ib4tech.minbar.content"].create({
            "name": "Hidden Dua", "category_id": category.id, "is_published": False})

    def test_public_pages_render(self):
        for url in (
            "/app", "/app/majalis", "/app/majalis?when=today&city=%d" % self.city.id,
            "/app/majalis?q=Published&audience=women&when=week", "/app/directory",
            "/app/directory?q=Owner", "/app/directory/mawkib", "/app/directory/radood",
            "/app/e/%d" % self.entity.id, "/app/majlis/%d" % self.majlis.id,
            "/app/library", "/app/library?q=Visible", "/app/library/%d" % self.content.category_id.id,
            "/app/read/%d" % self.content.id, "/app/prayer", "/app/qibla", "/app/tasbih",
            "/app/occasions", "/app/more", "/app/favorites", "/app/join", "/app/offline",
        ):
            with self.subTest(url=url):
                response = self.url_open(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn('dir="rtl"', response.text)

    def test_unpublished_records_are_hidden(self):
        draft_majlis = self.env["ib4tech.minbar.majlis"].create({
            "name": "Draft Majlis", "entity_id": self.entity.id, "date_start": self.start})
        hidden_majlis = self.env["ib4tech.minbar.majlis"].create({
            "name": "Majlis Of Hidden Page", "entity_id": self.hidden_entity.id,
            "date_start": self.start, "state": "published"})
        for url in (
            "/app/e/%d" % self.hidden_entity.id, "/app/majlis/%d" % draft_majlis.id,
            "/app/majlis/%d" % hidden_majlis.id, "/app/majlis/%d/calendar.ics" % draft_majlis.id,
            "/app/read/%d" % self.hidden_content.id, "/app/directory/unknown", "/app/e/999999",
            "/app/image/entity/%d/image_256" % self.hidden_entity.id,
            "/app/image/entity/%d/contact_phone" % self.entity.id,
        ):
            with self.subTest(url=url):
                self.assertEqual(self.url_open(url).status_code, 404)
        listing = self.url_open("/app/majalis").text
        self.assertIn("Published Majlis", listing)
        self.assertNotIn("Draft Majlis", listing)
        self.assertNotIn("Majlis Of Hidden Page", listing)
        self.assertNotIn("Hidden Page", self.url_open("/app/directory/husseiniya").text)
        self.assertNotIn("Hidden Dua", self.url_open("/app/library?q=Dua").text)
        cards = self.url_open("/app/favorites/cards?e=%d,%d&m=%d,%d" % (
            self.entity.id, self.hidden_entity.id, self.majlis.id, draft_majlis.id)).text
        self.assertIn("Owner Mawkib", cards)
        self.assertNotIn("Hidden Page", cards)
        self.assertNotIn("Draft Majlis", cards)

    def test_contact_details_never_rendered(self):
        self.assertNotIn("07700000000", self.url_open("/app/e/%d" % self.entity.id).text)

    def test_calendar_file(self):
        response = self.url_open("/app/majlis/%d/calendar.ics" % self.majlis.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/calendar", response.headers["Content-Type"])
        self.assertIn("SUMMARY:Published Majlis", response.text)
        self.assertIn("DTSTART:%s" % self.start.strftime("%Y%m%dT%H%M%SZ"), response.text)

    def test_pwa_plumbing(self):
        manifest = self.url_open("/app/manifest.webmanifest").json()
        self.assertEqual(manifest["start_url"], "/app")
        self.assertEqual(manifest["dir"], "rtl")
        worker = self.url_open("/app/sw.js")
        self.assertEqual(worker.headers["Service-Worker-Allowed"], "/app")
        self.assertNotIn("__VERSION__", worker.text)
        urls = self.url_open("/app/offline/urls").json()
        self.assertIn("/app/read/%d" % self.content.id, urls)
        self.assertNotIn("/app/read/%d" % self.hidden_content.id, urls)

    def test_join_request(self):
        Entity = self.env["ib4tech.minbar.entity"]
        self.authenticate(None, None)  # anonymous session, needed for the CSRF token
        data = {
            "csrf_token": http.Request.csrf_token(self),
            "name": "Joined Mawkib", "entity_type": "mawkib", "city_id": str(self.city.id),
            "contact_name": "Abu Hasan", "contact_phone": "07711111111",
        }
        response = self.url_open("/app/join", data=data)
        self.assertEqual(response.status_code, 200)
        page = Entity.search([("name", "=", "Joined Mawkib")])
        self.assertEqual(page.state, "pending")
        self.assertEqual(page.contact_phone, "07711111111")
        self.assertFalse(page.owner_user_id)
        # Missing contact: nothing is created and the form comes back with a message.
        self.url_open("/app/join", data=dict(data, name="No Contact", contact_phone=""))
        self.assertFalse(Entity.search([("name", "=", "No Contact")]))
        # Bots filling the hidden field are silently ignored.
        self.url_open("/app/join", data=dict(data, name="Bot Page", nickname="x"))
        self.assertFalse(Entity.search([("name", "=", "Bot Page")]))

    def test_visitor_city_comes_first(self):
        other_city = self.env["ib4tech.minbar.city"].create({"name": "Far City"})
        far_page = self.env["ib4tech.minbar.entity"].create({
            "name": "Far Husseiniya", "entity_type": "husseiniya", "state": "published",
            "city_id": other_city.id})
        self.env["ib4tech.minbar.majlis"].create({
            "name": "Far Majlis", "entity_id": far_page.id, "date_start": self.start,
            "state": "published"})
        self.env["ir.config_parameter"].set_param("ib4tech_minbar.default_city_id", str(self.city.id))
        # No choice yet: the default city decides.
        home = self.url_open("/app").text
        self.assertIn("Published Majlis", home)
        self.assertNotIn("Far Majlis", home)
        self.assertNotIn("Far Majlis", self.url_open("/app/majalis").text)
        # An explicit "all cities" filter and a search both look everywhere.
        self.assertIn("Far Majlis", self.url_open("/app/majalis?city=").text)
        self.assertIn("Far Majlis", self.url_open("/app/majalis?q=Far").text)
        # The city picked in the app wins over the default one.
        self.opener.cookies.set("minbar_city", str(other_city.id), domain=HOST, path="/app")
        home = self.url_open("/app").text
        self.assertIn("Far Majlis", home)
        self.assertNotIn("Published Majlis", home)

    def test_poster_and_link_preview(self):
        poster_url = "/app/image/majlis/%d/poster" % self.majlis.id
        self.assertEqual(self.url_open(poster_url).status_code, 404)
        self.majlis.poster = PIXEL
        self.assertTrue(self.majlis.has_poster)
        response = self.url_open(poster_url + "?size=thumb")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["Content-Type"].startswith("image/"))
        page = self.url_open("/app/majlis/%d" % self.majlis.id).text
        self.assertIn('property="og:image"', page)
        self.assertIn(poster_url, page)
        # The poster of a majlis that is not public stays hidden.
        self.majlis.state = "pending"
        self.assertEqual(self.url_open(poster_url).status_code, 404)
        self.authenticate("minbar_owner", "owner-password-1")
        self.assertEqual(self.url_open(poster_url).status_code, 200)

    def test_announcement(self):
        Ad = self.env["ib4tech.minbar.ad"]
        Ad.search([]).active = False  # sample announcements of the demo data
        self.assertNotIn('id="mb-ad"', self.url_open("/app").text)
        ad = Ad.create({"name": "Majlis Poster", "image": PIXEL, "majlis_id": self.majlis.id})
        poster_url = "/app/image/ad/%d/poster" % ad.id
        hit_url = self.base_url() + "/app/ad/%d/hit" % ad.id
        home = self.url_open("/app").text
        self.assertIn('id="mb-ad"', home)
        self.assertIn(poster_url, home)
        self.assertIn("/app/majlis/%d" % self.majlis.id, home)
        self.assertEqual(self.url_open(poster_url).status_code, 200)
        # Views and taps are counted by the app in the background.
        self.assertEqual(self.opener.post(hit_url + "?kind=view").status_code, 204)
        self.opener.post(hit_url + "?kind=view")
        self.opener.post(hit_url + "?kind=click")
        self.opener.post(hit_url + "?kind=other")
        ad.invalidate_recordset()
        self.assertEqual((ad.view_count, ad.click_count), (2, 1))
        # Only in another city: hidden here, shown to a visitor of that city.
        other_city = self.env["ib4tech.minbar.city"].create({"name": "Ad City"})
        ad.city_ids = other_city
        self.assertNotIn('id="mb-ad"', self.url_open("/app").text)
        self.opener.cookies.set("minbar_city", str(other_city.id), domain=HOST, path="/app")
        self.assertIn('id="mb-ad"', self.url_open("/app").text)
        ad.city_ids = False
        # Past its window: gone from the home page, the poster and the counters.
        ad.date_end = self.start - timedelta(days=3)
        self.assertNotIn('id="mb-ad"', self.url_open("/app").text)
        self.assertEqual(self.url_open(poster_url).status_code, 404)
        self.opener.post(hit_url + "?kind=view")
        ad.invalidate_recordset()
        self.assertEqual(ad.view_count, 2)
        # A tap leads nowhere once the majlis is no longer public.
        self.majlis.state = "cancelled"
        self.assertEqual(ad._target_url(), "")
        ad.url = "javascript:alert(1)"
        self.assertEqual(ad._target_url(), "")
        ad.url = "https://example.com/poster"
        self.assertEqual(ad._target_url(), "https://example.com/poster")

    def test_information_pages(self):
        Page = self.env["ib4tech.minbar.page"]
        privacy = self.env.ref("ib4tech_minbar.page_privacy")
        response = self.url_open("/app/page/privacy")
        self.assertEqual(response.status_code, 200)
        self.assertIn(privacy.name, response.text)
        self.assertIn("/app/page/privacy", self.url_open("/app/more").text)
        self.assertEqual(self.url_open("/app/page/unknown").status_code, 404)
        privacy.active = False
        self.assertEqual(self.url_open("/app/page/privacy").status_code, 404)
        with self.assertRaises(Exception), self.cr.savepoint():
            Page.create({"name": "Bad", "slug": "Not Valid"})

    def test_android_asset_links(self):
        def packages():
            return [item["target"].get("package_name") for item in self.url_open(
                "/.well-known/assetlinks.json").json()]

        # Odoo's own entries (its mobile app) stay; ours appears once configured.
        before = packages()
        self.assertNotIn("com.ib4tech.siddiqa", before)
        params = self.env["ir.config_parameter"]
        params.set_param("ib4tech_minbar.android_package", "com.ib4tech.siddiqa")
        params.set_param("ib4tech_minbar.android_fingerprints", "aa:bb:cc, DD:EE:FF")
        links = self.url_open("/.well-known/assetlinks.json").json()
        self.assertEqual([item["target"].get("package_name") for item in links[:-1]], before)
        self.assertEqual(links[-1]["target"]["package_name"], "com.ib4tech.siddiqa")
        self.assertEqual(links[-1]["target"]["sha256_cert_fingerprints"], ["AA:BB:CC", "DD:EE:FF"])
        self.assertEqual(links[-1]["relation"], ["delegate_permission/common.handle_all_urls"])

    def test_reader_navigation(self):
        second = self.env["ib4tech.minbar.content"].create({
            "name": "Second Dua", "category_id": self.content.category_id.id, "sequence": 20})
        first_page = self.url_open("/app/read/%d" % self.content.id).text
        self.assertIn("/app/read/%d" % second.id, first_page)
        self.assertNotIn("/app/read/%d" % self.hidden_content.id, first_page)
        self.assertIn("/app/read/%d" % self.content.id, self.url_open("/app/read/%d" % second.id).text)

    def test_owner_dashboard_requires_login(self):
        response = self.url_open("/app/my", allow_redirects=False)
        self.assertIn(response.status_code, (302, 303))
        self.assertIn("/web/login", response.headers["Location"])

    def test_owner_flow(self):
        self.authenticate("minbar_owner", "owner-password-1")
        token = http.Request.csrf_token(self)
        self.assertIn("Owner Mawkib", self.url_open("/app/my").text)
        self.assertEqual(self.url_open("/app/my/entity/%d" % self.other_entity.id).status_code, 404)

        self.url_open("/app/my/entity/%d" % self.entity.id, data={
            "csrf_token": token, "name": "Owner Mawkib", "tagline": "Edited from the phone",
            "phone": "07722222222", "city_id": str(self.city.id)})
        self.assertEqual(self.entity.tagline, "Edited from the phone")
        self.assertEqual(self.entity.state, "published")

        # Someone else's page cannot be saved, even with a forged form.
        self.url_open("/app/my/entity/%d" % self.other_entity.id, data={
            "csrf_token": token, "name": "Hijacked"})
        self.assertEqual(self.other_entity.name, "Other Husseiniya")

        day = (self.start + timedelta(days=2)).strftime("%Y-%m-%d")
        self.url_open("/app/my/majlis/new", data={
            "csrf_token": token, "name": "Ten Nights", "entity_id": str(self.entity.id),
            "date": day, "time_start": "19:30", "time_end": "21:00", "repeat_days": "2",
            "participant_ids": str(self.radood.id), "audience": "all"})
        majalis = self.env["ib4tech.minbar.majlis"].search([("name", "=", "Ten Nights")])
        self.assertEqual(len(majalis), 3)
        self.assertEqual(set(majalis.mapped("state")), {"pending"})
        # 19:30 in Baghdad is 16:30 UTC.
        self.assertEqual(majalis[0].date_start.strftime("%Y-%m-%d %H:%M"), "%s 16:30" % day)
        self.assertEqual(majalis[0].participant_ids, self.radood)

        self.url_open("/app/my/majlis/new", data={
            "csrf_token": token, "name": "Forged Majlis", "entity_id": str(self.other_entity.id),
            "date": day, "time_start": "19:30"})
        self.assertFalse(self.env["ib4tech.minbar.majlis"].search([("name", "=", "Forged Majlis")]))

        self.url_open("/app/my/majlis/%d/cancel" % self.majlis.id, data={"csrf_token": token})
        self.assertEqual(self.majlis.state, "cancelled")

    def test_owner_previews_unpublished_page(self):
        self.entity.state = "pending"
        self.assertEqual(self.url_open("/app/e/%d" % self.entity.id).status_code, 404)
        self.authenticate("minbar_owner", "owner-password-1")
        self.assertEqual(self.url_open("/app/e/%d" % self.entity.id).status_code, 200)
