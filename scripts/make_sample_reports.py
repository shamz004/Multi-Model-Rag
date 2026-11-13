"""Generates the sample report PDFs in sample_docs/.

    python scripts/make_sample_reports.py

The reports describe a fictional company, Aurora Dynamics. Every figure is
invented, which makes them ideal test data: an answer can only be correct if
it really came from the documents, never from the language model's memory.
"""

from pathlib import Path

import pymupdf

OUT = Path(__file__).resolve().parents[1] / "sample_docs"

CSS = """
body { font-family: sans-serif; font-size: 10.5pt; line-height: 1.5; color: #1f2937; }
h1 { font-size: 24pt; color: #0f172a; margin: 0 0 4pt 0; }
h2 { font-size: 15pt; color: #0f172a; margin: 0 0 8pt 0; padding-bottom: 4pt; border-bottom: 1pt solid #94a3b8; }
h3 { font-size: 11.5pt; color: #0f172a; margin: 14pt 0 4pt 0; }
p { margin: 0 0 8pt 0; text-align: justify; }
.sub { font-size: 12pt; color: #475569; margin-bottom: 30pt; }
.cover { margin-top: 150pt; }
.meta { font-size: 9.5pt; color: #64748b; margin-top: 60pt; }
.break { page-break-before: always; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 12pt 0; }
th { background-color: #e2e8f0; text-align: left; padding: 5pt 6pt; font-size: 9.5pt; border: 0.5pt solid #94a3b8; }
td { padding: 5pt 6pt; font-size: 9.5pt; border: 0.5pt solid #94a3b8; }
li { margin-bottom: 4pt; }
"""


def table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table><tr>{head}</tr>{body}</table>"


def cover(title: str, subtitle: str, meta: str) -> str:
    return (
        f'<div class="cover"><h1>{title}</h1><p class="sub">{subtitle}</p>'
        f'<p class="meta">{meta}</p></div>'
    )


def section(title: str, body: str) -> str:
    return f'<div class="break"><h2>{title}</h2>{body}</div>'


ANNUAL_2023 = cover(
    "Aurora Dynamics",
    "Annual Report 2023",
    "Fiscal year ended 31 December 2023 &middot; Aurora Dynamics Holdings plc &middot; Rotterdam",
) + section(
    "1. Letter from the Chief Executive Officer",
    """
<p>Dear shareholders, 2023 was a year of disciplined growth for Aurora Dynamics. Total revenue
reached $412.6 million, an increase of 9.0% over the $378.5 million reported in 2022. Net income
rose to $38.2 million, compared with $33.9 million a year earlier, and our operating margin
improved to 13.1%.</p>
<p>Demand for warehouse automation remained strong throughout the year, and our Smart Logistics
segment grew faster than any other part of the business. We also made deliberate investments in
our people: headcount increased to 2,140 employees at year end, up from 1,985.</p>
<p>In March 2023 we opened a new engineering centre in Pune, India, which now employs 160
software and controls engineers. The centre gives us round-the-clock development coverage and
has already shortened the release cycle of our fleet-management software from twelve weeks to
eight.</p>
<p>The Board has proposed a dividend of $0.48 per share for 2023. I thank our customers,
employees and shareholders for their continued trust.</p>
<p><b>Maria Chen</b><br/>Chief Executive Officer</p>
""",
) + section(
    "2. Financial Highlights",
    "<p>The table below summarises the principal financial results for the year.</p>"
    + table(
        ["Measure", "2023", "2022", "Change"],
        [
            ["Total revenue", "$412.6 million", "$378.5 million", "+9.0%"],
            ["Gross profit", "$156.8 million", "$140.0 million", "+12.0%"],
            ["Operating income", "$54.1 million", "$46.9 million", "+15.4%"],
            ["Net income", "$38.2 million", "$33.9 million", "+12.7%"],
            ["Research and development", "$46.1 million", "$41.7 million", "+10.6%"],
            ["Dividend per share", "$0.48", "$0.42", "+14.3%"],
            ["Employees at year end", "2,140", "1,985", "+7.8%"],
        ],
    )
    + """
<h3>Revenue by segment</h3>
<p>Aurora Dynamics reports three operating segments.</p>
"""
    + table(
        ["Segment", "2023 revenue", "Share of total"],
        [
            ["Industrial Automation", "$251.3 million", "60.9%"],
            ["Smart Logistics", "$118.9 million", "28.8%"],
            ["Services", "$42.4 million", "10.3%"],
        ],
    )
    + """
<p>Industrial Automation remained the largest segment. Smart Logistics revenue grew 17.2%,
driven by orders for autonomous mobile robots from European grocery retailers. Services revenue,
which consists of maintenance contracts and software subscriptions, grew 6.5%.</p>
""",
) + section(
    "3. Operations Review",
    """
<h3>Manufacturing</h3>
<p>The company operates two manufacturing plants, in Rotterdam (Netherlands) and Brno (Czech
Republic). During 2023 the Brno plant completed a $9.4 million expansion that increased robot
assembly capacity from 3,200 to 4,500 units per year. On-time delivery improved to 94.2%, from
91.0% in 2022.</p>
<h3>Research and development</h3>
<p>Research and development spending was $46.1 million, equal to 11.2% of revenue. The main
programmes were the AD-7 collaborative robot arm, launched in September 2023, and version 5 of
the FleetPilot fleet-management software. The company held 312 active patents at year end.</p>
<h3>Customers</h3>
<p>Aurora Dynamics served more than 1,300 customers in 41 countries. No single customer
accounted for more than 6% of revenue. The customer retention rate for service contracts was
93%.</p>
""",
) + section(
    "4. Principal Risks",
    """
<p>The Board considers the following to be the principal risks facing the company.</p>
<ul>
<li><b>Supply chain concentration.</b> Roughly 38% of the precision gearboxes used in our robots
are purchased from a single supplier in Japan. A prolonged disruption would delay deliveries.</li>
<li><b>Currency exposure.</b> About 55% of revenue is earned in euros while the company reports
in US dollars. A 10% weakening of the euro would reduce reported revenue by approximately
$22 million.</li>
<li><b>Talent retention.</b> Competition for robotics and software engineers is intense.
Voluntary employee turnover was 9.8% in 2023.</li>
<li><b>Cybersecurity.</b> Our connected products and cloud services are potential targets for
attack. No material security incident occurred during the year.</li>
</ul>
""",
) + section(
    "5. Outlook for 2024",
    """
<p>For 2024 the company expects total revenue of between $450 million and $465 million and an
operating margin of approximately 14%. Capital expenditure is planned at $28 million, mainly
for a new test facility in Rotterdam. The company intends to increase research and development
spending to around $54 million and to continue evaluating acquisitions in machine vision.</p>
<p>This outlook assumes stable exchange rates and no significant deterioration in industrial
investment in Europe.</p>
""",
)

