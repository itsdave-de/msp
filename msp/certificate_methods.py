import frappe
from frappe.utils.file_manager import save_file
import zipfile
import os
from frappe.utils import get_files_path
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15
import datetime

def process_certficate_data(doctype, method=None):
    
    if doctype.attach_zip:
        doctype = create_attach_cert_and_key_from_zip(doctype)
        
    if doctype.attach_certificate_copy:
        fill_certificate_data_from_attach_certificate_copy_content(doctype)

    if not doctype.certificate_data:
        frappe.throw("No Cert Data Available.")
    else: 
        print(doctype.certificate_data)
        if not doctype.certificate_data.startswith('-----BEGIN CERTIFICATE-----') or not doctype.certificate_data.strip().endswith('-----END CERTIFICATE-----'):
            frappe.throw("Missing Start or End Marker in Certificate")
        else:
            print("Success")

    cert_data = parse_certificate_content(doctype.certificate_data)
    pretty_html_with_cert_data = get_pretty_html_from_cert_data(cert_data)
    print(pretty_html_with_cert_data)
    doctype.certificate_information = pretty_html_with_cert_data
    doctype.not_valid_before = cert_data["not_valid_before"]
    doctype.not_valid_after = cert_data["not_valid_after"]

    if doctype.ca_label_content:
        ca_data = parse_certificate_content(doctype.ca_label_content)
        pretty_html_with_ca_data = get_pretty_html_from_cert_data(ca_data)
        print(pretty_html_with_ca_data)
        doctype.ca_information = pretty_html_with_ca_data
        doctype.ca_verification = verify_ca(cert_data, ca_data)
    else:
        print("No CA label content")

    cert = doctype.certificate_data
    key = doctype.private_key
    doctype.private_key_verification = verify_private_key(doctype.private_key, doctype.certificate_data)

    if not doctype.certificate_name and doctype.certificate_information:
        set_certificate_name(doctype)

def set_doctype_name(doctype, method=None):

        cert_data = parse_certificate_content(doctype.certificate_data)
        common_name = cert_data["subject"]["common_name"]
        not_valid_after = cert_data["not_valid_after"]
        
        not_valid_after_dt = datetime.datetime.strptime(not_valid_after, "%Y-%m-%d %H:%M:%S")
        formatted_date = not_valid_after_dt.strftime('%Y-%m-%d-%H-%M')
        
        certname = f"{common_name}_{formatted_date}"

        frappe.rename_doc("x509_certificate", doctype.name, certname) 

        doctype.name = certname
        doctype.save()
        frappe.db.commit()

def verify_ca(cert_data, ca_data):
    if cert_data["issuer"]["common_name"] == ca_data["subject"]["common_name"]:
            print("CA correct")
            return "CA is valid"
    else:
            print("CA not valid")
            return "CA not valid"

def verify_private_key(key: str, cert: str):
    try:
        # Load the certificate
        certificate = load_pem_x509_certificate(cert.encode(), default_backend())

        # Load the key
        private_key = serialization.load_pem_private_key(
            key.encode(),
            password=None,
            backend=default_backend()
        )

        # Get the public key from the certificate
        public_key = certificate.public_key()

        # Generate a random message to sign and verify
        message = b"Cachimba"
        
        # Sign the message with the private key
        signature = private_key.sign(
            message,
            PKCS1v15(),
            hashes.SHA256()
        )
        
        # Verify the signature with the public key
        public_key.verify(
            signature,
            message,
            PKCS1v15(),
            hashes.SHA256()
        )
        
        return "Private Key is valid and matches the certificate."
    except Exception as e:
        print(f"An error occurred: {e}")
        return f"Private Key is not valid: {e}"

def create_attach_cert_and_key_from_zip(doctype):
    docname = doctype.name
    zip_file = doctype.attach_zip
    if zip_file:
        try:
            # Change the route to absolute if necesary
            if zip_file.startswith("/private/files/"):
                zip_file = get_files_path(*zip_file.split("/private/files/", 1)[1].split("/"), is_private=1)
            elif zip_file.startswith("/files/"):
                zip_file = get_files_path(*zip_file.split("/files/", 1)[1].split("/"))

            # Verify if the file exists
            if not os.path.exists(zip_file):
                return doctype

            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                for file_info in zip_ref.infolist():
                    filename = file_info.filename

                    # Check if filename ends with crt.pem or key.pem
                    if filename.endswith("crt.pem") or filename.endswith("key.pem") or filename.endswith("ca.pem"):
                        with zip_ref.open(filename) as extracted_file:
                            content = extracted_file.read()

                            # Determine the field to attach the file
                            if filename.endswith("crt.pem"):
                                attach_field = "attach_certificate_copy"
                            elif filename.endswith("key.pem"):
                                attach_field = "attach_key"
                            elif filename.endswith("ca.pem"):
                                attach_field = "ca_label_content"

                            # Save the file and attach it to the document
                            saved_file = save_file(filename, content, "x509_certificate", docname, df=attach_field, is_private=1)
                            doctype.set(attach_field, saved_file.file_url)

                            print(f"Filename: {filename}")
                            print(f"Content:\n{content.decode('utf-8')}\n")

        except Exception as e:
            print(f"Error extracting and reading zip file: {e}")
    else:
        print("No zip file attached or file path is empty.")
    
    return doctype

