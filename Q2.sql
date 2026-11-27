-- SQLite
SELECT strftime('%H', txn_ts) AS hour_of_day,
        COUNT(*) AS transaction_count,
        ROUND(100.0* COUNT(*)/SUM(COUNT(*)),1) AS share_percentage
FROM transactions
GROUP BY hour_of_day
ORDER BY transaction_count DESC;