ANNUAL_2024 = cover(
    "Aurora Dynamics",
    "Annual Report 2024",
    "Fiscal year ended 31 December 2024 &middot; Aurora Dynamics Holdings plc &middot; Rotterdam",
) + section(
    "1. Letter from the Chief Executive Officer",
    """
<p>Dear shareholders, 2024 was the strongest year in the history of Aurora Dynamics. Total
revenue grew 14.4% to $471.9 million, exceeding the guidance of $450 million to $465 million
that we gave a year ago. Net income increased to $49.7 million and the operating margin
widened to 14.6%.</p>
<p>The most important strategic step of the year was the acquisition of Helix Vision Systems,
a machine-vision specialist based in Tampere, Finland. The transaction closed in July 2024 for
a total consideration of $62 million in cash. Helix brings 140 employees and camera-based
inspection technology that we are now building into every new robot we ship.</p>
<p>We also strengthened the leadership team. Daniel Okafor joined as Chief Financial Officer in
February 2024, succeeding Peter Lindqvist, who retired after eleven years with the company.</p>
<p>The Board has proposed a dividend of $0.56 per share for 2024, an increase of 16.7%.</p>
<p><b>Maria Chen</b><br/>Chief Executive Officer</p>
""",
) + section(
    "2. Financial Highlights",
    "<p>The table below summarises the principal financial results for the year.</p>"
    + table(
        ["Measure", "2024", "2023", "Change"],
        [
            ["Total revenue", "$471.9 million", "$412.6 million", "+14.4%"],
            ["Gross profit", "$184.0 million", "$156.8 million", "+17.3%"],
            ["Operating income", "$68.9 million", "$54.1 million", "+27.4%"],
            ["Net income", "$49.7 million", "$38.2 million", "+30.1%"],
            ["Research and development", "$55.3 million", "$46.1 million", "+20.0%"],
            ["Dividend per share", "$0.56", "$0.48", "+16.7%"],
            ["Employees at year end", "2,480", "2,140", "+15.9%"],
        ],
    )
    + """
<h3>Revenue by segment</h3>
"""
    + table(
        ["Segment", "2024 revenue", "Share of total"],
        [
            ["Industrial Automation", "$276.0 million", "58.5%"],
            ["Smart Logistics", "$149.2 million", "31.6%"],
            ["Services", "$46.7 million", "9.9%"],
        ],
    )
    + """
<p>Smart Logistics was again the fastest-growing segment, with revenue up 25.5%, helped by a
multi-year contract with a North American parcel carrier. Industrial Automation grew 9.8% and
Services grew 10.1%. Helix Vision Systems contributed $11.3 million of revenue in the five
months after the acquisition and is reported within Industrial Automation.</p>
""",
) + section(
    "3. Operations Review",
    """
<h3>Manufacturing</h3>
<p>The Rotterdam test facility announced last year opened in October 2024 at a cost of
$17.5 million. The Brno plant assembled 4,180 robots during the year, against a capacity of
4,500 units. On-time delivery reached 96.1%, the highest level the company has recorded.</p>
<h3>Research and development</h3>
<p>Research and development spending rose to $55.3 million, or 11.7% of revenue. The AD-9
heavy-payload robot arm was launched in May 2024 and can lift 35 kilograms. FleetPilot 6,
released in November 2024, added vision-guided navigation based on Helix technology. Active
patents increased to 371.</p>
<h3>Customers</h3>
<p>The company served more than 1,450 customers in 44 countries. The largest customer
represented 7% of revenue. The retention rate for service contracts improved to 95%.</p>
""",
) + section(
    "4. Principal Risks",
    """
<ul>
<li><b>Acquisition integration.</b> The benefits expected from Helix Vision Systems depend on
retaining its engineering team and combining two product roadmaps. Integration is planned to be
complete by the end of 2025.</li>
<li><b>Supply chain concentration.</b> Dependence on a single Japanese gearbox supplier has been
reduced from 38% to 27% of purchases after a second supplier in Germany was qualified.</li>
<li><b>Currency exposure.</b> Approximately 51% of revenue is earned in euros. A 10% weakening
of the euro would reduce reported revenue by about $24 million.</li>
<li><b>Talent retention.</b> Voluntary employee turnover fell to 8.4% in 2024.</li>
<li><b>Regulation of artificial intelligence.</b> New European rules on AI in machinery will
apply to vision-guided products from 2026 and will increase certification costs.</li>
</ul>
""",
) + section(
    "5. Outlook for 2025",
    """
<p>For 2025 the company expects total revenue of between $520 million and $540 million and an
operating margin of approximately 15%. Capital expenditure is planned at $31 million. Research
and development spending is expected to be around $63 million. The company does not plan
further acquisitions during 2025 while the integration of Helix Vision Systems is completed.</p>
""",
)

