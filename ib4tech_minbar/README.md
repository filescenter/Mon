# IB4Tech Minbar (`ib4tech_minbar`)

Odoo 19 module: a community platform for husseini services with an installable
mobile web app (PWA) for anonymous visitors.

- **Version:** 19.0.1.0.0
- **Depends:** `mail`, `portal` (no `website` needed)
- **License:** LGPL-3

## What it does

| Area | Details |
| --- | --- |
| Directory | Pages for husseiniyas, mawakib, radoods and khatibs: picture, cover, city, map, contact channels, services offered. |
| Majalis | Schedule by city, day and audience, live-stream link, calendar reminder (`.ics`), daily repetition (e.g. the ten nights of Muharram). |
| Library | Duas, ziyarat, taqibat in sections, with a reader (font size, screen kept on) and offline reading. |
| Tools | Prayer times (Jafari / Leva method), qibla compass, tasbih counter, hijri date and occasions. |
| Owners | Free portal accounts: each owner edits their own page and submits majalis; the administration approves. |

## The app

Visitors open `/app` on the Odoo domain. No login is needed. From the browser
menu (or the banner on the home page) the app can be installed on the phone.

| URL | Page |
| --- | --- |
| `/app` | Home: hijri date, next prayer, services, upcoming majalis |
| `/app/majalis` | Majalis schedule and filters |
| `/app/directory` | Directory by type |
| `/app/library` | Library |
| `/app/prayer`, `/app/qibla`, `/app/tasbih`, `/app/occasions` | Tools |
| `/app/join` | Public request to add a page (no account) |
| `/app/my` | Owner dashboard (portal login) |

Favourites, the chosen city and the tasbih counter are stored on the visitor's
phone only.

## Back office

Menu **Minbar**:

- **Directory / Majalis**: manage everything directly.
- **Review**: pages and majalis submitted by owners, waiting for approval.
- **Library**: sections and texts.
- **Configuration**: settings, cities (with coordinates for prayer times), hijri occasions, services.

Groups: **Minbar / Editor** (content and reviews) and **Minbar / Manager**
(settings, deletion, owner accounts).

### Giving an owner an account

1. The owner fills `/app/join`, or an editor creates the page.
2. On the page form, tab **Owner**, fill the contact email or phone.
3. Click **Create Owner Account**:
   - with an email, the standard portal invitation is sent;
   - with a phone only, the phone becomes the login and a temporary password is
     shown once, to pass on by phone or WhatsApp.
4. Approve the page. The owner logs in at `/app/my`.

Portal accounts are free: they do not count as paid Odoo users.

## Settings

Minbar > Configuration > Settings:

- **App Name**: shown in the header and on the phone home screen.
- **Timezone**: majalis times are shown in it (default `Asia/Baghdad`).
- **Default City**: for prayer times until the visitor picks one.
- **Hijri Date Adjustment**: -2..+2 days, to follow the local moon sighting.
- **Auto-publish majalis of verified pages**.

## Notes

- The library ships with three short starter texts only. Enter the full texts
  from a verified source.
- Hijri occasions are editable data; adjust them to the dates you follow.
- Prayer times are astronomical calculations and can differ by a minute or two
  from a local timetable.
- The PWA needs HTTPS to install and to work offline (Odoo.sh provides it;
  `localhost` is also accepted by browsers).
- Sample pages and majalis are loaded only on databases with demo data.

## Tests

```bash
odoo-bin -d <db> -i ib4tech_minbar --test-tags /ib4tech_minbar --stop-after-init
```

Fonts: Tajawal and Amiri, SIL Open Font License (see `static/src/app/fonts`).
