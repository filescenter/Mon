{
    "name": "IB4Tech Al-Siddiqa",
    "version": "19.0.1.2.0",
    "category": "Community",
    "summary": "Husseiniyas, mawakib, radoods, majalis schedule and devotional library with a mobile PWA",
    "description": """
IB4Tech Al-Siddiqa (الصدّيقة)
=============================
Community platform for husseini services:

* Directory of husseiniyas, mawakib, radoods and khatibs, each with its own page.
* Majalis schedule by city, date and audience.
* Devotional library (duas, ziyarat, taqibat), prayer times, qibla, hijri occasions, tasbih.
* Installable mobile web app (PWA) served under /app for anonymous visitors.
* Free portal accounts so that owners maintain their own page and majalis,
  with an approval workflow for the administration.
    """,
    "author": "IB4Tech",
    "company": "IB4Tech",
    "website": "https://ib4tech.com",
    "license": "LGPL-3",
    "depends": ["mail", "portal"],
    "data": [
        "security/ib4tech_minbar_security.xml",
        "security/ir.model.access.csv",
        "data/minbar_city_data.xml",
        "data/minbar_service_data.xml",
        "data/minbar_occasion_data.xml",
        "data/minbar_content_data.xml",
        "wizard/minbar_majlis_repeat_views.xml",
        "views/minbar_entity_views.xml",
        "views/minbar_majlis_views.xml",
        "views/minbar_content_views.xml",
        "views/minbar_ad_views.xml",
        "views/minbar_config_views.xml",
        "views/res_config_settings_views.xml",
        "views/minbar_menus.xml",
        "views/app_layout.xml",
        "views/app_pages.xml",
        "views/app_tools.xml",
        "views/app_owner.xml",
    ],
    "demo": [
        "demo/minbar_demo.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
