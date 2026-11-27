# Data Exploration Notes

## Customers
- Columns: customer_id (C00001), registration_date, county, age_group, account_type.
- Observation: Most customers are 'individual', and the ages are mostly 18-34.

## Agents
- Columns: agent_id (A0001), county.
- Observation: Agents are spread across counties; Nairobi has a few in a row (A0002, A0003...).

## Merchants
- Columns: merchant_id, merchant_kind (paybill/till), category, county.
- Observation: Paybills have 'National' as county, while tills have specific counties.

## Transactions
- Columns: txn_id, txn_ts, customer_id, txn_type, amount, fee, status, counterparty_type, counterparty_id.
- Observation: Airtime has NULL for counterparty_type and counterparty_id. Timestamps are formatted as 'YYYY-MM-DD HH:MM:SS'.
