# Dataset and local files

The batch uses version 8 of IBM's synthetic anti-money-laundering transaction data:

- Dataset handle: `ealtman2019/ibm-transactions-for-anti-money-laundering-aml/versions/8`
- [Dataset source](https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml/versions/8)
- Required file: `HI-Small_Trans.csv`
- Data rows: **5,078,345**
- Required SHA-256: `b19d39f515523373f991b689c07e11e7b0b95c17a2c27a87d91584ae16c5b040`

The original CSV is not included. Obtain it from the dataset provider and follow
the provider's license and terms. The runner checks the complete file identity;
a sorted, filtered, or edited CSV is not a substitute. Original zero-based row
positions define stable event IDs. The patterns file is not used.

The fixed cohort contains 1,024 destination-account/minute queries selected from
3,854,758 units with complete 24-hour lookback histories. The seed is `20261030`.
Selection did not use laundering labels, eligibility, or solver outcomes.
`batch/cohort.json` contains synthetic account identifiers and timestamps required
for exact replay. It is a cohort specification, not a real-customer dataset.

`results/BATCH_RESULTS.zip` contains aggregate outcomes only. The original dataset,
SQLite cache, detailed local contexts, full profiles and native witness files are
not included in that export. The small `batch/examples/demo_transactions.csv` is
an artificial demonstration created for the runner and is not the IBM dataset.

Dataset paper: Erik Altman and colleagues, *Realistic Synthetic Financial
Transactions for Anti-Money Laundering Models*, NeurIPS 2023,
[DOI 10.52202/075280-1300](https://doi.org/10.52202/075280-1300).
Source identities and sampling details are preserved in
[`SOURCE_COHORT_PROTOCOL.json`](../batch/SOURCE_COHORT_PROTOCOL.json) and the
current [`batch_protocol.json`](../batch/batch_protocol.json).
