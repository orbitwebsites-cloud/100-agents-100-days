"""Lead Scout — the inbound-lead agent.

Agent #3 of the 100-agents-100-days build. When a new lead lands in the CRM,
Lead Scout pulls up their actual website, audits it for real (load time, SSL,
mobile, SEO, broken links, dead contact forms), writes the findings back onto
the CRM record, and drafts a pitch email that quotes their real numbers.

The audit is measured, not guessed — that's the whole point. No language model
can tell you a stranger's site takes 4.2s to load or that their contact form
404s. Lead Scout goes and looks.
"""
