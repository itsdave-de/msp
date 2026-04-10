import csv
import io
import re
import urllib.request
import urllib.parse
from datetime import datetime

import frappe
from frappe.model.document import Document


class ITDomain(Document):
    def validate(self):
        self.domain = self.domain.strip().lower()
        if self.domain.startswith("http://") or self.domain.startswith("https://"):
            frappe.throw("Domain darf kein Protokoll-Prefix enthalten (http:// oder https://)")


@frappe.whitelist()
def import_hetzner_csv(file_content):
    """Import domains from Hetzner Registration Robot CSV export.

    Idempotent: existing domains are updated, new ones created.
    Returns summary dict with created/updated/skipped counts.
    """
    reader = csv.DictReader(
        io.StringIO(file_content),
        delimiter=";",
        quotechar='"',
    )

    created = 0
    updated = 0
    skipped = 0
    errors = []

    for row in reader:
        domain = row.get("Domain", "").strip().lower()
        if not domain:
            skipped += 1
            continue

        try:
            # Parse Hetzner date format DD.MM.YY -> Date
            registration_date = _parse_hetzner_date(row.get("Erstellt", ""))
            expiry_date = _parse_hetzner_date(row.get("abgerechnet bis", ""))
            cancellation = row.get("Kündigung", "").strip()

            # Collect nameservers
            nameservers = []
            for i in range(1, 6):
                ns = row.get(f"{i}. Nameserver", "").strip()
                if ns:
                    nameservers.append(ns)

            # Determine DNS provider from nameservers
            dns_provider = _detect_dns_provider(nameservers)

            # Extract handles
            handle_holder = row.get("Handle Holder", "").strip()
            handle_admin_c = (
                row.get("Handle Admin-c", "").strip()
                or row.get("Handle General-c", "").strip()
            )
            handle_tech_c = (
                row.get("Handle Tech-c", "").strip()
                or row.get("Handle Abuse-c", "").strip()
            )
            handle_zone_c = row.get("Handle Zone-c", "").strip()

            ns_text = "\n".join(nameservers)
            field_map = {
                "registrar": "Hetzner",
                "registration_date": registration_date,
                "expiry_date": expiry_date,
                "dns_provider": dns_provider,
                "dns_hosting": _classify_dns(ns_text),
                "auto_renew": 0 if cancellation else 1,
                "nameservers": ns_text,
                "handle_holder": handle_holder,
                "handle_admin_c": handle_admin_c,
                "handle_tech_c": handle_tech_c,
                "handle_zone_c": handle_zone_c,
                "is_hosting_domain": 1 if _is_itsdave_hosted(nameservers) else 0,
            }

            if frappe.db.exists("IT Domain", domain):
                doc = frappe.get_doc("IT Domain", domain)
                changed = False

                for field, value in field_map.items():
                    if value is not None and str(doc.get(field) or "") != str(value):
                        doc.set(field, value)
                        changed = True

                if changed:
                    doc.flags.ignore_permissions = True
                    doc.save()
                    updated += 1
                else:
                    skipped += 1
            else:
                doc = frappe.get_doc({
                    "doctype": "IT Domain",
                    "domain": domain,
                    "domain_type": "Primary",
                    **field_map,
                })
                doc.flags.ignore_permissions = True
                doc.insert()
                created += 1

        except Exception as e:
            errors.append(f"{domain}: {str(e)}")

    frappe.db.commit()

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "total": created + updated + skipped,
        "errors": errors,
    }


def _parse_hetzner_date(date_str):
    """Parse DD.MM.YY to YYYY-MM-DD string."""
    date_str = date_str.strip()
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, "%d.%m.%y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def _detect_dns_provider(nameservers):
    """Detect DNS provider from nameserver hostnames."""
    ns_str = " ".join(nameservers).lower()
    if "cloudflare" in ns_str:
        return "Cloudflare"
    elif "itsdave" in ns_str:
        return "itsdave (self-hosted)"
    elif "hetzner" in ns_str:
        return "Hetzner"
    elif "inwx" in ns_str:
        return "INWX"
    elif nameservers:
        return nameservers[0]
    return None