def fill_certificate_data_from_attach_certificate_copy_content(doctype):
    content, content_key, ca_label = None, None, None

    if doctype:
        if doctype.attach_certificate_copy:
            certificate_file_path = doctype.attach_certificate_copy
            content = read_file_content(certificate_file_path)
            doctype.certificate_data = content

        if doctype.attach_key:
            key_file_path = doctype.attach_key
            content_key = read_file_content(key_file_path)
            doctype.private_key = content_key

        if doctype.ca_label_content:
            ca_file_path = doctype.ca_label_content
            ca_label = read_file_content(ca_file_path)
            doctype.ca_label_content = ca_label

    return doctype

def read_file_content(file_path):
    if file_path:
        if file_path.startswith("/private/files/"):
            file_path = get_files_path(*file_path.split("/private/files/", 1)[1].split("/"), is_private=1)
        elif file_path.startswith("/files/"):
            file_path = get_files_path(*file_path.split("/files/", 1)[1].split("/"))
        
        try:
            with open(file_path, 'r') as file:
                content = file.read()
                if not content:
                    print(f"File {file_path} is empty.")
        except FileNotFoundError:
            print(f"File {file_path} not found.")
            content = None
    else:
        content = None

    return content

def parse_certificate_content(certificate_content):
    print("parse_certificate")
    try:
        certificate = x509.load_pem_x509_certificate(certificate_content.encode('utf-8'))

        subject_attrs = {
            "country": None,
            "state": None,
            "city": None,
            "organization": None,
            "organization_unit": None,
            "common_name": None
        }

        subject = certificate.subject
        for attr in subject:
            if attr.oid == x509.NameOID.COUNTRY_NAME:
                subject_attrs["country"] = attr.value
            elif attr.oid == x509.NameOID.STATE_OR_PROVINCE_NAME:
                subject_attrs["state"] = attr.value
            elif attr.oid == x509.NameOID.LOCALITY_NAME:
                subject_attrs["city"] = attr.value
            elif attr.oid == x509.NameOID.ORGANIZATION_NAME:
                subject_attrs["organization"] = attr.value
            elif attr.oid == x509.NameOID.ORGANIZATIONAL_UNIT_NAME:
                subject_attrs["organization_unit"] = attr.value
            elif attr.oid == x509.NameOID.COMMON_NAME:
                subject_attrs["common_name"] = attr.value

        # Obtain CN
        issuer = certificate.issuer
        issuer_common_name = None
        for attr in issuer:
            if attr.oid == x509.NameOID.COMMON_NAME:
                issuer_common_name = attr.value
                break

        subject_alt_names = format_subject_alt_names(certificate)
        data = {
            "subject": subject_attrs,
            "issuer": {
                "common_name": issuer_common_name
            },
            "subject_alt_names": subject_alt_names,
            "not_valid_before": str(certificate.not_valid_before),
            "not_valid_after": str(certificate.not_valid_after),
            "serial_number": certificate.serial_number,
            "signature_algorithm": str(certificate.signature_algorithm_oid)
        }

        return data
    except ValueError as e:
        print(f"Error parsing certificate data: {e}")
        return {"error": "Invalid certificate format"}
    except Exception as e:
        print(f"Error parsing certificate data: {e}")
        return {"error": str(e)}


def format_subject_alt_names(certificate):
    try:
        ext = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        alt_names = ext.value.get_values_for_type(x509.DNSName)
        return ', '.join(alt_names) if alt_names else 'No more'
    except x509.ExtensionNotFound:
        return 'No more'

def get_pretty_html_from_cert_data(cert_data):
    subject = cert_data.get("subject", {})
    issuer = cert_data.get("issuer", "N/A")

    # Format the certificate information
    certificate_info = (
        f"<strong>Subject:</strong><br>"
        f"- <strong>Common Name:</strong> {subject.get('common_name', 'N/A')}<br>"
        f"- <strong>Country:</strong> {subject.get('country', 'N/A')}<br>"
        f"- <strong>State/Province:</strong> {subject.get('state', 'N/A')}<br>"
        f"- <strong>City:</strong> {subject.get('city', 'N/A')}<br>"
        f"- <strong>Organization:</strong> {subject.get('organization', 'N/A')}<br>"
        f"- <strong>Organizational Unit:</strong> {subject.get('organization_unit', 'N/A')}<br>"
        f"<strong>Issuer:</strong> {issuer}<br>"
        f"<strong>Subject Alternative Name:</strong> {cert_data.get('subject_alt_names', 'N/A')}<br>"
        f"<strong>Validity Period:</strong><br>"
        f"- <strong>Not Before:</strong> {cert_data.get('not_valid_before', 'N/A')}<br>"
        f"- <strong>Not After:</strong> {cert_data.get('not_valid_after', 'N/A')}<br>"
        f"<strong>Serial Number:</strong> {cert_data.get('serial_number', 'N/A')}<br>"
    )
    print(certificate_info)
    return certificate_info

def set_certificate_name(doctype):
    cert_data = parse_certificate_content(doctype.certificate_data)
    
    common_name = cert_data["subject"]["common_name"]
    not_valid_after = cert_data["not_valid_after"]

    # Extrat date data
    not_valid_after_dt = datetime.datetime.strptime(not_valid_after, "%Y-%m-%d %H:%M:%S")
    year = not_valid_after_dt.year
    month = not_valid_after_dt.month
    day = not_valid_after_dt.day
    hour = not_valid_after_dt.hour
    minute = not_valid_after_dt.minute

    # Join CN and date
    certificate_name = f"{common_name}-{year}-{month:02d}-{day:02d}-{hour:02d}-{minute:02d}"

    doctype.certificate_name = certificate_name

    print(f"Certificate Name set to: {certificate_name}")