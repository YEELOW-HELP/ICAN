# MNP UA MARKET DATA MODEL V1

## Objects
MarketSnapshot, SalarySnapshot, DemandSnapshot, Employer/sector aggregates where permitted.

## Dimensions
career, country, region/city, date, source, sample size/data quality.

## Metrics
vacancy volume, salary distribution, demand trend, remote share, entry-level availability, common skills/tools, experience requirements.

## Rules
Market facts are snapshots, never permanent Career fields.
No unsupported salary/demand claims.
MARKET_DATA_LIMITED when coverage is insufficient.
Source/legal access policy is implemented per provider agreement/terms.
