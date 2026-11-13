from datetime import timedelta

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from .common import MinbarCommon


@tagged("post_install", "-at_install")
class TestMinbarSecurity(TransactionCase, MinbarCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setup_minbar()

    def test_owner_creates_page_in_review_queue(self):
        page = self.env["ib4tech.minbar.entity"].with_user(self.owner).create({
            "name": "New Page", "entity_type": "husseiniya",
            # An owner must not be able to self-publish or hand the page to someone else.
            "state": "published", "is_verified": True, "owner_user_id": self.other_owner.id,
        })
        self.assertEqual(page.state, "pending")
        self.assertFalse(page.is_verified)
        self.assertEqual(page.owner_user_id, self.owner)

    def test_owner_cannot_change_protected_fields(self):
        page = self.entity.with_user(self.owner)
        page.write({"tagline": "Serving the visitors"})
        self.assertEqual(self.entity.tagline, "Serving the visitors")
        for vals in ({"state": "draft"}, {"is_verified": True}, {"owner_user_id": self.other_owner.id}):
            with self.assertRaises(AccessError):
                page.write(vals)

    def test_owner_cannot_touch_other_pages(self):
        with self.assertRaises(AccessError):
            self.other_entity.with_user(self.owner).write({"name": "Hijacked"})
        with self.assertRaises(AccessError):
            self.hidden_entity.with_user(self.owner).read(["name"])
        # Published pages of other owners stay readable, they are public anyway.
        self.assertEqual(self.other_entity.with_user(self.owner).name, "Other Husseiniya")

    def test_contact_details_are_private(self):
        with self.assertRaises(AccessError):
            self.entity.with_user(self.owner).read(["contact_phone"])
        self.assertEqual(self.entity.with_user(self.manager).contact_phone, "07700000000")

    def test_resubmit_after_rejection(self):
        self.entity.with_user(self.manager).write({"reject_reason": "Missing address"})
        self.entity.with_user(self.manager).action_reject()
        self.assertEqual(self.entity.state, "rejected")
        self.entity.with_user(self.owner).action_submit()
        self.assertEqual(self.entity.state, "pending")
        self.assertFalse(self.entity.reject_reason)
        with self.assertRaises(UserError):
            self.entity.with_user(self.owner).action_submit()
        with self.assertRaises(AccessError):
            self.other_entity.with_user(self.owner).action_submit()

    def test_owner_majlis_goes_to_review(self):
        Majlis = self.env["ib4tech.minbar.majlis"].with_user(self.owner)
        majlis = Majlis.create({
            "name": "Evening Majlis", "entity_id": self.entity.id,
            "date_start": self.start, "state": "published",
            "participant_ids": [(6, 0, self.radood.ids)],
        })
        self.assertEqual(majlis.state, "pending")
        self.assertEqual(majlis.city_id, self.city)
        with self.assertRaises(AccessError):
            majlis.write({"state": "published"})
        with self.assertRaises(AccessError):
            Majlis.create({
                "name": "On someone else's page", "entity_id": self.other_entity.id,
                "date_start": self.start,
            })
        with self.assertRaises(AccessError):
            majlis.write({"entity_id": self.other_entity.id})

    def test_verified_owner_is_auto_published(self):
        self.env["ir.config_parameter"].set_param("ib4tech_minbar.auto_publish_verified", "True")
        Majlis = self.env["ib4tech.minbar.majlis"].with_user(self.owner)
        vals = {"name": "Trusted Majlis", "entity_id": self.entity.id, "date_start": self.start}
        self.assertEqual(Majlis.create(dict(vals)).state, "pending")
        self.entity.is_verified = True
        self.assertEqual(Majlis.create(dict(vals)).state, "published")

    def test_owner_cancels_and_repeats(self):
        majlis = self.majlis.with_user(self.owner)
        copies = majlis.action_repeat_daily(9)
        self.assertEqual(len(copies), 9)
        self.assertEqual(copies[-1].date_start, self.start + timedelta(days=9))
        # Copies made by an owner go back through the review rules.
        self.assertEqual(set(copies.mapped("state")), {"pending"})
        majlis.action_cancel()
        self.assertEqual(self.majlis.state, "cancelled")
        with self.assertRaises(AccessError):
            self.env["ib4tech.minbar.majlis"].create({
                "name": "Other", "entity_id": self.other_entity.id, "date_start": self.start,
            }).with_user(self.owner).action_cancel()
        with self.assertRaises(UserError):
            majlis.action_repeat_daily(0)

    def test_majlis_dates_and_participants(self):
        Majlis = self.env["ib4tech.minbar.majlis"]
        with self.assertRaises(Exception):
            with self.cr.savepoint():
                Majlis.create({
                    "name": "Backwards", "entity_id": self.entity.id,
                    "date_start": self.start, "date_end": self.start - timedelta(hours=1),
                })
        with self.assertRaises(Exception):
            with self.cr.savepoint():
                Majlis.create({
                    "name": "Wrong participant", "entity_id": self.entity.id,
                    "date_start": self.start, "participant_ids": [(6, 0, self.other_entity.ids)],
                })

    def test_grant_owner_account_by_phone(self):
        page = self.env["ib4tech.minbar.entity"].create({
            "name": "Requested Page", "entity_type": "mawkib", "state": "pending",
            "contact_name": "Abu Ali", "contact_phone": "0770 111 2222",
        })
        with self.assertRaises(AccessError):
            page.with_user(self.owner).action_grant_portal_access()
        action = page.with_user(self.manager).action_grant_portal_access()
        self.assertEqual(action["tag"], "display_notification")
        user = page.owner_user_id
        self.assertEqual(user.login, "07701112222")
        self.assertTrue(user._is_portal())
        self.assertIn("07701112222", action["params"]["message"])
        with self.assertRaises(UserError):
            page.with_user(self.manager).action_grant_portal_access()

    def test_grant_owner_account_by_email(self):
        page = self.env["ib4tech.minbar.entity"].create({
            "name": "Emailed Page", "entity_type": "husseiniya", "state": "pending",
            "contact_name": "Sayyid Hasan", "contact_email": "Owner@Example.com",
        })
        page.with_user(self.manager).action_grant_portal_access()
        self.assertEqual(page.owner_user_id.login, "owner@example.com")
        self.assertTrue(page.owner_user_id._is_portal())

    def test_publish_notifies_owner(self):
        page = self.env["ib4tech.minbar.entity"].with_user(self.owner).create({
            "name": "Waiting Page", "entity_type": "radood"})
        page.with_user(self.manager).action_publish()
        self.assertEqual(page.state, "published")
        self.assertIn(self.owner.partner_id, page.sudo().message_ids.mapped("partner_ids"))
