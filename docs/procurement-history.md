# Procurement History

Procurement history imports purchase-order line data so analytics can distinguish actual spend from estimated savings.

## Required Columns

- CPSE
- source system
- source material code
- date
- quantity
- UOM
- unit price
- total amount
- vendor, optional
- PO reference, optional

## Reconciliation

Rows are linked to `SourceMaterial` by CPSE, source system, and material code. If an approved mapping exists, the row is also linked to the corresponding national material.

## Analytics

Production analytics now report:

- actual procurement spend
- actual quantity
- vendor count
- approved national-code spend
- reconciliation status

Estimated savings remain separate and are never substituted when procurement history is available.