def _is_itsdave_hosted(nameservers):
    """Check if domain is hosted on itsdave servers."""
    return any("itsdave" in ns.lower() for ns in nameservers)


@frappe.whitelist()
def import_hetzner_handles_csv(file_content):
    """Import Hetzner handles CSV and update IT Domains with registrant data.

    Reads the handles CSV, builds a handle→registrant map, then updates all
    IT Domains that reference those handles.
    """
    reader = csv.DictReader(
        io.StringIO(file_content),
        delimiter=";",
        quotechar='"',
    )

    handle_map = {}
    for row in reader:
        handle = row.get("Handle", "").strip()
        if not handle:
            continue

        org = row.get("Organisation", "").strip()
        nachname = row.get("Nachname", "").strip()
        vorname = row.get("Vorname", "").strip()
        name = org or f"{vorname} {nachname}".strip()

        email = row.get("E-Mail", "").strip()
        # Clean mailto: URIs
        if email.startswith("mailto:"):
            email = email.split("mailto:")[1].split("?")[0]

        parts = []
        street = row.get("Straße", "").strip()
        plz = row.get("PLZ", "").strip()
        ort = row.get("Ort", "").strip()
        land = row.get("Land", "").strip()
        if street:
            parts.append(street)
        if plz or ort:
            parts.append(f"{plz} {ort}".strip())
        if land and land != "DE":
            parts.append(land)

        handle_map[handle] = {
            "name": name,
            "email": email,
            "address": "\n".join(parts),
        }

    # Update all IT Domains that have matching handle_holder
    updated = 0
    domains = frappe.get_all(
        "IT Domain",
        filters={"handle_holder": ["is", "set"]},
        fields=["name", "handle_holder"],
    )

    for dom in domains:
        registrant = handle_map.get(dom.handle_holder)
        if not registrant or not registrant["name"]:
            continue

        doc = frappe.get_doc("IT Domain", dom.name)
        changed = False
        for field, key in [
            ("registrant_name", "name"),
            ("registrant_email", "email"),
            ("registrant_address", "address"),
        ]:
            val = registrant[key]
            if val and str(doc.get(field) or "") != val:
                doc.set(field, val)
                changed = True

        if changed:
            doc.flags.ignore_permissions = True
            doc.save()
            updated += 1

    frappe.db.commit()
    return {"handles_parsed": len(handle_map), "domains_updated": updated}


@frappe.whitelist()
def enrich_domain(name):
    """Enrich a single IT Domain with DNS, HTTP, and SSL data."""
    import re
    import socket
    import ssl
    import subprocess
    import urllib.request

    doc = frappe.get_doc("IT Domain", name)
    domain = doc.domain

    # DNS A record
    try:
        out = subprocess.check_output(
            ["dig", "+short", "A", domain], timeout=5
        ).decode().strip()
        ips = [line for line in out.split("\n") if line and not line.endswith(".")]
        doc.resolved_ip = ips[0] if ips else None
    except Exception:
        doc.resolved_ip = None

    # DNS MX records
    try:
        out = subprocess.check_output(
            ["dig", "+short", "MX", domain], timeout=5
        ).decode().strip()
        doc.mx_records = out if out else None
    except Exception:
        doc.mx_records = None

    # HTTP title
    doc.website_title = None
    for scheme in ("https", "http"):
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(
                f"{scheme}://{domain}/",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            resp = urllib.request.urlopen(req, timeout=5, context=ctx)
            body = resp.read(8192).decode("utf-8", errors="ignore")
            title = re.search(
                r"<title[^>]*>(.*?)</title>", body, re.IGNORECASE | re.DOTALL
            )
            if title:
                doc.website_title = title.group(1).strip()[:140]
            break
        except Exception:
            continue

    # SSL certificate info
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=domain) as s:
            s.settimeout(5)
            s.connect((domain, 443))
            cert = s.getpeercert()
            doc.ssl_issuer = dict(x[0] for x in cert["issuer"]).get(
                "organizationName"
            )
            doc.ssl_expiry = cert.get("notAfter")
    except Exception:
        doc.ssl_issuer = None
        doc.ssl_expiry = None

    # Classify DNS hosting from nameservers
    doc.dns_hosting = _classify_dns(doc.nameservers or "")

    # Classify mail routing from MX records
    doc.mail_routing = _classify_mail(doc.mx_records or "")

    doc.last_enriched = frappe.utils.now()
    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()

    return {
        "resolved_ip": doc.resolved_ip,
        "mx_records": doc.mx_records,
        "website_title": doc.website_title,
        "ssl_issuer": doc.ssl_issuer,
        "ssl_expiry": doc.ssl_expiry,
        "dns_hosting": doc.dns_hosting,
        "mail_routing": doc.mail_routing,
    }


