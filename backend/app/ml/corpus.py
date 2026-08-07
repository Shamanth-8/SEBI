"""
Synthetic SEBI circular corpus.

The training data and the demo PDFs come from the SAME structured specs, so every
sentence carries ground-truth labels for free (obligation / category / severity /
intermediary / deadline type). That is what makes the trained model auditable:
the label of each training sentence is known by construction, not guessed.

Public entry points:
    build_circular(family, seed, ...) -> CircularSpec
    build_training_specs(n_per_family, seed) -> list[CircularSpec]
    build_negative_documents(n, seed)        -> list[(title, text)]
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

# ── Label spaces ─────────────────────────────────────────────────────────────

CATEGORIES = [
    "cyber_security",
    "surveillance",
    "kyc_onboarding",
    "margin_risk",
    "investor_grievance",
    "outsourcing_bcp",      # held out of the demo corpus — used to test novelty
]

# Families that make up the 5 demo circulars (and the doc-level classifier's classes)
DEMO_FAMILIES = [
    "cyber_security",
    "surveillance",
    "kyc_onboarding",
    "margin_risk",
    "investor_grievance",
]

SEVERITIES = ["high", "medium", "low"]

INTERMEDIARY_TYPES = [
    "stockbroker", "depository", "listed_company",
    "investment_adviser", "fiduciary", "rta",
]

DEADLINE_TYPES = ["fixed", "recurring", "relative", "not_specified"]

# ── Slot vocabularies ────────────────────────────────────────────────────────

ENTITIES: Dict[str, List[str]] = {
    "stockbroker": ["stock broker", "trading member", "stock broker and trading member",
                    "member of the stock exchange"],
    "depository": ["depository", "depository participant", "depository and depository participant"],
    "listed_company": ["listed entity", "listed company", "issuer whose securities are listed"],
    "investment_adviser": ["investment adviser", "registered investment adviser",
                           "research analyst and investment adviser"],
    "fiduciary": ["fiduciary", "portfolio manager", "asset management company"],
    "rta": ["registrar to an issue and share transfer agent", "RTA", "share transfer agent"],
}

RESPONSIBLE_PARTIES = [
    "Compliance Officer", "Designated Director", "Chief Information Security Officer",
    "Risk Management Committee", "Board of Directors", "Principal Officer",
    "Chief Risk Officer", "Audit Committee", "Chief Executive Officer",
    "Head of Operations", "Investor Grievance Redressal Officer",
]

PERIODS = ["7 days", "15 days", "30 days", "45 days", "60 days", "90 days",
           "two working days", "five working days", "one month", "six months"]

FREQUENCIES = ["daily", "weekly", "monthly", "quarterly", "half-yearly", "annually",
               "on a quarterly basis", "at the end of every calendar quarter"]

AUTHORITIES = ["SEBI", "the Board", "the concerned stock exchange", "the depository",
               "the clearing corporation", "the Designated Authority"]

# ── Clause template bank ─────────────────────────────────────────────────────
# Each template is (text, severity, deadline_type, evidence[], action_verb).
# {entity} {period} {frequency} {authority} {responsible} are slot-filled.

ObligationTemplate = Tuple[str, str, str, List[str], str]

OBLIGATION_TEMPLATES: Dict[str, List[ObligationTemplate]] = {
    "cyber_security": [
        ("Every {entity} shall formulate a comprehensive cyber security and cyber resilience "
         "policy duly approved by its Board of Directors, and shall review the said policy {frequency}.",
         "high", "recurring", ["Board-approved policy document", "Board minutes recording approval"],
         "formulate and review cyber security policy"),
        ("The {entity} shall appoint a Chief Information Security Officer who shall be responsible "
         "for assessing, identifying and reducing cyber security risks, and shall report directly to "
         "the {responsible}.",
         "high", "not_specified", ["Appointment letter of CISO", "Reporting structure chart"],
         "appoint Chief Information Security Officer"),
        ("The {entity} shall report all cyber attacks, threats, cyber incidents and breaches "
         "experienced by it to {authority} within {period} of the incident being noticed.",
         "high", "relative", ["Incident report submitted to SEBI", "Incident register extract"],
         "report cyber incidents"),
        ("Every {entity} shall conduct a comprehensive Vulnerability Assessment and Penetration "
         "Testing of its critical systems {frequency} and shall close all identified vulnerabilities "
         "within {period} of the report.",
         "high", "recurring", ["VAPT report", "Vulnerability closure tracker"],
         "conduct VAPT and remediate findings"),
        ("The {entity} shall maintain logs of all critical systems for a minimum period of two years "
         "in a tamper-proof manner and shall make such logs available to {authority} on demand.",
         "medium", "not_specified", ["Log retention policy", "Sample log archive"],
         "maintain and retain system logs"),
        ("The {entity} shall ensure that all critical data is encrypted both at rest and in transit "
         "using industry-recognised encryption standards.",
         "high", "not_specified", ["Encryption standard document", "System configuration evidence"],
         "encrypt critical data"),
        ("The {entity} shall carry out a cyber audit through an independent auditor {frequency} and "
         "submit the audit report along with the comments of its {responsible} to {authority}.",
         "medium", "recurring", ["Independent cyber audit report", "Management comments"],
         "conduct and submit cyber audit"),
        ("The {entity} shall implement multi-factor authentication for all remote access to its "
         "trading and back-office systems, and shall disable access of separated employees within "
         "{period}.",
         "high", "relative", ["MFA configuration evidence", "Access revocation log"],
         "enforce multi-factor authentication"),
        ("The {entity} shall establish a Security Operations Centre, either in-house or through a "
         "service provider, for continuous monitoring of security events.",
         "medium", "not_specified", ["SOC service agreement", "Monitoring dashboard screenshots"],
         "establish security operations centre"),
        ("No {entity} shall store client credentials in plain text in any system, database or "
         "application under its control.",
         "high", "not_specified", ["Database schema review", "Code review sign-off"],
         "prohibit plain-text credential storage"),
    ],
    "surveillance": [
        ("Every {entity} shall put in place a surveillance system, including appropriate software, "
         "to generate alerts for detecting potential market manipulation and unusual trading patterns.",
         "high", "not_specified", ["Surveillance system documentation", "Alert configuration list"],
         "implement surveillance system"),
        ("The {entity} shall dispose of all surveillance alerts generated by the system within "
         "{period} from the date of generation of the alert.",
         "high", "relative", ["Alert disposal register", "Ageing report of open alerts"],
         "dispose surveillance alerts within timeline"),
        ("The {entity} shall submit a report on the status of alerts generated and disposed of to "
         "{authority} on a {frequency} basis in the prescribed format.",
         "medium", "recurring", ["Quarterly alert status report", "Acknowledgement from exchange"],
         "submit alert status report"),
        ("The {entity} shall maintain records of all alerts, the analysis undertaken and the action "
         "taken thereon for a minimum period of five years.",
         "medium", "not_specified", ["Alert analysis records", "Retention policy"],
         "maintain alert records"),
        ("Where the {entity} suspects that a transaction is manipulative in nature, it shall report "
         "such transaction to {authority} within {period} of forming such suspicion.",
         "high", "relative", ["Suspicious transaction report", "Internal escalation note"],
         "report suspicious transactions"),
        ("The {entity} shall carry out due diligence of its clients on a continuous basis and shall "
         "document the rationale for classifying any client as high risk.",
         "medium", "not_specified", ["Client due-diligence file", "Risk classification rationale"],
         "conduct continuous client due diligence"),
        ("The {responsible} of the {entity} shall place a summary of surveillance alerts and their "
         "disposal before the Board {frequency}.",
         "medium", "recurring", ["Board agenda note", "Board minutes"],
         "place surveillance summary before Board"),
        ("The {entity} shall obtain and preserve documentary evidence supporting the funds and "
         "securities transferred in transactions flagged by the surveillance system.",
         "medium", "not_specified", ["Bank statements", "Demat transaction statements"],
         "preserve transaction evidence"),
        ("The {entity} shall not deal with any client whose transactions have been identified as "
         "manipulative unless the matter has been examined and recorded by the {responsible}.",
         "high", "not_specified", ["Examination note", "Approval record"],
         "restrict dealings with flagged clients"),
        ("The {entity} shall calibrate the parameters and thresholds of its alert generation logic "
         "at least {frequency} to reflect prevailing market conditions.",
         "low", "recurring", ["Threshold review note", "Change log of alert parameters"],
         "recalibrate alert thresholds"),
    ],
    "kyc_onboarding": [
        ("Every {entity} shall complete the Know Your Client procedure for each client before "
         "opening the account and shall not accept any funds or securities prior to such completion.",
         "high", "not_specified", ["Completed KYC form", "Client account opening record"],
         "complete KYC before onboarding"),
        ("The {entity} shall upload the KYC records of every new client on the KYC Registration "
         "Agency system within {period} of account opening.",
         "high", "relative", ["KRA upload acknowledgement", "Upload timestamp report"],
         "upload KYC records to KRA"),
        ("The {entity} shall carry out in-person verification of every client, either physically or "
         "through a Board-approved video-based process, and shall preserve the record thereof.",
         "high", "not_specified", ["IPV recording", "IPV register"],
         "perform in-person verification"),
        ("The {entity} shall categorise every client as low, medium or high risk and shall review "
         "such categorisation {frequency}.",
         "medium", "recurring", ["Client risk categorisation register", "Periodic review note"],
         "categorise and review client risk"),
        ("The {entity} shall obtain a fresh declaration of beneficial ownership from every "
         "non-individual client and shall update the same within {period} of any change.",
         "medium", "relative", ["Beneficial ownership declaration", "Change update log"],
         "obtain beneficial ownership declaration"),
        ("The {entity} shall preserve all client onboarding documents for a period of five years "
         "from the date of cessation of the client relationship.",
         "medium", "not_specified", ["Document retention register", "Archive index"],
         "preserve onboarding documents"),
        ("The {responsible} shall ensure that no account is opened in a fictitious or benami name, "
         "and shall record the verification performed in this regard.",
         "high", "not_specified", ["Name screening report", "Verification sign-off"],
         "prevent fictitious accounts"),
        ("The {entity} shall screen every client against the sanctions lists circulated by "
         "{authority} prior to onboarding and {frequency} thereafter.",
         "high", "recurring", ["Sanctions screening report", "Screening tool audit trail"],
         "screen clients against sanctions lists"),
        ("The {entity} shall obtain the consent of the client for the specific purposes for which "
         "personal data is collected and shall not use such data for any other purpose.",
         "medium", "not_specified", ["Consent record", "Data usage policy"],
         "obtain purpose-limited consent"),
        ("The {entity} shall re-verify the mobile number and email address registered for each "
         "client at least {frequency} and shall report unverified accounts to the {responsible}.",
         "low", "recurring", ["Contact re-verification report", "Exception list"],
         "re-verify client contact details"),
    ],
    "margin_risk": [
        ("Every {entity} shall collect the upfront margin from its clients before the execution of "
         "any trade and shall not permit trading against unpaid margins.",
         "high", "not_specified", ["Margin collection statement", "Client ledger extract"],
         "collect upfront margin"),
        ("The {entity} shall report the client-wise margin collected to {authority} on a "
         "{frequency} basis in the prescribed file format.",
         "high", "recurring", ["Margin reporting file", "Exchange acknowledgement"],
         "report client-wise margins"),
        ("The {entity} shall square off positions of clients who fail to meet the margin call "
         "within {period} of the call being made.",
         "high", "relative", ["Margin call records", "Square-off trade log"],
         "square off unmet margin positions"),
        ("The {entity} shall maintain a minimum net worth as prescribed and shall intimate "
         "{authority} within {period} of any erosion in such net worth.",
         "high", "relative", ["Net worth certificate", "Intimation to exchange"],
         "maintain and report net worth"),
        ("The {entity} shall segregate client funds from its own funds and shall not use client "
         "funds for its proprietary obligations under any circumstance.",
         "high", "not_specified", ["Bank account segregation proof", "Daily fund segregation report"],
         "segregate client funds"),
        ("The {entity} shall carry out a stress test of its exposure {frequency} and shall place "
         "the results before its {responsible}.",
         "medium", "recurring", ["Stress test report", "Committee minutes"],
         "conduct exposure stress testing"),
        ("The {entity} shall reconcile client securities held in its demat accounts with client "
         "ledgers {frequency} and shall resolve discrepancies within {period}.",
         "medium", "recurring", ["Reconciliation statement", "Discrepancy closure record"],
         "reconcile client securities"),
        ("The {entity} shall not accept any margin in the form of a third-party guarantee or an "
         "instrument not permitted by {authority}.",
         "medium", "not_specified", ["Margin composition report", "Collateral policy"],
         "restrict impermissible margin instruments"),
        ("The {entity} shall disclose to each client, {frequency}, a statement of funds and "
         "securities held on the client's behalf.",
         "medium", "recurring", ["Client statement dispatch log", "Sample statement"],
         "issue client funds and securities statement"),
        ("The {responsible} shall review the risk management policy of the {entity} at least "
         "{frequency} and record the review in writing.",
         "low", "recurring", ["Risk policy review note", "Signed review record"],
         "review risk management policy"),
    ],
    "investor_grievance": [
        ("Every {entity} shall designate an Investor Grievance Redressal Officer and shall display "
         "the name, contact number and email address of such officer on its website.",
         "medium", "not_specified", ["Website screenshot", "Designation letter"],
         "designate grievance redressal officer"),
        ("The {entity} shall resolve every investor complaint received on the SCORES platform "
         "within {period} of its receipt.",
         "high", "relative", ["SCORES resolution record", "Action taken report"],
         "resolve SCORES complaints within timeline"),
        ("The {entity} shall submit an Action Taken Report on each complaint to {authority} and "
         "shall upload supporting documents along with such report.",
         "high", "not_specified", ["Action Taken Report", "Supporting documents"],
         "submit action taken report"),
        ("The {entity} shall disclose on its website, {frequency}, the number of complaints "
         "received, resolved and pending, along with the average resolution time.",
         "medium", "recurring", ["Website disclosure", "Complaints data sheet"],
         "disclose complaints data"),
        ("The {entity} shall maintain a register of all investor complaints containing the date of "
         "receipt, nature of complaint, action taken and date of closure.",
         "medium", "not_specified", ["Complaints register", "Closure records"],
         "maintain complaints register"),
        ("Where a complaint is not resolved within the prescribed period, the {responsible} shall "
         "record the reasons for the delay and place the same before the Board {frequency}.",
         "medium", "recurring", ["Delay justification note", "Board minutes"],
         "escalate unresolved complaints"),
        ("The {entity} shall participate in the Online Dispute Resolution mechanism and shall abide "
         "by the outcome of the conciliation or arbitration proceedings.",
         "high", "not_specified", ["ODR case records", "Settlement records"],
         "participate in ODR mechanism"),
        ("The {entity} shall not levy any charge on an investor for the redressal of a complaint.",
         "low", "not_specified", ["Fee schedule", "Complaint cost records"],
         "prohibit complaint handling charges"),
        ("The {entity} shall conduct investor awareness programmes {frequency} and shall report the "
         "details of such programmes to {authority}.",
         "low", "recurring", ["Programme attendance records", "Report to exchange"],
         "conduct investor awareness programmes"),
        ("The {entity} shall preserve all records relating to investor complaints for a period of "
         "eight years from the date of closure of the complaint.",
         "medium", "not_specified", ["Retention schedule", "Archived complaint files"],
         "preserve complaint records"),
    ],
    "outsourcing_bcp": [
        ("Every {entity} shall formulate a Board-approved outsourcing policy identifying the "
         "activities that may and may not be outsourced.",
         "high", "not_specified", ["Board-approved outsourcing policy", "Board minutes"],
         "formulate outsourcing policy"),
        ("The {entity} shall not outsource any core business activity, including compliance and "
         "risk management functions, to any third-party service provider.",
         "high", "not_specified", ["Activity classification register", "Vendor scope documents"],
         "prohibit outsourcing of core activities"),
        ("The {entity} shall carry out due diligence of every service provider before engagement "
         "and shall review such due diligence {frequency}.",
         "medium", "recurring", ["Vendor due diligence report", "Periodic review note"],
         "conduct vendor due diligence"),
        ("The {entity} shall put in place a Business Continuity Plan and a Disaster Recovery site, "
         "and shall test the plan {frequency}.",
         "high", "recurring", ["BCP-DR policy", "DR drill report"],
         "maintain and test business continuity plan"),
        ("The {entity} shall ensure that the Recovery Time Objective does not exceed the timeline "
         "prescribed by {authority} and shall report any breach within {period}.",
         "high", "relative", ["RTO measurement report", "Breach intimation"],
         "meet recovery time objective"),
        ("The {entity} shall include in every outsourcing agreement a clause permitting {authority} "
         "to access the records maintained by the service provider.",
         "medium", "not_specified", ["Executed agreement with access clause", "Contract register"],
         "include regulatory access clause"),
        ("The {responsible} shall place before the Board, {frequency}, a report on the performance "
         "of all material outsourcing arrangements.",
         "medium", "recurring", ["Vendor performance report", "Board minutes"],
         "report on outsourcing arrangements"),
        ("The {entity} shall notify {authority} within {period} of the termination of any material "
         "outsourcing arrangement.",
         "medium", "relative", ["Termination notice", "Regulatory intimation"],
         "notify termination of outsourcing"),
    ],
}

# Non-obligation sentences: background, recitals, definitions, cross-references.
CONTEXT_TEMPLATES: Dict[str, List[str]] = {
    "_common": [
        "SEBI has, from time to time, issued circulars prescribing the framework applicable to "
        "market intermediaries in this regard.",
        "This circular is issued in exercise of the powers conferred under Section 11(1) of the "
        "Securities and Exchange Board of India Act, 1992, to protect the interests of investors "
        "in securities and to promote the development of the securities market.",
        "The provisions of this circular shall come into force with effect from the date specified "
        "in paragraph 1 above.",
        "The stock exchanges and depositories are advised to bring the provisions of this circular "
        "to the notice of their members and participants and disseminate the same on their websites.",
        "This circular is available on the SEBI website at www.sebi.gov.in under the categories "
        "'Legal' and 'Circulars'.",
        "The representations received from market participants and the recommendations of the "
        "concerned advisory committee have been examined by the Board.",
        "For the purposes of this circular, the terms used but not defined herein shall have the "
        "same meaning as assigned to them under the Securities Contracts (Regulation) Act, 1956.",
        "A consultation paper on the subject was placed on the SEBI website and public comments "
        "were invited thereon.",
        "The extant provisions in this regard are contained in the Master Circular issued for "
        "intermediaries, as amended from time to time.",
        "The format for the reports referred to in this circular is enclosed as Annexure A to this "
        "circular.",
        "Illustrations explaining the computation described above are provided in the annexure for "
        "the guidance of market participants.",
        "The intent of the framework described below is to strengthen the existing practices "
        "followed by market participants.",
    ],
    "cyber_security": [
        "Rapid technological developments in the securities market have increased the exposure of "
        "market intermediaries to cyber risk.",
        "Cyber security refers to the set of technologies, processes and practices designed to "
        "protect networks, computers, programmes and data from attack, damage or unauthorised access.",
        "Cyber resilience is the ability of an organisation to prepare for, respond to and recover "
        "from a cyber attack while continuing to operate.",
    ],
    "surveillance": [
        "Market intermediaries occupy a position of trust and are the first level of regulation in "
        "the securities market.",
        "An indicative list of transactional alerts that may be generated is provided in the "
        "annexure to this circular.",
        "The nature of alerts described herein is illustrative and not exhaustive.",
    ],
    "kyc_onboarding": [
        "Know Your Client norms form the foundation of the anti-money-laundering framework "
        "applicable to registered intermediaries.",
        "The KYC Registration Agency system enables inter-usability of client records across "
        "registered intermediaries.",
        "A uniform account opening form has been prescribed for all trading and demat accounts.",
    ],
    "margin_risk": [
        "The margin framework is intended to ensure that risk arising from client positions is "
        "adequately covered at all times.",
        "The peak margin obligation is computed on the basis of snapshots taken by the clearing "
        "corporation during the trading day.",
        "The definitions of the margin components referred to in this circular are those specified "
        "by the clearing corporations.",
    ],
    "investor_grievance": [
        "The SCORES platform provides a centralised web-based mechanism for lodging and tracking "
        "investor complaints.",
        "An efficient grievance redressal mechanism enhances investor confidence in the securities "
        "market.",
        "The timelines referred to in this circular are exclusive of the time taken by the "
        "complainant to provide additional information.",
    ],
    "outsourcing_bcp": [
        "Intermediaries increasingly rely on third-party service providers for technology and "
        "operational support.",
        "Outsourcing does not diminish the obligations of the intermediary or of its board and "
        "senior management under the securities laws.",
        "Business continuity arrangements are intended to ensure uninterrupted service to investors.",
    ],
}

# ── Document metadata per family ─────────────────────────────────────────────

FAMILY_META: Dict[str, Dict] = {
    "cyber_security": {
        "dept": "MIRSD", "pod": "MIRSD-PoD-1",
        "subject": "Cyber Security and Cyber Resilience Framework for Market Intermediaries",
        "primary": ["stockbroker", "depository"],
        "addressees": ["All Stock Brokers through Stock Exchanges",
                       "All Depository Participants through Depositories",
                       "All Registrars to an Issue and Share Transfer Agents"],
        "sections": ["Governance and Policy", "Identification and Protection",
                     "Detection and Monitoring", "Response and Recovery",
                     "Audit and Reporting"],
    },
    "surveillance": {
        "dept": "ISD", "pod": "ISD-PoD-2",
        "subject": "Strengthening of Surveillance Mechanism and Alert Disposal by Market Intermediaries",
        "primary": ["stockbroker", "depository"],
        "addressees": ["All Stock Brokers through Stock Exchanges",
                       "All Depository Participants through Depositories",
                       "All Recognised Stock Exchanges"],
        "sections": ["Surveillance Infrastructure", "Alert Generation and Disposal",
                     "Client Due Diligence", "Record Maintenance", "Reporting to Exchanges"],
    },
    "kyc_onboarding": {
        "dept": "MIRSD", "pod": "MIRSD-PoD-2",
        "subject": "Client Onboarding, KYC Norms and Risk Categorisation of Clients",
        "primary": ["stockbroker", "rta", "investment_adviser"],
        "addressees": ["All Registered Intermediaries",
                       "All Recognised Stock Exchanges and Depositories",
                       "All KYC Registration Agencies"],
        "sections": ["Client Identification", "In-Person Verification",
                     "Risk Categorisation", "Record Keeping", "Periodic Review"],
    },
    "margin_risk": {
        "dept": "MRD", "pod": "MRD-PoD-3",
        "subject": "Upfront Collection and Reporting of Margins by Trading and Clearing Members",
        "primary": ["stockbroker", "fiduciary"],
        "addressees": ["All Recognised Stock Exchanges", "All Clearing Corporations",
                       "All Stock Brokers and Clearing Members"],
        "sections": ["Margin Collection", "Margin Reporting", "Client Fund Segregation",
                     "Risk Monitoring", "Disclosure to Clients"],
    },
    "investor_grievance": {
        "dept": "OIAE", "pod": "OIAE-PoD-1",
        "subject": "Investor Grievance Redressal Mechanism and Disclosure of Complaints Data",
        "primary": ["stockbroker", "listed_company", "investment_adviser"],
        "addressees": ["All Listed Entities", "All Registered Intermediaries",
                       "All Recognised Stock Exchanges and Depositories"],
        "sections": ["Grievance Redressal Framework", "SCORES Timelines",
                     "Online Dispute Resolution", "Disclosure Requirements",
                     "Records and Review"],
    },
    "outsourcing_bcp": {
        "dept": "MIRSD", "pod": "MIRSD-PoD-4",
        "subject": "Outsourcing of Activities and Business Continuity Requirements for Intermediaries",
        "primary": ["stockbroker", "depository", "rta"],
        "addressees": ["All Registered Intermediaries",
                       "All Recognised Stock Exchanges and Depositories"],
        "sections": ["Outsourcing Policy", "Service Provider Due Diligence",
                     "Business Continuity and Disaster Recovery",
                     "Contractual Safeguards", "Board Oversight"],
    },
}


# ── Spec dataclasses ─────────────────────────────────────────────────────────

@dataclass
class Clause:
    """One numbered clause plus its ground-truth labels."""
    number: str
    text: str
    is_obligation: bool
    category: str
    severity: str = "medium"
    intermediaries: List[str] = field(default_factory=list)
    deadline: Optional[str] = None
    deadline_type: str = "not_specified"
    responsible: str = ""
    evidence: List[str] = field(default_factory=list)
    action: str = ""
    # Which template produced this clause. Held-out templates give an honest
    # generalisation score — see train.py.
    template_id: str = ""


@dataclass
class Section:
    heading: str
    clauses: List[Clause]


@dataclass
class CircularSpec:
    circular_id: str        # filesystem-safe id
    reference: str          # SEBI/HO/MIRSD/... printed on the document
    family: str
    subject: str
    issue_date: date
    effective_date: date
    addressees: List[str]
    preamble: List[str]
    sections: List[Section]
    closing: List[str]
    intermediary_types: List[str]
    amends: Optional[str] = None

    @property
    def all_clauses(self) -> List[Clause]:
        return [c for s in self.sections for c in s.clauses]

    def to_text(self) -> str:
        """Plain-text rendering — the exact string the model is trained on."""
        lines = [
            "SECURITIES AND EXCHANGE BOARD OF INDIA",
            "",
            self.reference,
            self.issue_date.strftime("%B %d, %Y"),
            "",
            "To,",
        ]
        lines += [f"    {a}" for a in self.addressees]
        lines += ["", f"Sub: {self.subject}", ""]
        for p in self.preamble:
            lines += [p, ""]
        for sec in self.sections:
            lines += [sec.heading, ""]
            for c in sec.clauses:
                lines += [f"{c.number} {c.text}", ""]
        for p in self.closing:
            lines += [p, ""]
        lines += ["Yours faithfully,", "", "General Manager", "Market Intermediaries Regulation",
                  "and Supervision Department"]
        return "\n".join(lines)


# ── Generation ───────────────────────────────────────────────────────────────

def _fill(template: str, rng: random.Random, itype: str) -> Tuple[str, Dict[str, str]]:
    """Slot-fill a template, returning the text and the values used."""
    used = {
        "entity": rng.choice(ENTITIES[itype]),
        "period": rng.choice(PERIODS),
        "frequency": rng.choice(FREQUENCIES),
        "authority": rng.choice(AUTHORITIES),
        "responsible": rng.choice(RESPONSIBLE_PARTIES),
    }
    text = template
    for k, v in used.items():
        text = text.replace("{" + k + "}", v)
    return text, used


def _deadline_value(deadline_type: str, used: Dict[str, str], rng: random.Random) -> Optional[str]:
    if deadline_type == "relative":
        return f"within {used['period']}"
    if deadline_type == "recurring":
        return used["frequency"]
    if deadline_type == "fixed":
        d = date.today() + timedelta(days=rng.randint(30, 300))
        return d.strftime("%Y-%m-%d")
    return None


def build_circular(
    family: str,
    seed: int,
    ref_number: Optional[int] = None,
    issue_date: Optional[date] = None,
    clauses_per_section: Tuple[int, int] = (2, 4),
    amends: Optional[str] = None,
    variant_label: str = "",
) -> CircularSpec:
    """Build one complete, internally consistent circular spec."""
    rng = random.Random(seed)
    meta = FAMILY_META[family]
    # Stable id per template (position in the bank) survives the shuffle below.
    template_ids = {t[0]: f"{family}#{i:02d}" for i, t in enumerate(OBLIGATION_TEMPLATES[family])}
    templates = list(OBLIGATION_TEMPLATES[family])
    rng.shuffle(templates)

    issue_date = issue_date or date(2026, rng.randint(1, 8), rng.randint(1, 28))
    effective = issue_date + timedelta(days=rng.choice([30, 60, 90]))
    ref_number = ref_number if ref_number is not None else rng.randint(1, 199)
    reference = (f"SEBI/HO/{meta['dept']}/{meta['pod']}/P/CIR/{issue_date.year}/"
                 f"{ref_number:03d}")
    circular_id = re.sub(r'[^A-Za-z0-9]+', '_', reference).strip('_')

    itypes = list(meta["primary"])
    context_pool = CONTEXT_TEMPLATES["_common"] + CONTEXT_TEMPLATES.get(family, [])

    # Preamble: 2-3 recital paragraphs (never obligations)
    preamble = rng.sample(context_pool, k=min(3, len(context_pool)))

    sections: List[Section] = []
    t_idx = 0
    clause_no = 1
    for sec_i, heading_text in enumerate(meta["sections"], start=1):
        n = rng.randint(*clauses_per_section)
        clauses: List[Clause] = []
        for j in range(n):
            if t_idx >= len(templates):     # wrap around with fresh slot fills
                rng.shuffle(templates)
                t_idx = 0
            tmpl, severity, dl_type, evidence, action = templates[t_idx]
            t_idx += 1
            itype = rng.choice(itypes)
            text, used = _fill(tmpl, rng, itype)
            applies_to = sorted(set([itype] + rng.sample(itypes, k=rng.randint(0, len(itypes) - 1))))
            clauses.append(Clause(
                number=f"{sec_i}.{j + 1}",
                text=text,
                is_obligation=True,
                category=family,
                severity=severity,
                intermediaries=applies_to,
                deadline=_deadline_value(dl_type, used, rng),
                deadline_type=dl_type,
                responsible=used["responsible"],
                evidence=evidence,
                action=action,
                template_id=template_ids[tmpl],
            ))
        # Sprinkle one contextual (non-obligation) clause into most sections
        if rng.random() < 0.7:
            pos = rng.randrange(len(clauses) + 1)
            clauses.insert(pos, Clause(
                number=f"{sec_i}.{len(clauses) + 1}",
                text=rng.choice(context_pool),
                is_obligation=False,
                category=family,
            ))
            for k, c in enumerate(clauses, start=1):
                c.number = f"{sec_i}.{k}"
        sections.append(Section(heading=f"{sec_i}. {heading_text}", clauses=clauses))
        clause_no += n

    closing = [
        f"The provisions of this circular shall come into force with effect from "
        f"{effective.strftime('%B %d, %Y')}.",
        "This circular is issued in exercise of the powers conferred under Section 11(1) of the "
        "Securities and Exchange Board of India Act, 1992, read with the relevant regulations, to "
        "protect the interests of investors in securities and to promote the development of, and "
        "to regulate, the securities market.",
        "Stock exchanges and depositories are advised to bring the provisions of this circular to "
        "the notice of their members and participants, and to disseminate the same on their websites.",
    ]

    subject = meta["subject"] + (f" — {variant_label}" if variant_label else "")

    return CircularSpec(
        circular_id=circular_id,
        reference=reference,
        family=family,
        subject=subject,
        issue_date=issue_date,
        effective_date=effective,
        addressees=meta["addressees"],
        preamble=preamble,
        sections=sections,
        closing=closing,
        intermediary_types=itypes,
        amends=amends,
    )


def build_demo_corpus(seed: int = 20260807) -> List[CircularSpec]:
    """The 5 circulars written out as PDFs — one per demo family."""
    rng = random.Random(seed)
    specs = []
    for i, family in enumerate(DEMO_FAMILIES):
        specs.append(build_circular(
            family,
            seed=seed + i * 101,
            ref_number=17 + i * 23,
            issue_date=date(2026, 2 + i, rng.randint(3, 26)),
            clauses_per_section=(3, 4),
        ))
    return specs


def build_holdout_specs(seed: int = 777) -> List[Tuple[str, CircularSpec]]:
    """
    Unseen circulars for testing recognition:
      - amendment: same family as a trained circular (should classify with high confidence)
      - novel:     a family the document classifier never saw (should flag low confidence)
    """
    amendment = build_circular(
        "surveillance", seed=seed, ref_number=204,
        issue_date=date(2026, 7, 15), clauses_per_section=(2, 3),
        variant_label="Amendment",
    )
    novel = build_circular(
        "outsourcing_bcp", seed=seed + 5, ref_number=211,
        issue_date=date(2026, 7, 29), clauses_per_section=(2, 3),
    )
    return [("holdout_amendment", amendment), ("holdout_novel_topic", novel)]


def build_training_specs(n_per_family: int = 6, seed: int = 4242) -> List[CircularSpec]:
    """
    Augmented training set. Same template bank, different slot fills and clause
    orderings, so the classifier learns the *language* of an obligation rather
    than memorising the five demo documents.
    """
    specs: List[CircularSpec] = []
    for f_i, family in enumerate(DEMO_FAMILIES):
        for k in range(n_per_family):
            specs.append(build_circular(
                family,
                seed=seed + f_i * 1000 + k,
                ref_number=300 + f_i * 20 + k,
                clauses_per_section=(3, 5),
            ))
    return specs


# ── Negative documents (used to train "is this a SEBI circular?") ─────────────

_NEGATIVE_DOCS: List[Tuple[str, str]] = [
    ("quarterly_results_press_release",
     "PRESS RELEASE\n\nThe company today announced its financial results for the quarter ended "
     "June 30, 2026. Revenue from operations grew 14 percent year on year to Rs. 1,240 crore, "
     "driven by strong demand in the domestic market and a favourable product mix. EBITDA margin "
     "expanded by 180 basis points to 21.4 percent. The management commented that the demand "
     "environment remains healthy and that capacity expansion at the Pune facility is on track for "
     "commissioning in the third quarter. The board has recommended an interim dividend of Rs. 4 "
     "per equity share. A conference call for analysts and investors will be held on Friday at "
     "4:00 PM IST. Details for the webcast are available on the investor relations section of the "
     "company website."),
    ("software_user_manual",
     "USER MANUAL — VERSION 3.2\n\nGetting started. Install the application by running the setup "
     "package and following the on-screen prompts. On first launch you will be asked to create a "
     "workspace. A workspace stores your projects, preferences and cached data. To create a new "
     "project, click File, then New Project, and choose a template from the gallery. Keyboard "
     "shortcuts are listed in Appendix B. If the application fails to start, check that your "
     "graphics driver is up to date and that at least 4 GB of memory is available. Log files are "
     "written to the application data folder and can be attached when contacting support. "
     "Troubleshooting steps for common network errors are described in the following section."),
    ("research_paper_abstract",
     "Abstract. We study the propagation of liquidity shocks in limit order book markets using a "
     "high-frequency dataset spanning three years. We document that order book imbalance predicts "
     "short-horizon returns and that the predictive power decays within seconds. Our identification "
     "strategy exploits exogenous variation in tick size introduced by a market-wide reform. We find "
     "that the effect is concentrated among stocks with lower market capitalisation. The results are "
     "robust to alternative measures of imbalance and to controlling for volatility clustering. We "
     "conclude with a discussion of the implications for market design and for the measurement of "
     "execution quality by institutional traders."),
    ("employment_contract",
     "EMPLOYMENT AGREEMENT\n\nThis agreement is made between the employer and the employee on the "
     "date set out above. The employee will be designated as Senior Engineer and will report to the "
     "Engineering Manager. The annual cost to company is set out in Schedule 1. The employee is "
     "entitled to twenty-one days of paid leave per calendar year, accruing monthly. Either party "
     "may terminate this agreement by giving sixty days written notice. During the term of "
     "employment, the employee will not engage in any other gainful occupation without prior written "
     "consent. All intellectual property created in the course of employment vests with the employer. "
     "Disputes arising under this agreement are subject to the jurisdiction of the courts at Bengaluru."),
    ("invoice_document",
     "TAX INVOICE\n\nInvoice number INV-2026-00842. Invoice date July 12, 2026. Bill to: Northwind "
     "Trading Company, 4th Floor, Commerce House, Mumbai 400001. Description of services: cloud "
     "infrastructure and managed database hosting for the billing period June 2026. Quantity one. "
     "Unit price Rs. 185000. Taxable value Rs. 185000. CGST at nine percent Rs. 16650. SGST at nine "
     "percent Rs. 16650. Total amount payable Rs. 218300. Payment is due within thirty days of the "
     "invoice date. Please quote the invoice number in the payment reference. Bank details for the "
     "remittance are printed at the foot of this invoice."),
    ("news_article",
     "Benchmark indices closed higher on Tuesday, extending gains for a third consecutive session as "
     "buying in banking and information technology stocks lifted sentiment. The rally was broad based, "
     "with the mid-cap index outperforming the headline gauge. Traders attributed the move to easing "
     "bond yields and to expectations of a steady monetary policy decision later this month. Foreign "
     "portfolio investors were net buyers, according to provisional exchange data. Analysts cautioned "
     "that valuations remain elevated relative to historical averages and that earnings delivery in "
     "the coming quarter will be the key driver of further upside. The rupee ended marginally stronger "
     "against the dollar."),
    ("meeting_minutes",
     "MINUTES OF THE PROJECT REVIEW MEETING\n\nThe meeting was called to order at 10:30 AM. Present "
     "were the project manager, the technical lead, the quality analyst and two developers. The "
     "previous minutes were read and approved without amendment. The technical lead presented the "
     "sprint burndown and noted that two stories had carried over because of a dependency on the "
     "vendor API. It was agreed that the integration test environment would be refreshed before the "
     "next sprint. The quality analyst raised a concern about flaky tests in the payment module and "
     "volunteered to triage them. The next meeting was scheduled for the following Thursday. The "
     "meeting concluded at 11:15 AM."),
    ("recipe_text",
     "Slow cooked tomato and basil soup. Serves four. Heat two tablespoons of olive oil in a heavy "
     "bottomed pan over medium heat. Add finely chopped onions and cook until translucent, about "
     "eight minutes. Stir in the garlic and cook for a further minute, taking care not to let it "
     "colour. Add the chopped tomatoes, a pinch of sugar and the stock, then bring to a gentle "
     "simmer. Cover partially and cook for forty minutes, stirring occasionally. Blend until smooth "
     "and pass through a sieve for a finer texture. Finish with torn basil leaves and a swirl of "
     "cream. Season to taste and serve with toasted sourdough."),
]


# ── Structural noise (negatives that only appear in real PDFs) ───────────────
# The demo circulars are clean, but a real 38-page master circular is full of
# contents lists, abbreviation tables and cross-references. Without these as
# explicit negatives the classifier happily labels "Trading Rules ... 7" an
# obligation, because it has never seen a line that looks like that.

_TOC_TITLES = [
    "Trading Rules and Shareholding in dematerialized mode", "Surveillance Obligations of MIIs",
    "Alert Generation and Disposal", "Trading Window Closure", "Suspension of Trading",
    "Handling of Investor Complaints", "Reporting Requirements", "Price Band and Circuit Filters",
    "Insider Trading Restrictions", "Monitoring of Client Activity", "Annexure to the Circular",
    "Definitions and Interpretation", "Margin Trading Facility", "Penalty and Enforcement",
    "Rescission and Savings", "Applicability and Effective Date",
]

_ABBREVIATIONS = [
    ("MII", "Market Infrastructure Institution"), ("PIT", "Prohibition of Insider Trading"),
    ("UPSI", "Unpublished Price Sensitive Information"), ("DP", "Depository Participant"),
    ("RTA", "Registrar and Transfer Agent"), ("IA", "Investment Adviser"),
    ("SOP", "Standard Operating Procedure"), ("STR", "Suspicious Transaction Report"),
    ("KRA", "KYC Registration Agency"), ("ODR", "Online Dispute Resolution"),
    ("VAPT", "Vulnerability Assessment and Penetration Testing"),
    ("BCP", "Business Continuity Plan"), ("AMC", "Asset Management Company"),
    ("CC", "Clearing Corporation"), ("IPEF", "Investor Protection and Education Fund"),
]

_DEFINITION_TERMS = [
    ('"Designated Person"', "a person designated as such by the board of the listed entity"),
    ('"Trading Window"', "the period during which trading in securities is permitted"),
    ('"Alert"', "an exception generated by the surveillance system of the intermediary"),
    ('"Material Event"', "an event specified in Schedule III of the Listing Regulations"),
    ('"Client"', "a person on whose behalf the intermediary acts in the securities market"),
    ('"Working Day"', "a day on which the recognised stock exchanges are open for trading"),
]

_CROSS_REFS = [
    "Refer to paragraph 4.2 of this Master Circular.",
    "As per Regulation 4(2) of the SEBI (Intermediaries) Regulations, 2008.",
    "In terms of Schedule B read with Regulation 9 of the PIT Regulations.",
    "Pursuant to the circular dated March 12, 2024 referred to above.",
    "See Annexure C for the reporting format.",
    "The provisions of Chapter IV shall apply mutatis mutandis.",
]

_TABLE_ROWS = [
    "Sr. No. Particulars Timeline Applicability",
    "1 Alert disposal T+30 days All members",
    "2 Quarterly report 15 days from quarter end Trading members",
    "Type of Alert Threshold Frequency Source",
    "Category A 5% of traded volume Daily Exchange",
    "Segment Cash Derivatives Currency Commodity",
    "Particulars FY 2024-25 FY 2025-26 Change",
]


def build_structural_noise(seed: int = 31) -> List[str]:
    """Non-obligation lines of the kind real circular PDFs are full of."""
    rng = random.Random(seed)
    out: List[str] = []

    for i, title in enumerate(_TOC_TITLES):
        page = rng.randint(1, 60)
        out.append(f"{title} {page}")                       # contents entry
        out.append(f"{i + 1}. {title} .......... {page}")   # with dot leaders
        out.append(title.upper())                            # bare heading

    for abbr, expansion in _ABBREVIATIONS:
        out.append(f"{abbr} {expansion}")
        out.append(f"{abbr} - {expansion}")

    for term, meaning in _DEFINITION_TERMS:
        out.append(f"{term} means {meaning};")
        out.append(f"For the purpose of this circular, {term} means {meaning}.")

    out.extend(_CROSS_REFS)
    out.extend(_TABLE_ROWS)

    # Annexure index runs. Real master circulars end with pages of these, and
    # because the titles they list often contain "shall", they sail past a
    # modality-only filter — on the 399-page stock broker circular they were the
    # top-scoring false positives until they were added here.
    _ANNEX_TITLES = [
        "Digital Mode of Payment", "Format for Monthly Reporting",
        "Details of FMC circulars which shall stand repealed",
        "List of circulars which shall continue to apply",
        "Format of the Annual Compliance Certificate",
        "Illustration of margin computation", "Reporting format for alerts",
        "Terms and conditions of the tripartite agreement",
        "Contents of the risk disclosure document",
    ]
    for i, title in enumerate(_ANNEX_TITLES, start=30):
        out.append(f"Annexure-{i} - {title}")
        out.append(f"Annexure-{i} - {title} Annexure-{i+1} - {_ANNEX_TITLES[(i) % len(_ANNEX_TITLES)]}")
        out.append(f"Annexure {i}: {title} {rng.randint(40, 380)}")
    out.extend([
        "Annexure-40 - Digital Mode of Payment Annexure-41 - Details of FMC circulars which "
        "shall stand repealed and 38 relevant SEBI circulars which shall be applicable",
        "Annexure-42 - Details of FMC circulars contents/norms of which are covered in this "
        "Master Circular",
        "List of Annexures",
        "Chapter Particulars Page No.",
        "The list of circulars rescinded is placed at Annexure-A to this Master Circular.",
    ])
    out.extend([
        "Page 12 of 38",
        "SEBI/HO/ISD/ISD-PoD-2/P/CIR/2025/041",
        "TABLE OF CONTENTS",
        "LIST OF ABBREVIATIONS",
        "CHAPTER 3",
        "Annexure A",
        "Format for reporting of alerts",
        "(Amended vide circular dated June 03, 2025)",
        "www.sebi.gov.in",
        "This Master Circular is a compilation of the circulars issued by SEBI up to March 31, 2025.",
        "The circulars listed in the Appendix stand rescinded with effect from the date of this circular.",
        "Notwithstanding such rescission, anything done or any action taken under the rescinded "
        "circulars shall be deemed to have been done or taken under the corresponding provisions "
        "of this Master Circular.",
    ])
    return out


def build_negative_documents(n: int = 8, seed: int = 99) -> List[Tuple[str, str]]:
    """Non-regulatory documents, so the recogniser can say 'this is not a circular'."""
    rng = random.Random(seed)
    docs = list(_NEGATIVE_DOCS)
    if n <= len(docs):
        return docs[:n]
    # Repeat with shuffled paragraph order to reach the requested count
    out = list(docs)
    while len(out) < n:
        name, text = rng.choice(docs)
        paras = text.split("\n\n")
        rng.shuffle(paras)
        out.append((f"{name}_v{len(out)}", "\n\n".join(paras)))
    return out
