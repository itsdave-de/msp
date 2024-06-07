import frappe
from frappe.model.document import Document
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from frappe.utils import get_files_path
import json

class x509_certificate(Document):
    pass

@frappe.whitelist()
def read_cert_data(certificate_name=None, doc=None):
    """
    Read data of certificado X.509.

    Args:
        certificate_name (str): Name.
        doc (str): Documento JSON.

    Returns:
        dict: Certificate Data.
    """

    # Obtain certificate doc
    certificate_doc = get_certificate_doc(certificate_name)

    # Read data
    content, content_key = read_attached_files(doc, certificate_doc)

    # Parse and valid certificate
    if content:
        return parse_certificate(content, certificate_doc, content_key)

    # Read data from certificate_data field if no attached file
    cert_data_field = read_certificate_data_field(certificate_doc)
    if cert_data_field:
        return parse_certificate(cert_data_field, certificate_doc, content_key)


@frappe.whitelist()
def get_certificate_doc(certificate_name):
    """
    obtain the document.

    Args:
        certificate_name (str): Name of the certificate.

    Returns:
        Document: Document of certificate.
    """

    if isinstance(certificate_name, str):
        try:
            certificate_doc = frappe.get_doc("x509_certificate", certificate_name)
        except frappe.DoesNotExistError:
            print(f"Certificate document {certificate_name} not found.")
            return {"error": f"Certificate document {certificate_name} not found."}
    else:
        certificate_doc = certificate_name

    return certificate_doc


@frappe.whitelist()
def read_attached_files(doc, certificate_doc):
    """
    Read the certificate and the private key if it exist.

    Args:
        doc (str): JSON document that have extre-info.

    """

    content, content_key = None, None

    if doc and "attach_cert" in json.loads(doc):
        file_path = json.loads(doc)["attach_cert"]
        if file_path:
            content = read_file_content(file_path)
            certificate_doc.certificate_data = content
            certificate_doc.save()

    if doc and "attach_key" in json.loads(doc):
        file_path = json.loads(doc)["attach_key"]
        if file_path:
            content_key = read_file_content(file_path)
            certificate_doc.private_key = content_key
            certificate_doc.save()

    return content, content_key


@frappe.whitelist()
def read_file_content(file_path):
    """
    Read the file.

    Args:
        file_path (str): 

    Returns:
        str: content
    """

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

@frappe.whitelist()
def read_certificate_data_field(certificate_doc):
    """
    Read certificate_data field.

    Args:
        certificate_doc (Document): 

    Returns:
        str: Content of certificate_date
    """
    cert_data = getattr(certificate_doc, 'certificate_data', None)
    if cert_data:
        return cert_data
    return None

@frappe.whitelist()
def parse_certificate(content, certificate_doc, content_key):
    """
    Parse the information

    Args:
        content (str): 
        certificate_doc (Document): 
        content_key (str): 

    Returns:
        dict: Certificate data.
    """

    try:
        certificate = x509.load_pem_x509_certificate(content.encode('utf-8'))

        def get_attr(name):
            try:
                return certificate.subject.get_attributes_for_oid(name)[0].value
            except IndexError:
                return None

        subject_attrs = {
            "country": get_attr(x509.NameOID.COUNTRY_NAME),
            "state": get_attr(x509.NameOID.STATE_OR_PROVINCE_NAME),
            "city": get_attr(x509.NameOID.LOCALITY_NAME),
            "organization": get_attr(x509.NameOID.ORGANIZATION_NAME),
            "organization_unit": get_attr(x509.NameOID.ORGANIZATIONAL_UNIT_NAME),
            "common_name": get_attr(x509.NameOID.COMMON_NAME)
        }

        subject_alt_names = format_subject_alt_names(certificate)
        data = {
            "subject": subject_attrs,
            "issuer": str(certificate.issuer),
            "subject_alt_names": subject_alt_names,
            "not_valid_before": str(certificate.not_valid_before),
            "not_valid_after": str(certificate.not_valid_after),
            "serial_number": certificate.serial_number,
            "signature_algorithm": str(certificate.signature_algorithm_oid)
        }

        # Validar clave privada
        private_key_valid = validate_private_key(certificate_doc.private_key, content_key)
        data["private_key_valid"] = private_key_valid

        return data
    except ValueError as e:
        print(f"Error parsing certificate data: {e}")
        return {"error": "Invalid certificate format"}
    except Exception as e:
        print(f"Error parsing certificate data: {e}")
        return {"error": str(e)}


@frappe.whitelist()
def format_subject_alt_names(certificate):
    """
    Format alternative names

    Args:
        certificate (Certificate): Certificado X.509.

    Returns:
        str: Alternative names
    """

    try:
        ext = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        alt_names = ext.value.get_values_for_type(x509.DNSName)
        return ', '.join(alt_names) if alt_names else 'No more'
    except x509.ExtensionNotFound:
        return 'No more'


@frappe.whitelist()
def validate_private_key(private_key, content_key):
    """
    Validate the private key.

    Args:
        private_key (str): 
        content_key (str): content of private key

    Returns:
        bool: True if is correct, False if not.
    """

    if not private_key:
        return False  # La clave privada está vacía

    try:
        private_key = serialization.load_pem_private_key(private_key.encode('utf-8'), password=None, backend=default_backend())
        public_key = private_key.public_key()
        public_key.verify(
            private_key.sign(b'Hello World!', padding.PKCS1v15(), hashes.SHA256()),
            b'Hello World!',
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True  # La clave privada es válida
    except Exception as e:
        print(f"Error validating private key: {e}")
        return False  # La clave privada es inválida

