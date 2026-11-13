from datetime import datetime, timedelta

from odoo.tests import new_test_user


class MinbarCommon:
    """Shared fixtures: one published page owned by a portal user, one owned by another."""

    @classmethod
    def setup_minbar(cls):
        cls.manager = new_test_user(
            cls.env, login="minbar_manager", groups="ib4tech_minbar.group_minbar_manager")
        cls.owner = new_test_user(cls.env, login="minbar_owner", groups="base.group_portal")
        cls.other_owner = new_test_user(cls.env, login="minbar_other", groups="base.group_portal")
        cls.city = cls.env["ib4tech.minbar.city"].create({
            "name": "Test City", "latitude": 31.86, "longitude": 46.08})
        Entity = cls.env["ib4tech.minbar.entity"]
        cls.entity = Entity.create({
            "name": "Owner Mawkib", "entity_type": "mawkib", "city_id": cls.city.id,
            "state": "published", "owner_user_id": cls.owner.id,
            "contact_phone": "07700000000",
        })
        cls.other_entity = Entity.create({
            "name": "Other Husseiniya", "entity_type": "husseiniya",
            "state": "published", "owner_user_id": cls.other_owner.id,
        })
        cls.hidden_entity = Entity.create({
            "name": "Hidden Page", "entity_type": "husseiniya",
            "state": "pending", "owner_user_id": cls.other_owner.id,
        })
        cls.radood = Entity.create({
            "name": "Test Radood", "entity_type": "radood", "state": "published"})
        cls.start = datetime.now().replace(microsecond=0) + timedelta(days=1)
        cls.majlis = cls.env["ib4tech.minbar.majlis"].create({
            "name": "Published Majlis", "entity_id": cls.entity.id,
            "date_start": cls.start, "state": "published",
        })
