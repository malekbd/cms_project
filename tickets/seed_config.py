"""
Seed script to populate the config option tables from the original hardcoded choices.
Run with: python manage.py shell < tickets/seed_config.py
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cms_project.settings')
django.setup()

from tickets.models import IssueType, ReceivedByOption, TechnicianOption, BranchOption

# ─── Issue Types ─────────────────────────────────────────────────────────────
ISSUES = [
    ('SLOW SPEED', 'Slow Speed'), ('OFFLINE', 'Offline'), ('UNPLUG DEVICE', 'Unplug Device'),
    ('CABLE CUT', 'Cable Cut'), ('WEBSITE BROWSING', 'Website Browsing'), ('HIGH LATENCY', 'High Latency'),
    ('VPN', 'VPN'), ('HOUSE SHIFTING', 'House Shifting'), ('LASER ISSUE', 'Laser Issue'),
    ('NEW LINE', 'New Line'), ('PHYSICALLY DAMAGE', 'Physically Damage'), ('DUPLICATE LOGIN', 'Duplicate Login'),
    ('LINK UPDOWN', 'Link Up/Down'), ('PC PROBLEM', 'PC Problem'), ('ROUTER PROBLEM', 'Router Problem'),
    ('ROUTER CONFIG', 'Router Config'), ('BILL EXPIRY ISSUE', 'Bill Expiry Issue'), ('OTHERS', 'Others'),
    ('RECONNECTION', 'Reconnection'), ('PATCH CORD JOIN', 'Patch Cord Join'), ('TV PROBLEM', 'TV Problem'),
    ('ONU & CABLE RETURN', 'ONU & Cable Return'), ('MAINTENANCE', 'Maintenance'), ('ROOM CHANGE', 'Room Change'),
    ('CABLE CHANGE', 'Cable Change'), ('MAIN CABLE', 'Main Cable'), ('ONU RETURN', 'ONU Return'),
    ('LOCATION CHANGE', 'Location Change'), ('CABLE RETURN', 'Cable Return'), ('WIRELESS SECURITY', 'Wireless Security'),
    ('EDC LINE', 'EDC Line'), ('PASSWORD CHANGE', 'Password Change'), ('FORGET PASSWORD', 'Forget Password'),
    ('NEW ROUTER CONFIGURATION', 'New Router Config'), ('OLD ROUTER CONFIGURATION', 'Old Router Config'),
    ('WIFI PASSWORD ISSUE', 'WiFi Password Issue'), ('FACEBOOK, YOUTUBE ISSUE', 'FB/YouTube Issue'),
    ('SITE ISSUE', 'Site Issue'), ('CONNECTOR CHANGE', 'Connector Change'), ('BACKUP ROUTER', 'Backup Router'),
    ('CAMERA ISSUE', 'Camera Issue'), ('GAME ISSUE', 'Game Issue'), ('NO INTERNET', 'No Internet'),
    ('PC CONNECTION', 'PC Connection'), ('ONU PROBLRM', 'ONU Problem'), ('CHARGER CHANGE', 'Charger Change'),
]

# ─── Received By ─────────────────────────────────────────────────────────────
RECEIVED_BY = [
    ('MD SIR', 'MD Sir'), ('CTO SIR', 'CTO Sir'), ('HR ADMIN', 'HR Admin'), ('MANAGER', 'Manager'),
    ('NOC', 'NOC'), ('CALL CENTER', 'Call Center'), ('ACCOUNTS', 'Accounts'), ('MARKETING TEAM', 'Marketing Team'),
    ('PHYSICAL TEAM', 'Physical Team'), ('TRANSMISSION TEAM', 'Transmission Team'),
    ('DISTRIBUTION TEAM', 'Distribution Team'), ('BRANCH OFFICE', 'Branch Office'),
    ('FIBER TEAM', 'Fiber Team'), ('CEO', 'CEO'), ('COO', 'COO'),
]

# ─── Technicians ─────────────────────────────────────────────────────────────
TECHNICIANS = [
    ('SALAM', 'Salam'), ('ROBIUL', 'Robiul'), ('RIPON', 'Ripon'), ('ABU BAKKAR', 'Abu Bakkar'),
    ('ASHIQUE', 'Ashique'), ('PRANTIK', 'Prantik'), ('SHANTO', 'Shanto'), ('JAHID', 'Jahid'),
    ('SOLAIMAN', 'Solaiman'), ('WARID', 'Warid'), ('SULTAN', 'Sultan'), ('NADIM', 'Nadim'),
    ('SOJIB', 'Sojib'), ('RUBEL', 'Rubel'), ('SAKIB', 'Sakib'), ('MEHEDI', 'Mehedi'),
    ('DIPANTO', 'Dipanto'), ('EMRUL', 'Emrul'), ('MUNNA', 'Munna'), ('ARIF', 'Arif'),
    ('KHIRUL', 'Khirul'), ('ARMAN', 'Arman'), ('RASHIDUL', 'Rashidul'), ('SAMIUL', 'Samiul'),
    ('AJOY', 'Ajoy'), ('NOC', 'NOC'), ('FIBER TEAM', 'Fiber Team'), ('CALL CENTER', 'Call Center'),
    ('USER', 'User'), ('OTHERS', 'Others'), ('AUTOMATICALLY SOLVED', 'Automatically Solved'),
    ('FORWARDED TO TOHA', 'Forwarded to Toha'), ('FORWARDED TO NOC', 'Forwarded to NOC'),
    ('FORWARDED TO ACCOUNTS', 'Forwarded to Accounts'), ('FORWARDED TO SAMIUL', 'Forwarded to Samiul'),
    ('FORWARDED TO ULLAPARA', 'Forwarded to Ullapara'), ('FORWARDED TO SHAHZADPUR', 'Forwarded to Shahzadpur'),
    ('FORWARDED TO TARASH', 'Forwarded to Tarash'), ('FORWARDED TO RAIGANJ', 'Forwarded to Raiganj'),
    ('FORWARDED TO KODDA', 'Forwarded to Kodda'), ('FORWARDED TO BELKUCHI', 'Forwarded to Belkuchi'),
    ('FORWARDED TO KAMARKHANDA', 'Forwarded to Kamarkhanda'), ('FORWARDED TO PIPULBARIA', 'Forwarded to Pipulbaria'),
    ('FORWARDED TO ENAYETPUR', 'Forwarded to Enayetpur'), ('FORWARDED TO CHANDAIKONA', 'Forwarded to Chandaikona'),
    ('FORWARDED TO BUSINESS PARTNER', 'Forwarded to Business Partner'),
    ('FORWARDED TO CALL CENTER', 'Forwarded to Call Center'),
]

# ─── Branches ────────────────────────────────────────────────────────────────
BRANCHES = [
    ('Head Quarter, Sirajganj', 'Head Quarter, Sirajganj'), ('Ullapara', 'Ullapara'),
    ('Shahzadpur', 'Shahzadpur'), ('Tarash', 'Tarash'), ('Raiganj', 'Raiganj'),
    ('Kodda', 'Kodda'), ('Belkuchi', 'Belkuchi'), ('Kamarkhanda', 'Kamarkhanda'),
    ('Pipulbaria', 'Pipulbaria'), ('Enayetpur', 'Enayetpur'), ('Chandaikona', 'Chandaikona'),
]


def seed(Model, data, label):
    created = 0
    for i, (name, display) in enumerate(data):
        obj, was_created = Model.objects.get_or_create(
            name=name,
            defaults={'display_name': display, 'sort_order': i}
        )
        if was_created:
            created += 1
    print(f"  {label}: {created} created, {len(data) - created} already existed")


print("Seeding configuration options...")
seed(IssueType, ISSUES, "Issue Types")
seed(ReceivedByOption, RECEIVED_BY, "Received By")
seed(TechnicianOption, TECHNICIANS, "Technicians")
seed(BranchOption, BRANCHES, "Branches")
print("Done!")