def _classify_dns(nameservers_text):
    ns = nameservers_text.lower()
    if "itsdave" in ns:
        return "itsdave"
    if "cloudflare" in ns:
        return "Cloudflare"
    if "hetzner" in ns:
        return "Hetzner"
    if "inwx" in ns:
        return "INWX"
    if ns.strip():
        return "Extern"
    return ""


def _classify_mail(mx_text):
    mx = mx_text.lower()
    if not mx.strip():
        return "Kein MX"
    if "hornetsecurity" in mx:
        return "Hornetsecurity"
    if "outlook.com" in mx or "microsoft" in mx:
        return "Microsoft 365"
    if "google" in mx or "googlemail" in mx or "gmail" in mx:
        return "Google"
    # Self-hosted: MX points to same or related domain
    return "Self-hosted"


@frappe.whitelist()
def enrich_all_domains():
    """Enrich all IT Domains that haven't been enriched yet (background job)."""
    domains = frappe.get_all(
        "IT Domain",
        filters={"last_enriched": ["is", "not set"]},
        pluck="name",
    )
    total = len(domains)
    for i, name in enumerate(domains):
        try:
            enrich_domain(name)
        except Exception as e:
            frappe.log_error(f"Enrich failed for {name}: {e}")
        if i % 10 == 0:
            frappe.publish_realtime(
                "enrich_progress",
                {"current": i + 1, "total": total},
            )
    return {"enriched": total}


_NOISE_WORDS = frozenset(
    "gmbh gbr ohg kg co e.k. ug ag inc ltd "
    "und and the der die das von zu".split()
)


def _significant_words(text):
    """Extract significant words (3+ chars, no legal forms) from text."""
    return {
        w for w in text.lower().split()
        if len(w) >= 3 and w not in _NOISE_WORDS
    }


def _score_match(source_text, customer_name):
    """Score how well source_text matches customer_name. Returns 0-1."""
    src = source_text.lower().strip()
    cust = customer_name.lower().strip()
    if not src or not cust:
        return 0

    # Exact containment
    if cust in src or src in cust:
        return min(len(src), len(cust)) / max(len(src), len(cust))

    # Word overlap
    src_words = _significant_words(src)
    cust_words = _significant_words(cust)
    if not cust_words:
        return 0
    overlap = src_words & cust_words
    if overlap:
        return len(overlap) / len(cust_words)
    return 0


@frappe.whitelist()
def suggest_customers():
    """Match unassigned domains to customers using all available signals.

    Priority: Handle propagation > Registrant name > Website title > Domain name.
    Returns list of suggestions sorted by confidence.
    """
    domains = frappe.get_all(
        "IT Domain",
        filters={"customer": ["is", "not set"]},
        fields=[
            "name", "domain", "website_title", "handle_holder",
            "registrant_name", "registrant_email", "registrant_address",
        ],
    )

    customers = frappe.get_all("Customer", fields=["name", "customer_name"])

    # Handle → customer from already-assigned domains
    handle_map = {}
    for row in frappe.get_all(
        "IT Domain",
        filters={"customer": ["is", "set"], "handle_holder": ["is", "set"]},
        fields=["handle_holder", "customer"],
    ):
        handle_map[row.handle_holder] = row.customer

    suggestions = []
    for dom in domains:
        suggestion = _match_domain(dom, customers, handle_map)
        if suggestion:
            suggestions.append(suggestion)

    # Sort: high first, then medium, then low
    order = {"high": 0, "medium": 1, "low": 2}
    suggestions.sort(key=lambda s: (order.get(s["confidence"], 9), s["domain"]))
    return suggestions


