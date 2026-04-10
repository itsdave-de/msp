import frappe
import zipfile
import os
import datetime
from frappe.model.document import Document
from frappe.utils import get_files_path
from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15


class SSLCertificate(Document):
    def before_save(self):
        if self.attach_zip and self.has_value_changed("attach_zip"):
            self._import_from_zip()

        if self.certificate_data:
            self._parse_certificate()

        if self.ca_chain:
            self._parse_ca()

        if self.certificate_data and self.get_password("private_key"):
            self._verify_private_key()

    def after_insert(self):
        if self.common_name and not self.certificate_name:
            self._set_auto_name()

    def _import_from_zip(self):
        zip_path = self._resolve_file_path(self.attach_zip)
        if not zip_path or not os.path.exists(zip_path):
            frappe.throw("ZIP-Datei nicht gefunden")

        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                name = info.filename
                content = zf.read(name).decode("utf-8").strip()

                if name.endswith(".crt.pem") and not name.endswith(".fullchain.pem"):
                    self.certificate_data = content
                elif name.endswith(".key.pem"):
                    self.private_key = content
                elif name.endswith(".ca.pem"):
                    self.ca_chain = content
                elif name.endswith(".csr.pem"):
                    self.csr_data = content

    def _parse_certificate(self):
        try:
            cert = x509.load_pem_x509_certificate(self.certificate_data.encode())
        except Exception as e:
            frappe.throw(f"Zertifikat konnte nicht gelesen werden: {e}")

        self.common_name = self._get_attr(cert.subject, x509.NameOID.COMMON_NAME)
        self.issuer = self._get_attr(cert.issuer, x509.NameOID.COMMON_NAME)
        self.not_valid_before = cert.not_valid_before_utc.strftime("%Y-%m-%d %H:%M:%S")
        self.not_valid_after = cert.not_valid_after_utc.strftime("%Y-%m-%d %H:%M:%S")
        self.is_wildcard = 1 if self.common_name and self.common_name.startswith("*.") else 0

        if not self.certificate_name:
            exp = cert.not_valid_after_utc.strftime("%Y-%m")
            self.certificate_name = f"{self.common_name} ({exp})"

        # Auto-set status based on expiry
        now_utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        if cert.not_valid_before_utc.replace(tzinfo=None) > now_utc:
            self.status = "Pending"
        elif cert.not_valid_after_utc.replace(tzinfo=None) < now_utc:
            self.status = "Expired"

        # Auto-detect certificate type from issuer
        if not self.certificate_type:
            issuer_org = self._get_attr(cert.issuer, x509.NameOID.ORGANIZATION_NAME) or ""
            if self.common_name and self._get_attr(cert.issuer, x509.NameOID.COMMON_NAME) == self.common_name:
                self.certificate_type = "Self-Signed"
            elif "Let's Encrypt" in issuer_org or "ZeroSSL" in issuer_org or "Sectigo" in issuer_org:
                self.certificate_type = "DV"

        # Populate SAN domains
        self._populate_san_domains(cert)

        # Build certificate info HTML
        self._build_cert_info_html(cert)

    def _populate_san_domains(self, cert):
        try:
            ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
            san_names = ext.value.get_values_for_type(x509.DNSName)
        except x509.ExtensionNotFound:
            san_names = []

        if self.common_name and self.common_name not in san_names:
            san_names.insert(0, self.common_name)

        existing = {row.domain_name for row in self.domains}
        for domain_name in san_names:
            if domain_name not in existing:
                # Try to find matching IT Domain
                it_domain = frappe.db.exists("IT Domain", domain_name.lstrip("*."))
                self.append("domains", {
                    "domain": it_domain or None,
                    "domain_name": domain_name,
                })

    def _build_cert_info_html(self, cert):
        subject = cert.subject
        cn = self._get_attr(subject, x509.NameOID.COMMON_NAME)
        org = self._get_attr(subject, x509.NameOID.ORGANIZATION_NAME)
        country = self._get_attr(subject, x509.NameOID.COUNTRY_NAME)
        state = self._get_attr(subject, x509.NameOID.STATE_OR_PROVINCE_NAME)

        try:
            ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
            sans = ext.value.get_values_for_type(x509.DNSName)
        except x509.ExtensionNotFound:
            sans = []

        serial_hex = format(cert.serial_number, "X")
        serial_formatted = ":".join(serial_hex[i:i+2] for i in range(0, len(serial_hex), 2))

        self.certificate_information = f"""
<table class="table table-bordered table-sm" style="margin:0">
  <tr><td style="width:180px"><strong>Common Name</strong></td><td>{cn or 'N/A'}</td></tr>
  <tr><td><strong>Organization</strong></td><td>{org or 'N/A'}</td></tr>
  <tr><td><strong>Country / State</strong></td><td>{country or 'N/A'} / {state or 'N/A'}</td></tr>
  <tr><td><strong>Issuer</strong></td><td>{self._get_attr(cert.issuer, x509.NameOID.COMMON_NAME) or 'N/A'}</td></tr>
  <tr><td><strong>SANs</strong></td><td>{', '.join(sans) if sans else 'None'}</td></tr>
  <tr><td><strong>Serial</strong></td><td><code style="font-size:11px">{serial_formatted}</code></td></tr>
  <tr><td><strong>Signature</strong></td><td>{cert.signature_hash_algorithm.name if cert.signature_hash_algorithm else 'N/A'}</td></tr>
</table>"""

    def _parse_ca(self):
        try:
            ca_cert = x509.load_pem_x509_certificate(self.ca_chain.encode())
        except Exception:
            self.ca_verification = "CA Chain nicht lesbar"
            return

        ca_cn = self._get_attr(ca_cert.subject, x509.NameOID.COMMON_NAME)
        ca_org = self._get_attr(ca_cert.issuer, x509.NameOID.ORGANIZATION_NAME)

        # Verify CA signed the certificate
        if self.certificate_data:
            cert = x509.load_pem_x509_certificate(self.certificate_data.encode())
            cert_issuer_cn = self._get_attr(cert.issuer, x509.NameOID.COMMON_NAME)
            ca_subject_cn = self._get_attr(ca_cert.subject, x509.NameOID.COMMON_NAME)
            if cert_issuer_cn == ca_subject_cn:
                self.ca_verification = "CA Chain valid"
            else:
                self.ca_verification = f"Mismatch: Cert Issuer={cert_issuer_cn}, CA CN={ca_subject_cn}"

        self.ca_information = f"""
<table class="table table-bordered table-sm" style="margin:0">
  <tr><td style="width:180px"><strong>CA Common Name</strong></td><td>{ca_cn or 'N/A'}</td></tr>
  <tr><td><strong>CA Issuer</strong></td><td>{ca_org or 'N/A'}</td></tr>
  <tr><td><strong>Valid Until</strong></td><td>{ca_cert.not_valid_after_utc}</td></tr>
</table>"""

    def _verify_private_key(self):
        try:
            cert = x509.load_pem_x509_certificate(self.certificate_data.encode())
            key_pem = self.get_password("private_key")
            private_key = serialization.load_pem_private_key(key_pem.encode(), password=None)

            message = b"x509_verify"
            signature = private_key.sign(message, PKCS1v15(), hashes.SHA256())
            cert.public_key().verify(signature, message, PKCS1v15(), hashes.SHA256())
            self.private_key_verification = "Key matches certificate"
        except Exception as e:
            self.private_key_verification = f"Key mismatch: {e}"

    def _set_auto_name(self):
        if self.not_valid_after:
            dt = frappe.utils.get_datetime(self.not_valid_after)
            new_name = f"{self.common_name}_{dt.strftime('%Y-%m-%d')}"
        else:
            new_name = self.common_name

        if new_name != self.name:
            frappe.rename_doc("SSL Certificate", self.name, new_name, force=True)

    @staticmethod
    def _get_attr(name_obj, oid):
        try:
            return name_obj.get_attributes_for_oid(oid)[0].value
        except (IndexError, Exception):
            return None

    @staticmethod
    def _resolve_file_path(file_url):
        if not file_url:
            return None
        if file_url.startswith("/private/files/"):
            return get_files_path(*file_url.split("/private/files/", 1)[1].split("/"), is_private=1)
        elif file_url.startswith("/files/"):
            return get_files_path(*file_url.split("/files/", 1)[1].split("/"))
        return None


