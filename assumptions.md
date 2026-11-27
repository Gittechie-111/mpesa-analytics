# Assumptions

- **Data Scope:** 2026-01-01 to 2026-06-30. "Today" = 2026-06-30.
- **Status Handling:** For all value, volume, and activity metrics, I will use `status = 'SUCCESS'` only. FAILED and REVERSED transactions do not represent actual money moved and are excluded. (Exception: Q1 success rate uses all rows as the denominator).
- **Counterparty:** `counterparty_id` is polymorphic. I must always filter on `counterparty_type` when joining.
- **Active Customer:** A customer with at least 1 SUCCESS transaction in the 6-month window.