# Contract plan: `SampleHiveDataset`

- DataHub asset: `urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)`
- Plan SHA-256: `9c100558ffa9a172ffcdd63c6ebb2172b94a3a56c5d84afb8f0e5ce03df9d161`
- Declared fields: 3
- Contract-tagged tests: 1
- Downstream assets: 0
- Owners: urn:li:corpuser:jdoe, urn:li:corpuser:datahub

## Risks

| Severity | Code | Subject | Detail |
|---|---|---|---|
| high | FIELD_REMOVAL | `field_bar` | Present in DataHub but absent from the enforced dbt contract. |
| high | FIELD_REMOVAL | `field_foo` | Present in DataHub but absent from the enforced dbt contract. |
| info | FIELD_ADDITION | `event_timestamp` | Declared by dbt but not present in the current DataHub schema. |
| info | FIELD_ADDITION | `event_type` | Declared by dbt but not present in the current DataHub schema. |
| info | FIELD_ADDITION | `id` | Declared by dbt but not present in the current DataHub schema. |

Mutation is not authorized by this artifact. Re-supply the exact plan hash to confirm write-back.