@frappe.whitelist()
def get_certificate_pem(name, format_type):
    """Return PEM data for download. format_type: cert, key, ca, csr, fullchain, cert_key"""
    doc = frappe.get_doc("SSL Certificate", name)
    doc.check_permission("read")

    if format_type == "cert":
        return {"content": doc.certificate_data, "filename": f"{doc.common_name or name}.crt.pem"}

    elif format_type == "key":
        key = doc.get_password("private_key")
        if not key:
            frappe.throw("Kein Private Key vorhanden")
        return {"content": key, "filename": f"{doc.common_name or name}.key.pem"}

    elif format_type == "ca":
        if not doc.ca_chain:
            frappe.throw("Keine CA Chain vorhanden")
        return {"content": doc.ca_chain, "filename": f"{doc.common_name or name}.ca.pem"}

    elif format_type == "csr":
        if not doc.csr_data:
            frappe.throw("Kein CSR vorhanden")
        return {"content": doc.csr_data, "filename": f"{doc.common_name or name}.csr.pem"}

    elif format_type == "fullchain":
        parts = [doc.certificate_data]
        if doc.ca_chain:
            parts.append(doc.ca_chain)
        return {"content": "\n".join(parts), "filename": f"{doc.common_name or name}.fullchain.pem"}

    elif format_type == "cert_key":
        key = doc.get_password("private_key")
        if not key:
            frappe.throw("Kein Private Key vorhanden")
        return {"content": doc.certificate_data + "\n" + key, "filename": f"{doc.common_name or name}.combined.pem"}

    frappe.throw(f"Unbekanntes Format: {format_type}")