SUSTAINABILITY_2024 = cover(
    "Aurora Dynamics",
    "Sustainability Report 2024",
    "Environmental, social and governance performance for calendar year 2024",
) + section(
    "1. Climate and Energy",
    """
<p>Aurora Dynamics has committed to reaching net-zero emissions in its own operations by 2035.
In 2024, combined Scope 1 and Scope 2 greenhouse gas emissions were 18,400 tonnes of CO2
equivalent, a reduction of 12% from 20,900 tonnes in 2023.</p>
<p>The share of electricity from renewable sources increased to 64%, from 49% in 2023. The main
contributor was a 2.1 megawatt rooftop solar installation at the Brno plant, which began
operating in April 2024 and supplies about 30% of that site's electricity.</p>
"""
    + table(
        ["Indicator", "2024", "2023"],
        [
            ["Scope 1 and 2 emissions (tonnes CO2e)", "18,400", "20,900"],
            ["Renewable electricity share", "64%", "49%"],
            ["Energy use (megawatt hours)", "71,200", "74,600"],
            ["Water withdrawal (cubic metres)", "96,000", "104,500"],
            ["Waste recycled", "81%", "76%"],
        ],
    )
    + """
<p>The company's interim target is a 50% reduction in Scope 1 and 2 emissions by 2030 compared
with the 2021 baseline of 26,300 tonnes.</p>
""",
) + section(
    "2. People and Safety",
    """
<p>The total recordable incident rate (TRIR) was 0.82 per 200,000 hours worked in 2024,
compared with 1.05 in 2023. There were no fatalities. Every production employee completed at
least 16 hours of safety training.</p>
<p>Women held 34% of leadership positions at the end of 2024, up from 31%. The company's goal
is 40% by 2028. Employees received an average of 27 hours of training during the year, and the
annual engagement survey had a participation rate of 88%.</p>
<h3>Community</h3>
<p>Aurora Dynamics donated $1.2 million to technical education programmes and provided 14
refurbished robot arms to vocational schools in the Netherlands and the Czech Republic.</p>
""",
) + section(
    "3. Governance and Supply Chain",
    """
<p>The Board of Directors has nine members, of whom six are independent. A Sustainability
Committee chaired by independent director Ingrid Solberg oversees climate targets and meets
four times a year. Since 2024, 15% of executive variable pay has been linked to emissions and
safety targets.</p>
<p>All 212 strategic suppliers have signed the Supplier Code of Conduct. During 2024 the company
carried out 58 on-site supplier audits; three suppliers were placed on corrective action plans
and one contract was terminated for repeated labour-standards violations.</p>
""",
)

