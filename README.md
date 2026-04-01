Payment Reconciliation System

This project simulates a reconciliation system between a payments platform and bank settlements to identify mismatches and discrepancies.

Problem

Transactions recorded by a platform may not always match bank settlements due to delays, duplicates, rounding differences, or missing entries. This system helps identify and categorize such inconsistencies.

Features
Detects missing settlements (unsettled transactions)
Identifies duplicate bank entries
Handles rounding differences within tolerance
Flags significant amount mismatches
Detects phantom bank entries (no matching transaction)
Provides a lightweight HTML-based UI for better visualization
Approach
Generated synthetic datasets for transactions and settlements
Used txn_id as the primary key for reconciliation
Categorized outcomes into match, mismatch, duplicates, etc.
Kept logic simple while documenting real-world limitations
How to Run
Step 1: Run reconciliation
python reconciliation_system.py
Step 2: Generate UI report
python reconciliation_report.py
Step 3: Open UI

Open reconciliation_report.html in any browser

Output

The system provides:

Summary statistics of reconciliation
Categorized discrepancies (mismatches, duplicates, etc.)
Clean visual UI for easy interpretation
Detailed tables for analysis
Scope Decisions
Fee deductions are not handled explicitly
Settlement timing boundaries are not considered
Multi-currency transactions are out of scope

These are intentionally excluded to keep the implementation simple and focused.

Limitations
Assumes 1:1 mapping between transaction and settlement
Does not handle partial settlements (split payments)
Does not support chargebacks or reversals
Not optimized for large-scale datasets
Uses in-memory processing (not production scalable)
Tech Stack
Python 3
HTML (for visualization)
No external dependencies