def _match_domain(dom, customers, handle_map):
    """Try to match a single domain against customers. Returns best match or None."""
    # 1. Handle propagation (highest confidence)
    if dom.handle_holder and dom.handle_holder in handle_map:
        return {
            "domain": dom.name,
            "suggested_customer": handle_map[dom.handle_holder],
            "match_type": "Handle",
            "confidence": "high",
            "registrant_name": dom.registrant_name,
            "registrant_address": dom.registrant_address,
        }

    # 2. Registrant name match (very reliable)
    if dom.registrant_name:
        match, score = _best_customer_match(dom.registrant_name, customers)
        if match:
            return {
                "domain": dom.name,
                "suggested_customer": match,
                "match_type": "Registrant",
                "confidence": "high" if score > 0.5 else "medium",
                "registrant_name": dom.registrant_name,
                "registrant_address": dom.registrant_address,
            }

    # 3. Website title match
    if dom.website_title:
        match, score = _best_customer_match(dom.website_title, customers)
        if match:
            return {
                "domain": dom.name,
                "suggested_customer": match,
                "match_type": "Website",
                "confidence": "high" if score > 0.6 else "medium",
                "registrant_name": dom.registrant_name,
                "registrant_address": dom.registrant_address,
            }

    # 4. Domain name match (lowest confidence)
    domain_base = dom.domain.rsplit(".", 1)[0].replace("-", " ").replace(".", " ")
    match, score = _best_customer_match(domain_base, customers)
    if match and score >= 0.3:
        return {
            "domain": dom.name,
            "suggested_customer": match,
            "match_type": "Domain",
            "confidence": "low",
            "registrant_name": dom.registrant_name,
            "registrant_address": dom.registrant_address,
        }

    # 5. No match — still return for manual assignment
    return {
        "domain": dom.name,
        "suggested_customer": None,
        "match_type": None,
        "confidence": None,
        "registrant_name": dom.registrant_name,
        "registrant_address": dom.registrant_address,
    }


def _best_customer_match(text, customers):
    """Find best matching customer for given text. Returns (customer_name, score)."""
    best_match = None
    best_score = 0
    for cust in customers:
        score = _score_match(text, cust.customer_name)
        if score > best_score:
            best_score = score
            best_match = cust.name
    return (best_match, best_score) if best_score >= 0.25 else (None, 0)


# --- DomainReselling.de API integration ---

_DR_API_URL = "https://api.domainreselling.de/api/call.cgi"


def _dr_api_call(command, login, password, **params):
    """Call DomainReselling.de API (read-only). Returns parsed response dict."""
    data = {
        "s_login": login,
        "s_pw": password,
        "command": command,
        **params,
    }
    encoded = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(_DR_API_URL, data=encoded)
    resp = urllib.request.urlopen(req, timeout=30)
    body = resp.read().decode("utf-8")

    # Parse the key-value response
    result = {"properties": {}}
    for line in body.strip().split("\n"):
        line = line.strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().lower()
        value = value.strip()

        if key == "code":
            result["code"] = int(value)
        elif key == "description":
            result["description"] = value
        elif key.startswith("property["):
            # Parse property[fieldname][index] = value
            m = re.match(r"property\[(\w+)\]\[(\d+)\]", key)
            if m:
                field, idx = m.group(1), int(m.group(2))
                result["properties"].setdefault(field, {})
                result["properties"][field][idx] = value

    if result.get("code", 0) != 200:
        frappe.throw(f"DomainReselling API Error: {result.get('description', 'Unknown')}")

    return result


