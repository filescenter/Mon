/* IB4Tech Al-Siddiqa: behaviour of the public mobile app (no framework, no build step). */
(function () {
    "use strict";

    var data = {};
    try {
        data = JSON.parse(document.body.dataset.app || "{}");
    } catch (error) {
        data = {};
    }
    var page = document.body.dataset.page || "";

    function $(selector, root) {
        return (root || document).querySelector(selector);
    }
    function $$(selector, root) {
        return Array.prototype.slice.call((root || document).querySelectorAll(selector));
    }
    function setText(selector, text) {
        $$(selector).forEach(function (node) {
            node.textContent = text;
        });
    }

    // Everything personal (city, favourites, counters) stays on the device.
    var store = {
        get: function (key, fallback) {
            try {
                var raw = localStorage.getItem("minbar." + key);
                return raw === null ? fallback : JSON.parse(raw);
            } catch (error) {
                return fallback;
            }
        },
        set: function (key, value) {
            try {
                localStorage.setItem("minbar." + key, JSON.stringify(value));
            } catch (error) {
                /* private mode or full storage: the app keeps working without it */
            }
        },
    };

    var toastTimer = null;
    function toast(message) {
        var node = $("#mb-toast");
        if (!node) {
            return;
        }
        node.textContent = message;
        node.classList.add("is-on");
        clearTimeout(toastTimer);
        toastTimer = setTimeout(function () {
            node.classList.remove("is-on");
        }, 2600);
    }

    // ------------------------------------------------------------------
    // Dates
    // ------------------------------------------------------------------
    var HIJRI_MONTHS = [
        "محرم", "صفر", "ربيع الأول", "ربيع الآخر", "جمادى الأولى", "جمادى الآخرة",
        "رجب", "شعبان", "شهر رمضان", "شوال", "ذو القعدة", "ذو الحجة",
    ];
    var WEEKDAYS = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"];
    var MONTHS = [
        "كانون الثاني", "شباط", "آذار", "نيسان", "أيار", "حزيران",
        "تموز", "آب", "أيلول", "تشرين الأول", "تشرين الثاني", "كانون الأول",
    ];
    var OCCASION_TYPES = { wiladah: "ولادة", shahadah: "شهادة", eid: "عيد", other: "مناسبة" };

    var hijriFormatter = null;
    try {
        hijriFormatter = new Intl.DateTimeFormat("en-u-ca-islamic-umalqura-nu-latn", {
            day: "numeric", month: "numeric", year: "numeric", timeZone: "UTC",
        });
        if (hijriFormatter.resolvedOptions().calendar.indexOf("islamic") !== 0) {
            hijriFormatter = null;
        }
    } catch (error) {
        hijriFormatter = null;
    }

    // Arithmetic (tabular) calendar, used only where the browser has no hijri calendar.
    function tabularHijri(utcNoon) {
        var jdn = Math.floor(utcNoon.getTime() / 86400000 + 2440587.5);
        var l = jdn - 1948440 + 10632;
        var n = Math.floor((l - 1) / 10631);
        l = l - 10631 * n + 354;
        var j = Math.floor((10985 - l) / 5316) * Math.floor((50 * l) / 17719)
            + Math.floor(l / 5670) * Math.floor((43 * l) / 15238);
        l = l - Math.floor((30 - j) / 15) * Math.floor((17719 * j) / 50)
            - Math.floor(j / 16) * Math.floor((15238 * j) / 43) + 29;
        var month = Math.floor((24 * l) / 709);
        return { day: l - Math.floor((709 * month) / 24), month: month, year: 30 * n + j - 30 };
    }

    /** Hijri date of a calendar day, shifted by the adjustment set by the administration. */
    function hijri(date) {
        var utcNoon = new Date(Date.UTC(
            date.getFullYear(), date.getMonth(), date.getDate() + (data.hijriOffset || 0), 12));
        if (!hijriFormatter) {
            return tabularHijri(utcNoon);
        }
        var result = {};
        hijriFormatter.formatToParts(utcNoon).forEach(function (part) {
            if (part.type === "day" || part.type === "month" || part.type === "year") {
                result[part.type] = parseInt(part.value, 10);
            }
        });
        return result;
    }
    function hijriLabel(date) {
        var h = hijri(date);
        return h.day + " " + HIJRI_MONTHS[h.month - 1] + " " + h.year + " هـ";
    }
    function gregorianLabel(date) {
        return WEEKDAYS[date.getDay()] + " " + date.getDate() + " " + MONTHS[date.getMonth()]
            + " " + date.getFullYear();
    }
    function occasionsOn(date) {
        var h = hijri(date);
        return (data.occasions || []).filter(function (occasion) {
            return occasion.m === h.month && occasion.d === h.day;
        });
    }

    function initDates() {
        var today = new Date();
        setText('[data-hijri="full"]', hijriLabel(today));
        setText('[data-gregorian="full"]', gregorianLabel(today));
        var todays = occasionsOn(today);
        // Muharram, Safar and martyrdom anniversaries: the app dresses in black.
        var month = hijri(today).month;
        var isMourning = month === 1 || month === 2
            || todays.some(function (o) { return o.t === "shahadah"; });
        if (data.mourningTheme && isMourning) {
            document.documentElement.dataset.mood = "mourning";
            $$('meta[name="theme-color"]').forEach(function (meta) {
                meta.setAttribute("content", "#0a0a0b");
            });
        }
        $$("[data-occasion-today]").forEach(function (node) {
            if (todays.length) {
                node.textContent = todays.map(function (o) { return o.name; }).join(" · ");
                node.hidden = false;
            }
        });
        $$("[data-hijri-of]").forEach(function (node) {
            var parts = (node.dataset.date || "").split("-");
            if (parts.length === 3) {
                node.textContent = hijriLabel(new Date(+parts[0], parts[1] - 1, +parts[2]));
            }
        });
    }

    function initOccasions() {
        var list = $("#mb-occasions");
        if (!list) {
            return;
        }
        var today = new Date();
        var rows = [];
        for (var offset = 0; offset < 355 && rows.length < 40; offset++) {
            var day = new Date(today.getFullYear(), today.getMonth(), today.getDate() + offset);
            var h = hijri(day);
            occasionsOn(day).forEach(function (occasion) {
                rows.push({ occasion: occasion, day: day, hijri: h, offset: offset });
            });
        }
        if (!rows.length) {
            list.outerHTML = '<p class="mb-note">لا توجد مناسبات مسجلة.</p>';
            return;
        }
        rows.forEach(function (row) {
            var item = document.createElement("div");
            item.className = "mb-row mb-row--static";
            var when = row.offset === 0 ? "اليوم" : row.offset === 1 ? "غداً" : "بعد " + row.offset + " يوماً";
            var body = document.createElement("span");
            body.className = "mb-row__body";
            var title = document.createElement("span");
            title.className = "mb-row__title";
            title.textContent = row.occasion.name;
            var meta = document.createElement("span");
            meta.className = "mb-row__meta";
            meta.textContent = row.hijri.day + " " + HIJRI_MONTHS[row.hijri.month - 1] + " · "
                + gregorianLabel(row.day);
            var tags = document.createElement("span");
            tags.className = "mb-majlis__tags";
            [OCCASION_TYPES[row.occasion.t] || OCCASION_TYPES.other, when].forEach(function (label) {
                var tag = document.createElement("span");
                tag.className = "mb-tag";
                tag.textContent = label;
                tags.appendChild(tag);
            });
            body.appendChild(title);
            body.appendChild(meta);
            body.appendChild(tags);
            item.appendChild(body);
            list.appendChild(item);
        });
    }

    // ------------------------------------------------------------------
    // Place (city picked by the visitor, or the position of the device)
    // ------------------------------------------------------------------
    function currentPlace() {
        var saved = store.get("place", null);
        if (saved && saved.gps && isFinite(saved.lat) && isFinite(saved.lng)) {
            return { id: "gps", name: "موقعي الحالي", lat: saved.lat, lng: saved.lng, tz: null };
        }
        var cities = data.cities || [];
        var wanted = saved && saved.cityId ? saved.cityId : data.defaultCityId;
        var city = cities.filter(function (c) { return c.id === wanted; })[0] || cities[0];
        return city || null;
    }

    /** Hours between UTC and the wall clock of ``tz`` (or of the device when there is none). */
    function tzOffsetHours(tz, date) {
        if (!tz) {
            return -date.getTimezoneOffset() / 60;
        }
        try {
            var parts = {};
            new Intl.DateTimeFormat("en-US", {
                timeZone: tz, hourCycle: "h23",
                year: "numeric", month: "numeric", day: "numeric", hour: "numeric", minute: "numeric",
            }).formatToParts(date).forEach(function (part) {
                parts[part.type] = parseInt(part.value, 10);
            });
            var wall = Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute);
            return Math.round((wall - Math.floor(date.getTime() / 60000) * 60000) / 60000) / 60;
        } catch (error) {
            return 3;
        }
    }

    /** The server reads this cookie to show the majalis of the visitor's city first. */
    function rememberCity(value) {
        document.cookie = "minbar_city=" + value + "; path=/app; max-age=31536000; samesite=lax";
    }

    function locate(done) {
        if (!navigator.geolocation) {
            toast("هذا المتصفح لا يدعم تحديد الموقع.");
            return;
        }
        navigator.geolocation.getCurrentPosition(function (position) {
            store.set("place", {
                gps: true, lat: position.coords.latitude, lng: position.coords.longitude,
            });
            rememberCity("gps");
            done();
        }, function () {
            toast("تعذر تحديد الموقع. اختر مدينتك من القائمة.");
        }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 });
    }

    function initPlacePicker(onChange) {
        var select = $("[data-city-select]");
        if (select) {
            var place = currentPlace();
            if (place) {
                select.value = String(place.id);
            }
            select.addEventListener("change", function () {
                if (select.value === "gps") {
                    locate(onChange);
                } else {
                    store.set("place", { cityId: parseInt(select.value, 10) });
                    rememberCity(select.value);
                    onChange();
                }
            });
        }
        var button = $("[data-locate]");
        if (button) {
            button.addEventListener("click", function () {
                locate(function () {
                    if (select) {
                        select.value = "gps";
                    }
                    onChange();
                });
            });
        }
    }

    function initCitySheet() {
        var sheet = $("#mb-city-sheet");
        var place = currentPlace();
        if (place) {
            setText("[data-city-name]", place.name);
        }
        if (!sheet || typeof sheet.showModal !== "function") {
            return;
        }
        $$("[data-city-open]").forEach(function (button) {
            button.addEventListener("click", function () {
                var current = currentPlace();
                $$("[data-city-pick]", sheet).forEach(function (option) {
                    option.setAttribute("aria-pressed",
                        String(Boolean(current) && String(current.id) === option.dataset.cityPick));
                });
                sheet.showModal();
            });
        });
        $$("[data-sheet-close]", sheet).forEach(function (button) {
            button.addEventListener("click", function () { sheet.close(); });
        });
        sheet.addEventListener("click", function (event) {
            if (event.target === sheet) {
                sheet.close();
            }
        });
        // The page is loaded again so that the majalis follow the new city.
        $$("[data-city-pick]", sheet).forEach(function (option) {
            option.addEventListener("click", function () {
                if (option.dataset.cityPick === "gps") {
                    locate(function () { location.reload(); });
                } else {
                    store.set("place", { cityId: parseInt(option.dataset.cityPick, 10) });
                    rememberCity(option.dataset.cityPick);
                    location.reload();
                }
            });
        });
    }

    // ------------------------------------------------------------------
    // Prayer times: standard solar position formulas, Jafari (Leva, Qom) angles
    // ------------------------------------------------------------------
    var RAD = Math.PI / 180;
    function sin(d) { return Math.sin(d * RAD); }
    function cos(d) { return Math.cos(d * RAD); }
    function tan(d) { return Math.tan(d * RAD); }
    function fix(value, range) {
        value = value - range * Math.floor(value / range);
        return value < 0 ? value + range : value;
    }

    function julian(year, month, day) {
        if (month <= 2) {
            year -= 1;
            month += 12;
        }
        var a = Math.floor(year / 100);
        var b = 2 - a + Math.floor(a / 4);
        return Math.floor(365.25 * (year + 4716)) + Math.floor(30.6001 * (month + 1)) + day + b - 1524.5;
    }

    function sunPosition(jd) {
        var d = jd - 2451545.0;
        var g = fix(357.529 + 0.98560028 * d, 360);
        var q = fix(280.459 + 0.98564736 * d, 360);
        var l = fix(q + 1.915 * sin(g) + 0.020 * sin(2 * g), 360);
        var e = 23.439 - 0.00000036 * d;
        var ra = Math.atan2(cos(e) * sin(l), cos(l)) / RAD / 15;
        return {
            declination: Math.asin(sin(e) * sin(l)) / RAD,
            equation: q / 15 - fix(ra, 24),
        };
    }

    var FAJR_ANGLE = 16;
    var MAGHRIB_ANGLE = 4;
    var HORIZON_ANGLE = 0.833;
    var IMSAK_MINUTES = 10;

    /** Times of one calendar day as decimal hours on the wall clock of the place. */
    function prayerTimes(date, lat, lng, tzHours) {
        var jd = julian(date.getFullYear(), date.getMonth() + 1, date.getDate()) - lng / (15 * 24);

        function midDay(portion) {
            return fix(12 - sunPosition(jd + portion).equation, 24);
        }
        function angleTime(angle, portion, beforeNoon) {
            var declination = sunPosition(jd + portion).declination;
            var cosine = (-sin(angle) - sin(declination) * sin(lat)) / (cos(declination) * cos(lat));
            var span = Math.acos(cosine) / RAD / 15;
            return midDay(portion) + (beforeNoon ? -span : span);
        }

        var times = { fajr: 5, sunrise: 6, dhuhr: 12, sunset: 18, maghrib: 18 };
        for (var pass = 0; pass < 2; pass++) {
            times = {
                fajr: angleTime(FAJR_ANGLE, times.fajr / 24, true),
                sunrise: angleTime(HORIZON_ANGLE, times.sunrise / 24, true),
                dhuhr: midDay(times.dhuhr / 24),
                sunset: angleTime(HORIZON_ANGLE, times.sunset / 24, false),
                maghrib: angleTime(MAGHRIB_ANGLE, times.maghrib / 24, false),
            };
        }
        Object.keys(times).forEach(function (key) {
            times[key] += tzHours - lng / 15;
        });
        times.imsak = times.fajr - IMSAK_MINUTES / 60;
        // Shari midnight: half way between sunset and the following fajr.
        times.midnight = times.sunset + fix(times.fajr - times.sunset, 24) / 2;
        return times;
    }

    function formatClock(hours) {
        if (!isFinite(hours)) {
            return "--:--";
        }
        var minutes = Math.round(fix(hours, 24) * 60) % 1440;
        var h = Math.floor(minutes / 60);
        var m = minutes % 60;
        return (h % 12 || 12) + ":" + (m < 10 ? "0" : "") + m + " " + (h < 12 ? "ص" : "م");
    }

    var PRAYERS = [["fajr", "الفجر"], ["dhuhr", "الظهر"], ["maghrib", "المغرب"]];

    function nextPrayer(place) {
        var now = new Date();
        var offset = tzOffsetHours(place.tz, now);
        // "Now" expressed as a calendar day and decimal hour at the place.
        var local = new Date(now.getTime() + offset * 3600000);
        var day = new Date(local.getUTCFullYear(), local.getUTCMonth(), local.getUTCDate());
        var hour = local.getUTCHours() + local.getUTCMinutes() / 60 + local.getUTCSeconds() / 3600;
        var today = prayerTimes(day, place.lat, place.lng, offset);
        for (var i = 0; i < PRAYERS.length; i++) {
            if (today[PRAYERS[i][0]] > hour) {
                return { key: PRAYERS[i][0], name: PRAYERS[i][1], at: today[PRAYERS[i][0]], left: today[PRAYERS[i][0]] - hour };
            }
        }
        var tomorrow = prayerTimes(
            new Date(day.getFullYear(), day.getMonth(), day.getDate() + 1), place.lat, place.lng, offset);
        return { key: "fajr", name: "الفجر", at: tomorrow.fajr, left: tomorrow.fajr + 24 - hour };
    }

    function renderNextPrayer() {
        var place = currentPlace();
        if (!place) {
            return null;
        }
        var next = nextPrayer(place);
        var minutes = Math.max(Math.round(next.left * 60), 0);
        var left = minutes >= 60
            ? "بعد " + Math.floor(minutes / 60) + " س " + (minutes % 60) + " د"
            : "بعد " + minutes + " دقيقة";
        setText('[data-next-prayer="name"]', next.name);
        setText('[data-next-prayer="time"]', formatClock(next.at));
        setText('[data-next-prayer="left"]', left);
        setText("[data-city-name]", place.name);
        return next;
    }

    function initPrayer() {
        if (!$("[data-next-prayer]")) {
            return;
        }
        var dayOffset = 0;

        function render() {
            var next = renderNextPrayer();
            var table = $("#mb-times");
            var place = currentPlace();
            if (!table || !place) {
                return;
            }
            var now = new Date();
            var offset = tzOffsetHours(place.tz, now);
            var local = new Date(now.getTime() + offset * 3600000);
            var day = new Date(local.getUTCFullYear(), local.getUTCMonth(), local.getUTCDate() + dayOffset);
            var times = prayerTimes(day, place.lat, place.lng, offset);
            $$("tr[data-prayer]", table).forEach(function (row) {
                var key = row.dataset.prayer;
                row.lastElementChild.textContent = formatClock(times[key]);
                row.classList.toggle("is-next", dayOffset === 0 && next && next.key === key);
            });
            setText("[data-prayer-date]", dayOffset === 0 ? "اليوم" : gregorianLabel(day));
        }

        $$("[data-prayer-day]").forEach(function (button) {
            button.addEventListener("click", function () {
                dayOffset += parseInt(button.dataset.prayerDay, 10);
                render();
            });
        });
        initPlacePicker(render);
        render();
        setInterval(render, 30000);
    }

    // ------------------------------------------------------------------
    // Qibla
    // ------------------------------------------------------------------
    var KAABA = { lat: 21.4225, lng: 39.8262 };

    function qiblaBearing(lat, lng) {
        var delta = KAABA.lng - lng;
        var angle = Math.atan2(sin(delta), cos(lat) * tan(KAABA.lat) - sin(lat) * cos(delta)) / RAD;
        return fix(angle, 360);
    }

    function initQibla() {
        var dial = $("[data-compass-dial]");
        if (!dial) {
            return;
        }
        var needle = $("[data-compass-needle]");
        var status = $("[data-compass-status]");

        function render() {
            var place = currentPlace();
            if (!place) {
                return;
            }
            var bearing = qiblaBearing(place.lat, place.lng);
            needle.style.transform = "rotate(" + bearing + "deg)";
            setText("[data-qibla-angle]", String(Math.round(bearing)));
            setText("[data-qibla-city]", place.name);
        }

        function onOrientation(event) {
            var heading = null;
            if (typeof event.webkitCompassHeading === "number") {
                heading = event.webkitCompassHeading;
            } else if (event.absolute && typeof event.alpha === "number") {
                heading = 360 - event.alpha;
            }
            if (heading === null) {
                return;
            }
            dial.style.transform = "rotate(" + (-heading) + "deg)";
            status.textContent = "البوصلة تعمل. أبعد الهاتف عن المعادن وحرّكه على شكل رقم 8 إن بدا الاتجاه غير ثابت.";
        }

        function start() {
            if (!("DeviceOrientationEvent" in window)) {
                status.textContent = "هذا الجهاز لا يحتوي على بوصلة. وجّه أعلى الهاتف نحو الشمال ليشير السهم إلى القبلة.";
                return;
            }
            var listen = function () {
                window.addEventListener("deviceorientationabsolute", onOrientation, true);
                window.addEventListener("deviceorientation", onOrientation, true);
            };
            if (typeof DeviceOrientationEvent.requestPermission === "function") {
                DeviceOrientationEvent.requestPermission().then(function (answer) {
                    if (answer === "granted") {
                        listen();
                    } else {
                        status.textContent = "لم يُسمح باستخدام البوصلة. فعّلها من إعدادات المتصفح ثم أعد المحاولة.";
                    }
                }).catch(function () {
                    status.textContent = "تعذر تشغيل البوصلة على هذا الجهاز.";
                });
            } else {
                listen();
            }
        }

        var button = $("[data-compass-start]");
        if (button) {
            button.addEventListener("click", start);
        }
        initPlacePicker(render);
        render();
    }

    // ------------------------------------------------------------------
    // Tasbih counter
    // ------------------------------------------------------------------
    var PRESETS = {
        zahra: [
            { phrase: "الله أكبر", goal: 34 },
            { phrase: "الحمد لله", goal: 33 },
            { phrase: "سبحان الله", goal: 33 },
        ],
        salawat: [{ phrase: "اللهم صلِّ على محمد وآل محمد", goal: 100 }],
        istighfar: [{ phrase: "أستغفر الله ربي وأتوب إليه", goal: 100 }],
        free: [{ phrase: "عدّاد حر", goal: 0 }],
    };

    function initTasbih() {
        var counter = $("#mb-counter");
        if (!counter) {
            return;
        }
        var todayKey = new Date().toDateString();
        var state = store.get("tasbih", null) || {};
        if (!PRESETS[state.preset]) {
            state = { preset: "zahra", step: 0, count: 0 };
        }
        if (state.day !== todayKey) {
            state.day = todayKey;
            state.total = 0;
        }

        function buzz(pattern) {
            if (navigator.vibrate) {
                navigator.vibrate(pattern);
            }
        }
        function render() {
            var step = PRESETS[state.preset][state.step];
            setText('[data-tasbih="phrase"]', step.phrase);
            setText('[data-tasbih="count"]', String(state.count));
            setText('[data-tasbih="goal"]', step.goal ? "من " + step.goal : "بلا حد");
            setText('[data-tasbih="total"]', String(state.total || 0));
            $$("[data-tasbih-preset]").forEach(function (button) {
                button.setAttribute("aria-pressed", String(button.dataset.tasbihPreset === state.preset));
            });
            store.set("tasbih", state);
        }

        counter.addEventListener("click", function () {
            var steps = PRESETS[state.preset];
            var step = steps[state.step];
            state.count += 1;
            state.total = (state.total || 0) + 1;
            if (step.goal && state.count >= step.goal) {
                buzz([60, 40, 60]);
                var isLast = state.step === steps.length - 1;
                toast(isLast ? "تمّ، تقبّل الله أعمالكم" : "انتقل إلى: " + steps[state.step + 1].phrase);
                state.step = isLast ? 0 : state.step + 1;
                state.count = 0;
            } else {
                buzz(12);
            }
            render();
        });
        $$("[data-tasbih-preset]").forEach(function (button) {
            button.addEventListener("click", function () {
                state.preset = button.dataset.tasbihPreset;
                state.step = 0;
                state.count = 0;
                render();
            });
        });
        var reset = $("[data-tasbih-reset]");
        if (reset) {
            reset.addEventListener("click", function () {
                state.step = 0;
                state.count = 0;
                render();
            });
        }
        render();
    }

    // ------------------------------------------------------------------
    // Favourites (kept on the device, no account needed)
    // ------------------------------------------------------------------
    var FAV_LABELS = {
        entity: { on: "تتابعها", off: "متابعة", added: "أُضيفت إلى المفضلة", removed: "أُزيلت من المفضلة" },
        majlis: { on: "محفوظ", off: "حفظ", added: "حُفظ المجلس في المفضلة", removed: "أُزيل المجلس من المفضلة" },
    };

    function favorites(kind) {
        var list = store.get("fav." + kind, []);
        return Array.isArray(list) ? list : [];
    }

    function initFavorites() {
        $$("[data-fav]").forEach(function (button) {
            var kind = button.dataset.fav;
            var id = parseInt(button.dataset.id, 10);
            var labels = FAV_LABELS[kind];
            var label = $("[data-fav-label]", button);

            function render() {
                var isOn = favorites(kind).indexOf(id) !== -1;
                button.setAttribute("aria-pressed", String(isOn));
                if (label) {
                    label.textContent = isOn ? labels.on : labels.off;
                }
            }
            button.addEventListener("click", function () {
                var list = favorites(kind);
                var index = list.indexOf(id);
                if (index === -1) {
                    list.push(id);
                } else {
                    list.splice(index, 1);
                }
                store.set("fav." + kind, list.slice(-200));
                toast(index === -1 ? labels.added : labels.removed);
                render();
            });
            render();
        });

        var box = $("#mb-favorites");
        if (!box) {
            return;
        }
        var empty = $("#mb-favorites-empty");
        var entities = favorites("entity");
        var majalis = favorites("majlis");
        function showEmpty() {
            box.innerHTML = empty.innerHTML;
        }
        if (!entities.length && !majalis.length) {
            showEmpty();
            return;
        }
        fetch("/app/favorites/cards?e=" + entities.join(",") + "&m=" + majalis.join(","))
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("favorites");
                }
                return response.text();
            })
            .then(function (html) {
                if (html.trim()) {
                    box.innerHTML = html;
                } else {
                    showEmpty();
                }
            })
            .catch(function () {
                box.innerHTML = '<p class="mb-alert">تعذر تحميل المفضلة. تحقق من الاتصال ثم أعد المحاولة.</p>';
            });
    }

    // ------------------------------------------------------------------
    // Small interactions
    // ------------------------------------------------------------------
    function initShare() {
        $$("[data-share]").forEach(function (button) {
            button.addEventListener("click", function () {
                var url = button.dataset.url || location.href;
                var title = button.dataset.title || document.title;
                if (navigator.share) {
                    navigator.share({ title: title, url: url }).catch(function () {});
                } else if (navigator.clipboard) {
                    navigator.clipboard.writeText(url).then(function () {
                        toast("تم نسخ الرابط");
                    });
                } else {
                    window.prompt("انسخ الرابط", url);
                }
            });
        });
    }

    function initForms() {
        $$("form[data-autosubmit]").forEach(function (form) {
            form.addEventListener("change", function (event) {
                if (event.target.matches("select, input[type=radio]")) {
                    form.submit();
                }
            });
        });
        $$("form[data-confirm]").forEach(function (form) {
            form.addEventListener("submit", function (event) {
                if (!window.confirm(form.dataset.confirm)) {
                    event.preventDefault();
                }
            });
        });
    }

    function initBack() {
        var link = $("[data-back]");
        if (!link) {
            return;
        }
        link.addEventListener("click", function (event) {
            var fromApp = document.referrer.indexOf(location.origin + "/app") === 0;
            if (fromApp && history.length > 1) {
                event.preventDefault();
                history.back();
            }
        });
    }

    function initReader() {
        var reader = $(".mb-reader");
        if (!reader) {
            return;
        }
        var size = Number(store.get("reader.size", 1.5)) || 1.5;
        function apply() {
            reader.style.setProperty("--reader-size", size + "rem");
        }
        $$("[data-font]").forEach(function (button) {
            button.addEventListener("click", function () {
                size = Math.min(2.7, Math.max(1.05, size + 0.15 * parseInt(button.dataset.font, 10)));
                store.set("reader.size", size);
                apply();
            });
        });
        apply();
        // Keep the screen on while reciting, where the browser allows it.
        if (navigator.wakeLock) {
            var lock = function () {
                navigator.wakeLock.request("screen").catch(function () {});
            };
            lock();
            document.addEventListener("visibilitychange", function () {
                if (document.visibilityState === "visible") {
                    lock();
                }
            });
        }
    }

    // ------------------------------------------------------------------
    // Installable app and offline reading
    // ------------------------------------------------------------------
    var PAGE_CACHE = "minbar-pages";

    function initInstall() {
        var banner = $("#mb-install");
        var standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone;
        if (!banner || standalone) {
            return;
        }
        var inline = banner.classList.contains("mb-install--inline");
        if (!inline && store.get("install.dismissed", false)) {
            return;
        }
        var button = $("[data-install]", banner);
        var deferred = null;
        window.addEventListener("beforeinstallprompt", function (event) {
            event.preventDefault();
            deferred = event;
            banner.hidden = false;
        });
        button.addEventListener("click", function () {
            if (!deferred) {
                return;
            }
            deferred.prompt();
            deferred.userChoice.then(function () {
                deferred = null;
                banner.hidden = true;
            });
        });
        var close = $("[data-install-dismiss]", banner);
        if (close) {
            close.addEventListener("click", function () {
                store.set("install.dismissed", true);
                banner.hidden = true;
            });
        }
        // Safari on iOS has no install prompt: explain the manual steps instead.
        var isIos = /iphone|ipad|ipod/i.test(navigator.userAgent);
        if (isIos) {
            banner.querySelector("span").textContent =
                "لتثبيت التطبيق: اضغط زر المشاركة ثم «إضافة إلى الشاشة الرئيسية».";
            button.hidden = true;
            banner.hidden = false;
        }
    }

    function initOffline() {
        var box = $("#mb-offline-box");
        if (!box || !("caches" in window) || !("serviceWorker" in navigator)) {
            return;
        }
        var status = $("[data-offline-status]", box);
        var button = $("[data-offline-save]", box);
        var saved = store.get("offline.saved", null);
        if (saved) {
            status.textContent = "محفوظة على هذا الهاتف (" + saved.count + " صفحة). اضغط للتحديث.";
            button.textContent = "تحديث";
        }
        box.hidden = false;
        button.addEventListener("click", function () {
            button.disabled = true;
            status.textContent = "جارٍ الحفظ…";
            fetch("/app/offline/urls")
                .then(function (response) { return response.json(); })
                .then(function (urls) {
                    return caches.open(PAGE_CACHE).then(function (cache) {
                        var done = 0;
                        // One request at a time: gentle on slow connections and on the server.
                        return urls.reduce(function (chain, url) {
                            return chain.then(function () {
                                return fetch(url).then(function (response) {
                                    if (response.ok) {
                                        done += 1;
                                        status.textContent = "جارٍ الحفظ… " + done + " من " + urls.length;
                                        return cache.put(url, response);
                                    }
                                });
                            });
                        }, Promise.resolve()).then(function () { return done; });
                    });
                })
                .then(function (count) {
                    store.set("offline.saved", { count: count, at: Date.now() });
                    status.textContent = "تم الحفظ: " + count + " صفحة متاحة بدون إنترنت.";
                    button.textContent = "تحديث";
                })
                .catch(function () {
                    status.textContent = "تعذر الحفظ. تحقق من الاتصال ثم أعد المحاولة.";
                })
                .then(function () {
                    button.disabled = false;
                });
        });
    }

    // Announcement posters over the home page, one after another: each shows a countdown
    // first, then its close button.
    var MAX_ADS_PER_VISIT = 3;

    function initAd() {
        var dialog = $("#mb-ad");
        if (!dialog || typeof dialog.showModal !== "function") {
            return;
        }
        var ads = [];
        try {
            ads = JSON.parse(dialog.dataset.ads || "[]");
        } catch (error) {
            ads = [];
        }
        var today = new Date().toDateString();
        function sessionSeen(id) {
            try {
                return sessionStorage.getItem("minbar.ad." + id) === "1";
            } catch (error) {
                return false;
            }
        }
        var queue = ads.filter(function (item) {
            if (sessionSeen(item.id)) {
                return false;
            }
            var seen = store.get("ad." + item.id, null);
            if (item.frequency === "once") {
                return !seen;
            }
            if (item.frequency === "daily") {
                return seen !== today;
            }
            return true;
        }).slice(0, MAX_ADS_PER_VISIT);
        if (!queue.length) {
            return;
        }
        var image = $("[data-ad-image]", dialog);
        var link = $("[data-ad-link]", dialog);
        var close = $("[data-ad-close]", dialog);
        var count = $("[data-ad-count]", dialog);
        var ad = null;
        var left = 0;
        var timer = null;

        function hit(kind) {
            var url = "/app/ad/" + ad.id + "/hit?kind=" + kind;
            if (navigator.sendBeacon) {
                navigator.sendBeacon(url);
            } else {
                fetch(url, { method: "POST", keepalive: true }).catch(function () {});
            }
        }
        function unlock() {
            clearInterval(timer);
            left = 0;
            close.disabled = false;
            count.textContent = "×";
        }
        function tick() {
            if (left <= 0) {
                unlock();
            } else {
                count.textContent = String(left);
                left -= 1;
            }
        }
        function open() {
            try {
                sessionStorage.setItem("minbar.ad." + ad.id, "1");
            } catch (error) {
                /* no session storage: the announcement may show again */
            }
            store.set("ad." + ad.id, today);
            dialog.showModal();
            hit("view");
            tick();
            timer = setInterval(tick, 1000);
        }
        // Prepares the next poster; it opens once its picture is ready.
        function next() {
            ad = queue.shift();
            if (!ad) {
                return;
            }
            left = Math.max(parseInt(ad.seconds, 10) || 0, 0);
            close.disabled = true;
            count.textContent = String(left);
            image.alt = ad.title || "إعلان";
            link.removeAttribute("href");
            link.removeAttribute("target");
            link.removeAttribute("rel");
            if (ad.url) {
                link.href = ad.url;
                if (/^https?:/i.test(ad.url)) {
                    link.target = "_blank";
                    link.rel = "noopener noreferrer";
                }
            }
            image.src = ad.image;
        }

        link.addEventListener("click", function () {
            if (ad && ad.url) {
                hit("click");
            }
        });
        close.addEventListener("click", function () { dialog.close(); });
        // Escape and taps outside the poster only work once the countdown is over.
        dialog.addEventListener("cancel", function (event) {
            if (close.disabled) {
                event.preventDefault();
            }
        });
        dialog.addEventListener("click", function (event) {
            if (event.target === dialog && !close.disabled) {
                dialog.close();
            }
        });
        dialog.addEventListener("close", function () {
            clearInterval(timer);
            next();
        });
        image.addEventListener("load", function () { setTimeout(open, 500); });
        next();
    }

    function initServiceWorker() {
        if (!("serviceWorker" in navigator) || location.protocol === "file:") {
            return;
        }
        window.addEventListener("load", function () {
            navigator.serviceWorker.register("/app/sw.js", { scope: "/app" }).catch(function () {});
        });
    }

    // Exposed for automated checks of the astronomical helpers.
    window.MinbarApp = {
        hijri: hijri, prayerTimes: prayerTimes, qiblaBearing: qiblaBearing, formatClock: formatClock,
    };

    initDates();
    initCitySheet();
    initPrayer();
    initQibla();
    initTasbih();
    initFavorites();
    initOccasions();
    initShare();
    initForms();
    initBack();
    initReader();
    initInstall();
    initAd();
    initOffline();
    initServiceWorker();
    void page;
}());
