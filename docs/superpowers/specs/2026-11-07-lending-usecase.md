# End to end use case: personal loan model governance

Date: 2026-11-07

This is the spec for the pipeline plan. It describes the business the demo is about, who acts, and which pipelines exist today.

## The decision

Emirates NBD Demo is a fictional UAE bank. It offers personal loans. Loan model v2 scores those applications today, including the west region. The bank wants loan model v3 to take that job. On the holdout, v3 misses 4 more defaults per 100 than v2. v3 still expects a debt to income column. That column left the application file last month. Yesterday's file also arrived without two other columns, and scoring failed.

The product decides whether v3 may score live applications. It does not decide any one person's loan. It does not pay out a loan. It does not change production.

## Who this serves and how

Casework serves the bank staff who have to decide whether a new credit model may score personal loans. The only person who uses the desk is the analyst. Everyone else is served by a reply, a queue item, or a refusal. An applicant is the subject of the file. They are not the audience.

Credit risk owns loan model v2 and loan model v3. They need a hold or promote answer before v3 scores live applications. They do not sign in. The analyst opens the case, the agent drafts a reply that cites both models, and Approve stores that reply for credit risk. Nothing is emailed, and the model that scores loans stays v2.

Lending ops owns the application file, the weekly credit review, and the open retrain note. Their requests sit in the same queue. The draft names the missing columns and the review that still has no owner. A request to rescore production is refused.

The Casework analyst is the person signed in on the desk. They pick a request, watch the agent plan, read the graph, and draft through OmniRoute, then Approve, Escalate, or Reject. The checker blocks a reply that cites nothing.

The pod lead is the analyst's lead when a case should not be closed on the desk. Escalate records the case for them. It does not send a message, and it does not contact an applicant.

An applicant asked the bank for a personal loan. They are a row in the application file, not a user of Casework. They apply at the bank, outside this product. This desk never shows them a decision and never pays a loan.

Another bank on the same platform is not served by this desk. Their findings stay in their own tenant. A request from Emirates NBD Demo to read them is refused and written to the audit.

## How an application exists

People apply at the bank, outside this product. What this product sees is an application file: one row per application, with an id, a region, income, loan amount, and debt to income. The file is synthetic. The rows are the applicants. There is no origination website in this repo.

The holdout sentence "4 more defaults per 100" stays a labeled fact on the case. A small sample file shows who is in the book. The sample is not re-counted into a new holdout statistic.

## Stakeholders

| Stakeholder | What they need | In the product today |
|---|---|---|
| Applicant | A row in the application file. No account. | Named only as "applications" in prose. No rows. |
| Lending ops | A valid file, a weekly credit review owner, a closed retrain note, a refused production rescore. | Static findings F-102, F-103, F-107. |
| Credit risk | The hold or promote reply, the holdout fact, which model scores the west region, an owner for nightly scoring. | Static findings F-101, F-104, F-105, F-106. The desk drafts a reply. |
| Model steward | A promotion gate that cannot flip the live scorer from this desk. | No gate. v2 and v3 are graph labels. |
| Casework analyst | The queue, the graph, the model draft, the checker, the decision. | Built. OmniRoute writes the reply. |
| Pod lead | A queue of escalations. | Escalate writes an audit row. Nobody else can open it. |
| Other customer | Nothing. A cross tenant request is refused. | Built for F-901 and tenant_other_corp. |

## Pipelines

1. Intake. Read the application file. Report missing columns. Open the intake findings from that report.
2. Scoring. Record that v2 is the live scorer, that the west region is on v2, and that nightly scoring has an owner or does not.
3. Evidence. Attach the holdout fact and the missing debt to income fact to v3. Do not invent a new miss rate.
4. Casework. LangGraph plans, reads the graph, ranks, asks OmniRoute for the reply, and the checker demands a real citation. Built.
5. Decision. Approve addresses credit risk. Escalate appears for the pod lead. Reject returns the draft. None of these call the bank or change the live scorer.
6. Promotion. A request to put v3 live is refused. The live scorer stays v2.
7. Lending ops. Name the weekly review owner in the draft only. Leave the retrain note open until a person closes it. A request to rescore production is refused.
8. Tenant wall. No pipeline reads or writes another tenant's book.

## Out of scope

A public apply page, identity checks, disbursement, collections, a real credit bureau, and any change to OmniRoute. Scanner tools stay as they are. Each triage run opens a casework.run span and sends it when DataRobot monitoring is configured.