@frappe.whitelist()
def import_domainreselling(login, password):
    """Import domains from DomainReselling.de API.

    Fetches all domains with details, resolves contact handles, and creates/updates
    IT Domain records. Read-only API calls only.
    """
    # Step 1: Fetch all domains
    resp = _dr_api_call("QueryDomainList", login, password, first="0", limit="500", wide="1")
    props = resp["properties"]
    total = int(props.get("total", {}).get(0, 0))

    if not total:
        return {"created": 0, "updated": 0, "skipped": 0, "total": 0, "errors": []}

    # Step 2: Collect unique contact handles
    contact_handles = set()
    for i in range(total):
        handle = props.get("domainownercontact", {}).get(i, "")
        if handle:
            contact_handles.add(handle)

    # Step 3: Resolve contact handles to names/addresses
    contact_map = {}
    for handle in contact_handles:
        try:
            c = _dr_api_call("StatusContact", login, password, contact=handle)
            cp = c["properties"]
            org = cp.get("organization", {}).get(0, "")
            name = org or cp.get("name", {}).get(0, "")
            email = cp.get("email", {}).get(0, "")
            street = cp.get("street", {}).get(0, "")
            zip_code = cp.get("zip", {}).get(0, "")
            city = cp.get("city", {}).get(0, "")

            addr_parts = []
            if street:
                addr_parts.append(street)
            if zip_code or city:
                addr_parts.append(f"{zip_code} {city}".strip())

            contact_map[handle] = {
                "name": name,
                "email": email,
                "address": "\n".join(addr_parts),
            }
        except Exception:
            contact_map[handle] = {"name": "", "email": "", "address": ""}

    # Step 4: Import domains
    created = 0
    updated = 0
    skipped = 0
    errors = []

    for i in range(total):
        domain = props.get("domain", {}).get(i, "").strip().lower()
        if not domain:
            continue

        try:
            # Parse dates (format: 2023-07-06 15:17:50)
            created_date = _parse_dr_date(props.get("domaincreateddate", {}).get(i, ""))
            expiry_date = _parse_dr_date(
                props.get("domainregistrationexpirationdate", {}).get(i, "")
            )

            # Nameservers
            ns_list = []
            for ns_idx in range(5):
                ns = props.get(f"nameserver{ns_idx}", {}).get(i, "")
                if ns:
                    ns_list.append(ns)
            ns_text = "\n".join(ns_list)

            # Contact
            owner_handle = props.get("domainownercontact", {}).get(i, "")
            admin_handle = props.get("domainadmincontact", {}).get(i, "")
            tech_handle = props.get("domaintechcontact", {}).get(i, "")
            registrant = contact_map.get(owner_handle, {})

            # Renewal mode
            renewal_mode = props.get("domainrenewalmode", {}).get(i, "")
            auto_renew = 1 if renewal_mode == "AUTORENEW" else 0

            field_map = {
                "registrar": "DomainReselling.de",
                "registration_date": created_date,
                "expiry_date": expiry_date,
                "dns_provider": _detect_dns_provider(ns_list),
                "dns_hosting": _classify_dns(ns_text),
                "auto_renew": auto_renew,
                "nameservers": ns_text,
                "handle_holder": owner_handle,
                "handle_admin_c": admin_handle,
                "handle_tech_c": tech_handle,
                "registrant_name": registrant.get("name", ""),
                "registrant_email": registrant.get("email", ""),
                "registrant_address": registrant.get("address", ""),
                "is_hosting_domain": 1 if _is_itsdave_hosted(ns_list) else 0,
            }

            if frappe.db.exists("IT Domain", domain):
                doc = frappe.get_doc("IT Domain", domain)
                changed = False
                for field, value in field_map.items():
                    if value is not None and str(doc.get(field) or "") != str(value):
                        doc.set(field, value)
                        changed = True
                if changed:
                    doc.flags.ignore_permissions = True
                    doc.save()
                    updated += 1
                else:
                    skipped += 1
            else:
                doc = frappe.get_doc({
                    "doctype": "IT Domain",
                    "domain": domain,
                    "domain_type": "Primary",
                    **field_map,
                })
                doc.flags.ignore_permissions = True
                doc.insert()
                created += 1

        except Exception as e:
            errors.append(f"{domain}: {str(e)}")

    frappe.db.commit()
    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "total": created + updated + skipped,
        "errors": errors,
    }


def _parse_dr_date(date_str):
    """Parse DomainReselling date (YYYY-MM-DD HH:MM:SS) to YYYY-MM-DD."""
    if not date_str or date_str.startswith("0000"):
        return None
    return date_str.split(" ")[0]