SECURITY_POLICY = cover(
    "Aurora Dynamics",
    "Information Security Policy",
    "Policy IS-001 &middot; Version 4.2 &middot; Effective 1 January 2025 &middot; "
    "Owner: Chief Information Security Officer",
) + section(
    "1. Purpose and Scope",
    """
<p>This policy defines the minimum information security requirements for Aurora Dynamics. It
applies to all employees, contractors and temporary staff, and to every system that stores or
processes company information, including personal devices used for work.</p>
<p>The Chief Information Security Officer (CISO), Rahul Menon, owns this policy. It is reviewed
at least once every twelve months. Exceptions must be approved in writing by the CISO and are
valid for a maximum of six months.</p>
""",
) + section(
    "2. Access Control",
    """
<h3>Passwords</h3>
<p>Passwords must be at least 14 characters long and must not be reused across systems.
Passwords for standard accounts do not expire unless a compromise is suspected. Credentials for
privileged and administrator accounts must be rotated every 90 days and stored in the approved
password vault.</p>
<h3>Multi-factor authentication</h3>
<p>Multi-factor authentication (MFA) is mandatory for all remote access, all cloud services and
all administrator accounts. SMS text messages are not an approved second factor; staff must use
the company authenticator app or a hardware security key.</p>
<h3>Access reviews</h3>
<p>System owners must review user access rights every quarter. Access for employees who leave
the company must be removed within 24 hours of their last working day.</p>
""",
) + section(
    "3. Devices and Data",
    """
<h3>Devices</h3>
<p>All laptops must use full-disk encryption and lock automatically after 5 minutes of
inactivity. Critical security patches must be installed within 7 days of release and all other
patches within 30 days. Lost or stolen devices must be reported to the IT service desk
immediately.</p>
<h3>Data classification</h3>
<p>Information is classified into four levels: Public, Internal, Confidential and Restricted.
Restricted information, which includes customer source code and payroll data, may only be stored
on company-managed systems and must be encrypted in transit and at rest.</p>
<h3>Backups</h3>
<p>Business-critical systems are backed up daily. Backups are retained for 35 days and a restore
test is performed every quarter. Backup copies are stored in a separate geographic region.</p>
""",
) + section(
    "4. Incident Response and Compliance",
    """
<p>Any suspected security incident must be reported to the Security Operations Centre within
1 hour of discovery, by email to security@auroradynamics.example or by phone on extension 4400.
Staff must not attempt to investigate incidents themselves.</p>
<p>Incidents are classified as low, medium, high or critical. Critical incidents are escalated
to the CISO within 30 minutes and to the executive team within 4 hours. A written post-incident
review is completed within 10 working days.</p>
<p>All staff must complete security awareness training within 30 days of joining and once a
year afterwards. Simulated phishing exercises are run every month. Failure to follow this
policy may result in disciplinary action.</p>
""",
)

REPORTS = {
    "Aurora_Dynamics_Annual_Report_2023.pdf": ("Aurora Dynamics | Annual Report 2023", ANNUAL_2023),
    "Aurora_Dynamics_Annual_Report_2024.pdf": ("Aurora Dynamics | Annual Report 2024", ANNUAL_2024),
    "Aurora_Dynamics_Sustainability_Report_2024.pdf": (
        "Aurora Dynamics | Sustainability Report 2024",
        SUSTAINABILITY_2024,
    ),
    "Aurora_Dynamics_Information_Security_Policy.pdf": (
        "Aurora Dynamics | Information Security Policy IS-001",
        SECURITY_POLICY,
    ),
}


def build(path: Path, footer: str, html: str) -> int:
    page_rect = pymupdf.paper_rect("a4")
    content_rect = page_rect + (62, 64, -62, -70)
    story = pymupdf.Story(html=html, user_css=CSS)
    writer = pymupdf.DocumentWriter(str(path))
    more = True
    while more:
        device = writer.begin_page(page_rect)
        more, _ = story.place(content_rect)
        story.draw(device)
        writer.end_page()
    writer.close()

    # Second pass: add a footer with the page number to every page after the cover.
    doc = pymupdf.open(str(path))
    for number, page in enumerate(doc, start=1):
        if number == 1:
            continue
        page.insert_text(
            (62, page_rect.height - 40), f"{footer}   |   Page {number}", fontsize=8, color=(0.4, 0.45, 0.5)
        )
    pages = doc.page_count
    doc.save(str(path), incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
    doc.close()
    return pages


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for filename, (footer, html) in REPORTS.items():
        pages = build(OUT / filename, footer, html)
        print(f"{filename}: {pages} pages")


if __name__ == "__main__":
    main()
