import datetime
import uuid
import pandas as pd
from ldap3 import Server, Connection, ALL, NTLM
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Configuration from environment variables
server_name = os.getenv('LDAP_SERVER')
domain_name = os.getenv('LDAP_DOMAIN')
username = os.getenv('LDAP_USERNAME')  # Format: DOMAIN\username
password = os.getenv('LDAP_PASSWORD')

# Connect to the server
server = Server(server_name, get_info=ALL)
conn = Connection(server, user=username, password=password, authentication=NTLM)

# Bind to the server
if not conn.bind():
    print('Error in binding to the server')
    exit()

# Get server info for automatic domain detection
server_info = server.info

# Determine search base - use domain root for recursive search
search_base = None

# Try environment variable first
env_search_base = os.getenv('LDAP_SEARCH_BASE')
if env_search_base:
    search_base = env_search_base
# Try to construct from domain name
elif domain_name:
    domain_parts = domain_name.split('.')
    search_base = ','.join([f'DC={part}' for part in domain_parts])
# Try to get from server naming contexts
elif hasattr(server_info, 'naming_contexts') and server_info.naming_contexts:
    for nc in server_info.naming_contexts:
        nc_str = str(nc)
        if nc_str.startswith('DC=') and 'CN=Configuration' not in nc_str and 'CN=Schema' not in nc_str:
            search_base = nc_str
            break

# Fallback
if not search_base:
    search_base = 'DC=corp,DC=local'

print(f"Durchsuche rekursiv: {search_base}")

# Simple user filter (exclude computer accounts)
search_filter = '(&(objectClass=user)(!(sAMAccountName=*$)))'

attributes = [
    'sAMAccountName', 'lastLogon', 'lastLogonTimestamp', 'objectGUID', 'userAccountControl',
    'givenName', 'sn', 'cn', 'displayName', 'distinguishedName', 
    'userPrincipalName', 'proxyAddresses', 'mail', 'lockoutTime'
]

# Perform recursive search
print("Starte rekursive Suche...")
try:
    from ldap3 import SUBTREE
    success = conn.search(search_base, search_filter, search_scope=SUBTREE, attributes=attributes)
    
    if success and conn.entries:
        print(f"Benutzer-Accounts gefunden: {len(conn.entries)}")
        
        # Remove duplicates based on distinguishedName
        seen_dns = set()
        unique_entries = []
        for entry in conn.entries:
            dn = str(entry.distinguishedName)
            if dn not in seen_dns:
                seen_dns.add(dn)
                unique_entries.append(entry)
        
        print(f"Nach Duplikat-Entfernung: {len(unique_entries)} eindeutige Benutzer-Accounts")
    else:
        unique_entries = []
        print("Keine Benutzer-Accounts gefunden")
        
except Exception as e:
    print(f"Fehler bei der Suche: {str(e)}")
    unique_entries = []

# Function to convert Windows File Time to human-readable format
def convert_filetime(filetime):
    if filetime and isinstance(filetime, int):
        return (datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=filetime / 10)).replace(tzinfo=None)
    elif filetime and isinstance(filetime, datetime.datetime):
        return filetime.replace(tzinfo=None)
    else:
        return None

# Function to check if the user is disabled
def is_user_disabled(user_account_control):
    return bool(user_account_control & 0x0002)

# Function to check if the user is locked
def is_user_locked(lockout_time):
    return lockout_time and lockout_time != 0

# Collecting results in a list
results = []

for entry in unique_entries:
    username = entry.sAMAccountName.value
    last_logon = entry.lastLogon.value
    last_logon_timestamp = entry.lastLogonTimestamp.value
    object_guid = entry.objectGUID.value
    user_account_control = entry.userAccountControl.value
    lockout_time = entry.lockoutTime.value

    # Convert timestamps
    last_logon_date = convert_filetime(last_logon)
    last_logon_timestamp_date = convert_filetime(last_logon_timestamp)

    # Determine the most recent logon date
    if last_logon_date and last_logon_timestamp_date:
        most_recent_logon = max(last_logon_date, last_logon_timestamp_date)
    else:
        most_recent_logon = last_logon_date or last_logon_timestamp_date or 'Never logged in'

    guid_string = object_guid
    disabled_status = "Disabled" if is_user_disabled(user_account_control) else "Enabled"
    locked_status = "Locked" if is_user_locked(lockout_time) else "Unlocked"

    given_name = entry.givenName.value if entry.givenName else 'N/A'
    sn = entry.sn.value if entry.sn else 'N/A'
    cn = entry.cn.value if entry.cn else 'N/A'
    display_name = entry.displayName.value if entry.displayName else 'N/A'
    distinguished_name = entry.distinguishedName.value if entry.distinguishedName else 'N/A'
    user_principal_name = entry.userPrincipalName.value if entry.userPrincipalName else 'N/A'
    proxy_addresses = ', '.join(entry.proxyAddresses.values) if entry.proxyAddresses else 'N/A'
    mail = entry.mail.value if entry.mail else 'N/A'

    # Skip computer accounts based on the presence of a dollar sign in the username
    if not username.endswith('$'):
        results.append({
            'User': username,
            'Given Name': given_name,
            'Surname': sn,
            'Common Name': cn,
            'Display Name': display_name,
            'Distinguished Name': distinguished_name,
            'User Principal Name': user_principal_name,
            'Proxy Addresses': proxy_addresses,
            'Mail': mail,
            'Most Recent Logon': most_recent_logon,
            'GUID': guid_string,
            'Status': disabled_status,
            'Lockout Status': locked_status
        })

# Unbind the connection
conn.unbind()

# Create a DataFrame and export to Excel
df = pd.DataFrame(results)

# Check if we have any results
if len(results) > 0:
    # Ensure all datetime columns are timezone-unaware
    datetime_columns = ['Most Recent Logon']
    for column in datetime_columns:
        if column in df.columns:
            df[column] = df[column].apply(lambda x: x.replace(tzinfo=None) if isinstance(x, datetime.datetime) else x)
    
    df.to_excel('active_directory_users.xlsx', index=False)
    print(f"Benutzer-Accounts erfolgreich exportiert. Gefundene Benutzer: {len(results)}")
else:
    print("\n=== DEBUGGING-INFORMATIONEN ===")
    print("Keine Benutzer-Accounts gefunden.")
    print(f"Search-Base: {search_base}")
    print(f"Search-Filter: {search_filter}")
    print(f"LDAP-Server: {server_name}")
    print(f"Domain: {domain_name}")
    
    if server_info and hasattr(server_info, 'naming_contexts'):
        print(f"Server Naming Contexts: {list(server_info.naming_contexts)}")
    if server_info and hasattr(server_info, 'schema_entry'):
        print(f"Schema Entry: {server_info.schema_entry}")
    
    print("\nBitte überprüfen Sie:")
    print("1. LDAP-Verbindung und Anmeldedaten")
    print("2. Search-Base Konfiguration")
    print("3. Berechtigungen für die Benutzer-Suche")
    print("4. Domain-Controller Erreichbarkeit")
    
    # Create empty Excel file with headers for reference
    headers = ['User', 'Given Name', 'Surname', 'Common Name', 'Display Name', 'Distinguished Name',
               'User Principal Name', 'Proxy Addresses', 'Mail', 'Most Recent Logon', 'GUID', 'Status', 'Lockout Status']
    empty_df = pd.DataFrame(columns=headers)
    empty_df.to_excel('active_directory_users.xlsx', index=False)